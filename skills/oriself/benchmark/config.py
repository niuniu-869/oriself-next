"""
Benchmark 配置 · 16×30 压力测试（v2.4.2 验证轮）。

- mimo-v2-pro  · 作为 OriSelf（对话主理人 + converge 报告生成）
- mimo-v2-flash · 作为被试者（16 MBTI × 30 风格 = 480 位不同的人）
- RPM 打到 100（上一轮 wait_seconds 多数 ~0，瓶颈在 backend 延迟而非限流）
- MAX_CONCURRENT_SESSIONS 提到 100 吃满带宽
"""
from __future__ import annotations

import os
from dataclasses import dataclass


API_BASE_URL = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
API_KEY = os.environ.get(
    "MIMO_API_KEY",
    "sk-c3f447qx88w88m1hljsd5yvsqk4vwsigf9abyz3al95eopyn",
)

MODEL_ORISELF = "mimo-v2-pro"
MODEL_SUBJECT = "mimo-v2-flash"

# mimo-v2-pro 是推理模型，reasoning + content 总 token 预算要拉够
MAX_TOKENS_TURN = 4096          # 对话轮
MAX_TOKENS_CONVERGE = 32768     # 报告生成（含 HTML，很长）
MAX_TOKENS_SUBJECT = 1024       # 被试者每轮最多说这么多

# 限流
RPM_CAP = 100                   # 令牌桶每分钟放这么多
MAX_CONCURRENT_SESSIONS = 100   # 同时开 100 场对话
PER_REQUEST_TIMEOUT = 240.0     # 单请求超时

# 轮数硬上限（与 server/schemas.MAX_ROUNDS 对齐）
MAX_ROUNDS = 30
MIN_CONVERGE_ROUND = 6

# 产物目录
BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BENCHMARK_DIR, "results")
LOGS_DIR = os.path.join(BENCHMARK_DIR, "logs")


@dataclass(frozen=True)
class BenchmarkConfig:
    base_url: str = API_BASE_URL
    api_key: str = API_KEY
    model_oriself: str = MODEL_ORISELF
    model_subject: str = MODEL_SUBJECT
    rpm_cap: int = RPM_CAP
    max_concurrent: int = MAX_CONCURRENT_SESSIONS
    max_rounds: int = MAX_ROUNDS
    max_tokens_turn: int = MAX_TOKENS_TURN
    max_tokens_converge: int = MAX_TOKENS_CONVERGE
    max_tokens_subject: int = MAX_TOKENS_SUBJECT
    per_request_timeout: float = PER_REQUEST_TIMEOUT

    def as_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "model_oriself": self.model_oriself,
            "model_subject": self.model_subject,
            "rpm_cap": self.rpm_cap,
            "max_concurrent": self.max_concurrent,
            "max_rounds": self.max_rounds,
            "max_tokens_turn": self.max_tokens_turn,
            "max_tokens_converge": self.max_tokens_converge,
            "max_tokens_subject": self.max_tokens_subject,
        }


DEFAULT_CONFIG = BenchmarkConfig()
