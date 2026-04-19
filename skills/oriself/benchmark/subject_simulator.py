"""
被试者模拟器。
- 拿 Persona + 与 OriSelf 的对话历史，调 mimo-v2-flash 产出一句「被试」回复
- 被试 system prompt 在 persona.to_system_prompt() 定义
- 如果 flash 真的输出空、或出现"我是 AI"这类破戏词，这里做一次 fallback（不 retry LLM，只回落到人设里的一句话）
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List

_SERVER_PATH = Path(__file__).resolve().parents[4] / "server"
if str(_SERVER_PATH) not in sys.path:
    sys.path.insert(0, str(_SERVER_PATH))

from oriself_server.llm_client import Message  # noqa: E402

from .mimo_backend import MimoBackend  # noqa: E402
from .personas import Persona  # noqa: E402


logger = logging.getLogger(__name__)


_BREAK_CHARACTER_HINTS = (
    "作为AI", "作为 AI", "作为人工智能", "语言模型", "我是AI", "我是 AI",
    "我是一个AI", "我无法", "我是 OpenAI", "我是 ChatGPT",
)


class SubjectSimulator:
    def __init__(self, backend: MimoBackend):
        self.backend = backend

    async def respond(
        self,
        persona: Persona,
        conversation: List[tuple[str, str]],
        current_round: int,
    ) -> str:
        """基于完整对话历史产出被试者下一句话。

        conversation: [(oriself_text, user_text), ...]  —— 按时间顺序。
        但我们要让"被试者视角"里 OriSelf = assistant（对话伙伴），被试者 = user（自己）。
        对 LLM 来说，被试者的下一句要作为 assistant 角色生成。
        做法：把历史翻过来——被试者以前说的话作 assistant role，OriSelf 说的话作 user role。
        这样 LLM 自然扮演"下一个 assistant"即被试者。
        """
        sys_prompt = persona.to_system_prompt()
        msgs: List[Message] = [Message(role="system", content=sys_prompt)]

        # 第一轮：OriSelf 还没说话，被试者主动开场 —— 直接返回 persona.opening
        if current_round == 1 and not conversation:
            return persona.opening

        # 之后：历史按「被试者上一句 → OriSelf 说 → 被试者这一句」交替
        # conversation 里保存的是 [(subject_text, oriself_text)] — 我们从旧到新穿上去
        for subject_prev, oriself_said in conversation:
            # 被试者之前说的话 = assistant
            msgs.append(Message(role="assistant", content=subject_prev))
            # OriSelf 回的话 = user（对被试来说 OriSelf 是对方）
            msgs.append(Message(role="user", content=oriself_said))

        msgs.append(
            Message(
                role="system",
                content=(
                    f"[round={current_round}] 上面是你和对方的对话。"
                    "现在该你回复对方最后一句了。严格保持人设和说话风格。"
                    "不要问元问题、不要暴露你是 AI、不要提 MBTI 字母。"
                ),
            )
        )

        try:
            text = await self.backend.complete_text(msgs)
        except Exception as exc:
            logger.warning("subject backend error: %s — fallback to persona-safe line", exc)
            return _safe_fallback_line(persona, current_round)

        text = (text or "").strip()
        if not text or any(h in text for h in _BREAK_CHARACTER_HINTS):
            logger.info("subject broke character, using fallback")
            return _safe_fallback_line(persona, current_round)
        return text


def _safe_fallback_line(persona: Persona, round_n: int) -> str:
    """LLM 坏了或破戏时的兜底话。按风格给一句符合人设的安全句。"""
    fallbacks = {
        "literary": "嗯……脑子里一片雾，先让我缓一会儿。",
        "analytical": "嗯，我在想。",
        "casual_verbal": "哎，我也不知道说啥。",
        "tired": "就……有点累。",
        "introspective": "说不上来那种感觉。",
        "energetic": "哈哈哈我想想啊！",
        "jumpy": "对了，说回来——我有点忘了刚说到哪。",
        "silent": "嗯。",
        "verbose": "其实吧这个事挺复杂的，我再理一下。",
        "hesitant": "不知道诶，你觉得呢。",
    }
    return fallbacks.get(persona.style_key, "嗯。")
