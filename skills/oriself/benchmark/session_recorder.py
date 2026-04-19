"""
SessionRecorder · 每场对话一个目录，装下：
- metadata.json            · 人设 + 汇总统计
- transcript.md            · 人类可读的对话全文
- turns/turn_XX.json       · 每轮完整 OriSelf 请求 + 响应（含 full skill system prompt）
- subject/subject_XX.json  · 每轮被试者请求 + 响应
- converge_request.json    · 报告生成调用的 full system/user prompt
- converge_response.json   · LLM 原始 JSON + 解析后 ConvergeOutput
- report.html              · 报告页 HTML（converge 成功才有）
"""
from __future__ import annotations

import dataclasses
import json
import os
from typing import Any, Dict, List, Optional

from .personas import Persona


def _default_encode(o):
    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)
    if hasattr(o, "model_dump"):
        try:
            return o.model_dump()
        except Exception:
            pass
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)


class SessionRecorder:
    def __init__(self, results_root: str, persona: Persona, session_id: str):
        self.root = os.path.join(results_root, persona.persona_id)
        self.persona = persona
        self.session_id = session_id
        self.turns_dir = os.path.join(self.root, "turns")
        self.subject_dir = os.path.join(self.root, "subject")
        os.makedirs(self.turns_dir, exist_ok=True)
        os.makedirs(self.subject_dir, exist_ok=True)
        self.metadata: Dict[str, Any] = {
            "persona_id": persona.persona_id,
            "session_id": session_id,
            "mbti_true": persona.mbti_true,
            "style_key": persona.style_key,
            "style_name": persona.style_name,
            "opening": persona.opening,
            "life_seed": persona.life_seed,
            "turns": [],
            "converge": None,
            "outcome": "pending",
            "errors": [],
        }

    # ------- 每轮记录 -------
    def record_turn(
        self,
        round_number: int,
        subject_text: str,
        oriself_record: dict,
        oriself_visible: str,
        status: str,
        status_explicit: bool,
        phase_key: Optional[str],
    ) -> None:
        path = os.path.join(self.turns_dir, f"turn_{round_number:02d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "round": round_number,
                    "subject_text": subject_text,
                    "phase_key": phase_key,
                    "status": status,
                    "status_explicit": status_explicit,
                    "oriself_visible": oriself_visible,
                    "oriself_call": oriself_record,
                },
                f,
                ensure_ascii=False,
                indent=2,
                default=_default_encode,
            )
        self.metadata["turns"].append(
            {
                "round": round_number,
                "status": status,
                "status_explicit": status_explicit,
                "phase_key": phase_key,
                "subject_chars": len(subject_text),
                "oriself_chars": len(oriself_visible),
                "wait_seconds": oriself_record.get("wait_seconds", 0.0),
                "duration_sec": oriself_record.get("duration_sec", 0.0),
                "error": oriself_record.get("error"),
            }
        )

    def record_subject(
        self,
        round_number: int,
        subject_record: dict,
        subject_text: str,
    ) -> None:
        path = os.path.join(self.subject_dir, f"subject_{round_number:02d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "round": round_number,
                    "subject_text": subject_text,
                    "subject_call": subject_record,
                },
                f,
                ensure_ascii=False,
                indent=2,
                default=_default_encode,
            )

    # ------- converge -------
    def record_converge(
        self,
        attempt_records: List[dict],
        output: Optional[dict],
        retries: int,
        error_reasons: List[str],
    ) -> None:
        converge_path = os.path.join(self.root, "converge_call.json")
        with open(converge_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "attempts": attempt_records,
                    "retries": retries,
                    "error_reasons": error_reasons,
                    "output": output,
                },
                f,
                ensure_ascii=False,
                indent=2,
                default=_default_encode,
            )
        self.metadata["converge"] = {
            "retries": retries,
            "error_reasons": error_reasons,
            "has_output": bool(output),
            "predicted_mbti": output.get("mbti_type") if output else None,
            "card_title": (output or {}).get("card", {}).get("title") if output else None,
        }
        if output and output.get("report_html"):
            html_path = os.path.join(self.root, "report.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(output["report_html"])

    # ------- 结束 -------
    def record_outcome(self, outcome: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self.metadata["outcome"] = outcome
        if extra:
            self.metadata.update(extra)

    def log_error(self, msg: str) -> None:
        self.metadata["errors"].append(msg)

    def finalize(self) -> dict:
        """写 metadata.json + transcript.md，返回 metadata 字典。"""
        meta_path = os.path.join(self.root, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2, default=_default_encode)

        # transcript.md
        lines = [
            f"# {self.persona.persona_id}",
            "",
            f"- MBTI 真实：{self.persona.mbti_true}",
            f"- 风格：{self.persona.style_name} ({self.persona.style_key})",
            f"- Session id：{self.session_id}",
            f"- Outcome：{self.metadata.get('outcome')}",
            "",
        ]
        if self.metadata.get("converge"):
            conv = self.metadata["converge"]
            lines.append(
                f"- 报告生成：retries={conv['retries']} · predicted={conv['predicted_mbti']} · "
                f"has_output={conv['has_output']}"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

        for turn in self.metadata["turns"]:
            rn = turn["round"]
            # 从各 turn json 里读回 text
            tp = os.path.join(self.turns_dir, f"turn_{rn:02d}.json")
            if not os.path.exists(tp):
                continue
            with open(tp, "r", encoding="utf-8") as f:
                obj = json.load(f)
            lines.append(f"## R{rn} · {obj.get('phase_key')} · STATUS: {obj.get('status')}")
            lines.append("")
            lines.append("**被试者：**")
            lines.append("")
            lines.append(obj.get("subject_text", "").strip() or "_(空)_")
            lines.append("")
            lines.append("**OriSelf：**")
            lines.append("")
            lines.append(obj.get("oriself_visible", "").strip() or "_(空)_")
            lines.append("")

        if self.metadata.get("converge") and self.metadata["converge"]["has_output"]:
            lines.append("---")
            lines.append("")
            lines.append("## CONVERGE · 报告生成")
            lines.append("")
            lines.append(f"预测 MBTI：**{self.metadata['converge']['predicted_mbti']}**")
            lines.append("")
            lines.append(f"名片标题：{self.metadata['converge']['card_title']}")
            lines.append("")
            lines.append("HTML 写入：`report.html`")
            lines.append("")

        transcript_path = os.path.join(self.root, "transcript.md")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return self.metadata
