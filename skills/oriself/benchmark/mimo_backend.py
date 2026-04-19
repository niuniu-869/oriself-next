"""
小米 mimo OpenAI-compatible backend，带两项本次 benchmark 关键增强：

1. `max_tokens` 显式注入 —— mimo-v2-pro 是推理模型，必须给够预算避免 finish=length
2. 每个调用先走 `AsyncRateLimiter.acquire()`，统一限流；
3. 本次 benchmark 还需要捕获**完整 raw payload**（请求 + 响应），这里 `last_raw_request`
   / `last_raw_response` 暴露出去给 recorder 抓。

对话轮：沿用 SSE 流式。
报告轮：非流式 JSON。
被试者轮：非流式文本。
"""
from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, List, Optional

import httpx

# 把 server 目录加入 sys.path，让我们复用 oriself_server.llm_client 的 Message 类型
_SERVER_PATH = Path(__file__).resolve().parents[4] / "server"
if str(_SERVER_PATH) not in sys.path:
    sys.path.insert(0, str(_SERVER_PATH))

from oriself_server.llm_client import Message, LLMBackend  # noqa: E402

from .rate_limiter import AsyncRateLimiter  # noqa: E402


logger = logging.getLogger(__name__)


@dataclass
class LLMCallRecord:
    """一次 LLM 调用的完整档案。写盘供事后审阅。"""
    model: str
    purpose: str                       # "turn" | "converge" | "subject"
    started_at: float = 0.0
    ended_at: float = 0.0
    wait_seconds: float = 0.0
    request_messages: list = field(default_factory=list)
    request_extra: dict = field(default_factory=dict)
    response_text: str = ""
    response_raw: Optional[dict] = None
    usage: Optional[dict] = None
    error: Optional[str] = None

    def duration(self) -> float:
        return max(0.0, self.ended_at - self.started_at)

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "purpose": self.purpose,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_sec": round(self.duration(), 3),
            "wait_seconds": round(self.wait_seconds, 3),
            "request_messages": self.request_messages,
            "request_extra": self.request_extra,
            "response_text": self.response_text,
            "response_raw": self.response_raw,
            "usage": self.usage,
            "error": self.error,
        }


class MimoBackend(LLMBackend):
    """mimo OpenAI-compatible，带 RPM 限流 + 完整调用日志。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        rate_limiter: AsyncRateLimiter,
        max_tokens: int = 4096,
        purpose: str = "turn",
        timeout: float = 240.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider_name = "mimo"
        self.rate_limiter = rate_limiter
        self.max_tokens = max_tokens
        self.purpose = purpose
        self.timeout = timeout
        # 上一次调用的记录，供 recorder 落盘
        self.last_call: Optional[LLMCallRecord] = None

    # ------- 流式文本（对话轮） -------
    async def stream_text(
        self,
        messages: List[Message],
        *,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[str]:
        req_msgs = [{"role": m.role, "content": m.content} for m in messages]
        payload = {
            "model": self.model,
            "messages": req_msgs,
            "stream": True,
            "max_tokens": self.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        record = LLMCallRecord(
            model=self.model,
            purpose=self.purpose,
            request_messages=req_msgs,
            request_extra={"stream": True, "max_tokens": self.max_tokens},
        )
        record.wait_seconds = await self.rate_limiter.acquire(1.0)
        record.started_at = time.time()
        buffer_parts: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as resp:
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode("utf-8", errors="replace")
                        raise RuntimeError(f"mimo stream {resp.status_code}: {body[:400]}")
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.startswith(":"):
                            continue
                        data = line[5:].strip() if line.startswith("data:") else line.strip()
                        if not data or data == "[DONE]":
                            if data == "[DONE]":
                                break
                            continue
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        chunk = delta.get("content")
                        if chunk:
                            buffer_parts.append(chunk)
                            yield chunk
        except Exception as exc:
            record.error = repr(exc)
            record.response_text = "".join(buffer_parts)
            record.ended_at = time.time()
            self.last_call = record
            raise
        record.response_text = "".join(buffer_parts)
        record.ended_at = time.time()
        self.last_call = record

    # ------- 非流式文本（报告轮 · v2.5.2 改 HTML / 被试者用） -------
    async def complete_text(
        self,
        messages: List[Message],
        *,
        timeout: Optional[float] = None,
    ) -> str:
        req_msgs = [{"role": m.role, "content": m.content} for m in messages]
        payload = {
            "model": self.model,
            "messages": req_msgs,
            "max_tokens": self.max_tokens,
        }
        record = LLMCallRecord(
            model=self.model,
            purpose=self.purpose,
            request_messages=req_msgs,
            request_extra={"max_tokens": self.max_tokens},
        )
        record.wait_seconds = await self.rate_limiter.acquire(1.0)
        record.started_at = time.time()
        try:
            async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            record.error = repr(exc)
            record.ended_at = time.time()
            self.last_call = record
            raise
        record.response_raw = data
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError):
            content = ""
        record.response_text = content
        record.usage = data.get("usage")
        record.ended_at = time.time()
        self.last_call = record
        return content
