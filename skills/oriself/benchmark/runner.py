"""
主 runner · 拉起 160 场对话。

执行模型：
1. 一个全局 `AsyncRateLimiter(RPM=95)` 管所有 LLM 调用（oriself 轮 + 被试者轮 + 报告轮）
2. `asyncio.Semaphore(MAX_CONCURRENT_SESSIONS)` 限制同时开几场对话
3. 每场对话独立跑 `run_one_session(persona)`：
   - R1: 被试者用 persona.opening 主动开口
   - R1 → R30: OriSelf 流式产出，被试者非流式回复，写 recorder
   - R6+ 看到 CONVERGE 或 R30 触顶 → 跳报告生成
4. 跑完把 160 份 metadata 汇总到 results/index.json + summary.md

错误策略：**不 retry 对话轮**。LLM 错了就记错了，保留现场用来分析，
和产品线上保持一致（服务端本来就是让用户点「重写」）。报告轮沿用 ReportRunner
内置的 3 次 retry。
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import List, Optional

_SERVER_PATH = Path(__file__).resolve().parents[4] / "server"
if str(_SERVER_PATH) not in sys.path:
    sys.path.insert(0, str(_SERVER_PATH))

from oriself_server.guardrails import (  # noqa: E402
    extract_card_title_from_html,
    parse_status_sentinel,
    resolve_mbti_or_fail,
    strip_markdown_fence,
    verify_report_html_parseable,
    verify_report_html_shape,
)
from oriself_server.llm_client import Message  # noqa: E402
from oriself_server.schemas import ConvergeOutput, MIN_CONVERGE_ROUND  # noqa: E402
from oriself_server.skill_loader import load_skill_bundle  # noqa: E402
from oriself_server.skill_runner import (  # noqa: E402
    SessionState,
    TurnRunner,
    ReportRunner,
    advance_state,
    choose_phase_key,
)

from .config import DEFAULT_CONFIG, RESULTS_DIR, LOGS_DIR  # noqa: E402
from .mimo_backend import MimoBackend  # noqa: E402
from .personas import Persona, generate_personas  # noqa: E402
from .rate_limiter import AsyncRateLimiter  # noqa: E402
from .session_recorder import SessionRecorder  # noqa: E402
from .subject_simulator import SubjectSimulator  # noqa: E402


logger = logging.getLogger("bench")


# ---------------------------------------------------------------------------
# 单场对话
# ---------------------------------------------------------------------------


async def run_one_session(
    persona: Persona,
    limiter: AsyncRateLimiter,
    semaphore: asyncio.Semaphore,
    global_stats: dict,
) -> dict:
    async with semaphore:
        session_id = uuid.uuid4().hex
        recorder = SessionRecorder(RESULTS_DIR, persona, session_id)
        t0 = time.time()

        cfg = DEFAULT_CONFIG
        turn_backend = MimoBackend(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model=cfg.model_oriself,
            rate_limiter=limiter,
            max_tokens=cfg.max_tokens_turn,
            purpose="turn",
            timeout=cfg.per_request_timeout,
        )
        converge_backend = MimoBackend(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model=cfg.model_oriself,
            rate_limiter=limiter,
            max_tokens=cfg.max_tokens_converge,
            purpose="converge",
            timeout=cfg.per_request_timeout,
        )
        subject_backend = MimoBackend(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            model=cfg.model_subject,
            rate_limiter=limiter,
            max_tokens=cfg.max_tokens_subject,
            purpose="subject",
            timeout=cfg.per_request_timeout,
        )

        bundle = load_skill_bundle()
        turn_runner = TurnRunner(turn_backend, bundle=bundle)
        subject = SubjectSimulator(subject_backend)

        session = SessionState(session_id=session_id, domain="mbti")

        # conversation history 对被试者视角：[(subject_prev, oriself_said), ...]
        subject_view_history: list[tuple[str, str]] = []

        round_n = 0
        convergence_triggered = False
        last_status = "CONTINUE"

        try:
            while session.round_count < cfg.max_rounds:
                round_n = session.round_count + 1

                # 1. 被试者发言
                if round_n == 1:
                    subject_text = persona.opening
                else:
                    subject_text = await subject.respond(
                        persona, subject_view_history, round_n
                    )
                sub_record = subject_backend.last_call.to_dict() if subject_backend.last_call else {}
                recorder.record_subject(round_n, sub_record, subject_text)

                # 2. OriSelf 流式回复
                phase_key = choose_phase_key(session, round_n)
                visible_text = ""
                status = "CONTINUE"
                status_explicit = False
                try:
                    async for kind, payload in turn_runner.stream_turn(session, subject_text):
                        if kind == "token":
                            continue  # 我们只在 last_call 里拿完整 buffer
                        if kind == "status":
                            status = payload
                        elif kind == "visible":
                            visible_text = payload
                        elif kind == "error":
                            recorder.log_error(f"R{round_n} stream error: {payload}")
                            break
                except Exception as exc:
                    recorder.log_error(f"R{round_n} exception: {exc!r}")
                    # 中断本场对话，尝试跑 converge 兜底
                    break

                # parse from raw buffer（真实 explicit 状态）
                turn_record = turn_backend.last_call.to_dict() if turn_backend.last_call else {}
                raw_buffer = turn_record.get("response_text", "")
                parsed = parse_status_sentinel(raw_buffer)
                # 用真实解析替代 streamer 给的 payload（保证 status_explicit 正确）
                visible_text = parsed.visible_text
                status = parsed.status
                status_explicit = parsed.status_explicit

                recorder.record_turn(
                    round_number=round_n,
                    subject_text=subject_text,
                    oriself_record=turn_record,
                    oriself_visible=visible_text,
                    status=status,
                    status_explicit=status_explicit,
                    phase_key=phase_key,
                )
                session = advance_state(session, subject_text, visible_text, status)
                subject_view_history.append((subject_text, visible_text))
                last_status = status

                # 3. 决定要不要退出
                if status == "CONVERGE" and session.round_count >= MIN_CONVERGE_ROUND:
                    convergence_triggered = True
                    break
                if status == "NEED_USER":
                    # 让被试者继续一轮；如果已经连续两次都 NEED_USER 则放弃
                    if sum(
                        1 for t in session.turns if t.status == "NEED_USER"
                    ) >= 2:
                        break
                    # 否则 loop 会继续

            # 如果 R30 硬顶 → 强制 converge
            if not convergence_triggered and session.round_count >= cfg.max_rounds:
                convergence_triggered = True
        except Exception as exc:
            recorder.log_error(f"session fatal: {exc!r}")

        # 4. converge 阶段
        attempt_records: list[dict] = []
        converge_output_dict: Optional[dict] = None
        retries = 0
        errors: list[str] = []
        if convergence_triggered and session.round_count >= MIN_CONVERGE_ROUND:
            report_runner = ReportRunner(converge_backend, bundle=bundle)
            # ReportRunner 内部会 retry；但它每 attempt 覆盖 last_call。
            # 我们用 hook：手工循环一次性获取每次 attempt 的 call log
            try:
                attempt_records, converge_output_dict, retries, errors = await _run_converge_with_capture(
                    report_runner, converge_backend, session
                )
            except Exception as exc:
                errors = [f"converge exception: {exc!r}"]

        recorder.record_converge(attempt_records, converge_output_dict, retries, errors)

        # 5. 收尾
        elapsed = time.time() - t0
        outcome = _compute_outcome(
            convergence_triggered,
            converge_output_dict,
            session.round_count,
            last_status,
        )
        recorder.record_outcome(
            outcome,
            extra={
                "round_count": session.round_count,
                "elapsed_sec": round(elapsed, 2),
            },
        )
        meta = recorder.finalize()
        global_stats["done"] = global_stats.get("done", 0) + 1
        logger.info(
            "[%d/%d] %s outcome=%s rounds=%d mbti=%s elapsed=%.1fs",
            global_stats["done"],
            global_stats["total"],
            persona.persona_id,
            outcome,
            session.round_count,
            meta.get("converge", {}).get("predicted_mbti") if meta.get("converge") else None,
            elapsed,
        )
        return meta


async def _run_converge_with_capture(
    report_runner: ReportRunner,
    converge_backend: MimoBackend,
    session: SessionState,
):
    """像 ReportRunner.compose 那样跑 3 次尝试，但每次都抓 backend.last_call 存进 attempt_records。"""
    from oriself_server.schemas import REPORT_MAX_RETRIES

    attempt_records: list[dict] = []
    last_reasons: list[str] = []
    output_dict: Optional[dict] = None
    retries = REPORT_MAX_RETRIES

    for attempt in range(REPORT_MAX_RETRIES):
        hint = "\n".join(last_reasons[:5]) if attempt > 0 else None
        messages = report_runner._build_converge_messages(session, retry_hint=hint)
        call_err: Optional[str] = None
        raw_text: Optional[str] = None
        try:
            raw_text = await converge_backend.complete_text(messages)
        except Exception as exc:
            call_err = f"LLM backend error: {exc}"
            last_reasons = [call_err]

        attempt_record = converge_backend.last_call.to_dict() if converge_backend.last_call else {}
        attempt_record["attempt_index"] = attempt
        attempt_record["hint"] = hint
        attempt_record["rejection_reasons"] = []
        attempt_records.append(attempt_record)

        if call_err:
            attempt_record["rejection_reasons"] = [call_err]
            continue

        # v2.5.2 · LLM 直吐 HTML，不再是 JSON
        html = strip_markdown_fence(raw_text or "").strip()

        shape = verify_report_html_shape(html)
        if not shape.passed:
            last_reasons = shape.reasons
            attempt_record["rejection_reasons"] = last_reasons
            continue

        parseable = verify_report_html_parseable(html)
        if not parseable.passed:
            last_reasons = parseable.reasons
            attempt_record["rejection_reasons"] = last_reasons
            continue

        mbti_type, mbti_result = resolve_mbti_or_fail(html)
        if not mbti_result.passed or mbti_type is None:
            last_reasons = mbti_result.reasons
            attempt_record["rejection_reasons"] = last_reasons
            continue

        card_title = extract_card_title_from_html(html)

        try:
            output = ConvergeOutput(
                mbti_type=mbti_type,
                card_title=card_title,
                report_html=html,
            )
        except Exception as exc:
            last_reasons = [f"ConvergeOutput validate: {exc}"]
            attempt_record["rejection_reasons"] = last_reasons
            continue

        output_dict = output.model_dump()
        attempt_record["rejection_reasons"] = []
        retries = attempt
        return attempt_records, output_dict, retries, []

    return attempt_records, None, REPORT_MAX_RETRIES, last_reasons


def _compute_outcome(convergence_triggered, converge_output, round_count, last_status) -> str:
    if converge_output:
        return "ok"
    if not convergence_triggered:
        if last_status == "NEED_USER":
            return "need_user_halt"
        return "truncated_no_converge"
    return "converge_failed"


# ---------------------------------------------------------------------------
# 全局调度
# ---------------------------------------------------------------------------


async def main_async(
    limit_personas: Optional[int] = None,
    styles_per_mbti: Optional[int] = None,
) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    log_file = os.path.join(
        LOGS_DIR,
        f"bench_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s · %(message)s")
    )
    logging.basicConfig(level=logging.INFO, handlers=[file_handler])
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s · %(message)s"))
    logger.addHandler(console)
    logger.setLevel(logging.INFO)

    cfg = DEFAULT_CONFIG
    personas = generate_personas(styles_per_mbti=styles_per_mbti)
    if limit_personas:
        personas = personas[:limit_personas]

    logger.info("=== benchmark start ===")
    logger.info("cfg=%s", cfg.as_dict())
    logger.info("personas=%d results_dir=%s", len(personas), RESULTS_DIR)

    limiter = AsyncRateLimiter(cfg.rpm_cap)
    semaphore = asyncio.Semaphore(cfg.max_concurrent)
    global_stats = {"done": 0, "total": len(personas)}

    tasks = [
        asyncio.create_task(
            run_one_session(p, limiter, semaphore, global_stats), name=p.persona_id
        )
        for p in personas
    ]
    all_meta: list[dict] = []
    for fut in asyncio.as_completed(tasks):
        try:
            meta = await fut
        except Exception as exc:
            logger.exception("a session task crashed: %s", exc)
            continue
        all_meta.append(meta)

    # 汇总
    index = {
        "cfg": cfg.as_dict(),
        "started_personas": len(personas),
        "completed": len(all_meta),
        "timestamp": _dt.datetime.now().isoformat(),
        "sessions": sorted(all_meta, key=lambda m: m["persona_id"]),
    }
    with open(os.path.join(RESULTS_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    _write_summary(index)
    logger.info("=== benchmark done ===")


def _write_summary(index: dict) -> None:
    sessions = index["sessions"]
    if not sessions:
        return
    outcome_counter: dict[str, int] = {}
    mbti_hits = 0
    mbti_total = 0
    rounds_dist: list[int] = []
    retry_dist: list[int] = []
    by_type_hit: dict[str, list[bool]] = {}
    by_style_hit: dict[str, list[bool]] = {}
    errors_bucket: list[str] = []

    for s in sessions:
        outcome_counter[s["outcome"]] = outcome_counter.get(s["outcome"], 0) + 1
        rounds_dist.append(s.get("round_count", 0))
        conv = s.get("converge") or {}
        if conv and conv.get("predicted_mbti"):
            mbti_total += 1
            predicted = conv["predicted_mbti"]
            truth = s["mbti_true"]
            hit = predicted == truth
            if hit:
                mbti_hits += 1
            by_type_hit.setdefault(truth, []).append(hit)
            by_style_hit.setdefault(s["style_key"], []).append(hit)
            retry_dist.append(conv.get("retries", 0))
        if s.get("errors"):
            errors_bucket.extend(s["errors"][:3])

    def _pct(hits: list[bool]) -> str:
        if not hits:
            return "n/a"
        rate = sum(1 for h in hits if h) / len(hits)
        return f"{rate*100:.1f}% ({sum(1 for h in hits if h)}/{len(hits)})"

    lines = [
        "# Benchmark Summary",
        "",
        f"- 跑完：{index['completed']}/{index['started_personas']}",
        f"- 开始时间：{index['timestamp']}",
        f"- 模型：OriSelf={index['cfg']['model_oriself']} · Subject={index['cfg']['model_subject']}",
        "",
        "## Outcome 分布",
        "",
    ]
    for k, v in sorted(outcome_counter.items(), key=lambda x: -x[1]):
        lines.append(f"- `{k}`：{v}")
    lines.append("")

    if rounds_dist:
        rounds_dist.sort()
        lines.append("## 轮数分布")
        lines.append("")
        lines.append(
            f"- min={rounds_dist[0]} · max={rounds_dist[-1]} · "
            f"median={rounds_dist[len(rounds_dist)//2]} · avg={sum(rounds_dist)/len(rounds_dist):.1f}"
        )
        lines.append("")

    lines.append("## MBTI 命中")
    lines.append("")
    if mbti_total:
        lines.append(f"- 整体：{_pct([s['converge']['predicted_mbti']==s['mbti_true'] for s in sessions if s.get('converge') and s['converge'].get('predicted_mbti')])}")
    lines.append("")
    lines.append("### 按人格类型")
    lines.append("")
    for t in sorted(by_type_hit.keys()):
        lines.append(f"- {t}: {_pct(by_type_hit[t])}")
    lines.append("")
    lines.append("### 按风格")
    lines.append("")
    for sk in sorted(by_style_hit.keys()):
        lines.append(f"- {sk}: {_pct(by_style_hit[sk])}")
    lines.append("")

    if retry_dist:
        lines.append("## 报告生成重试")
        lines.append("")
        lines.append(
            f"- 0 次成功：{sum(1 for r in retry_dist if r==0)} · "
            f"1 次：{sum(1 for r in retry_dist if r==1)} · "
            f"2 次：{sum(1 for r in retry_dist if r==2)} · "
            f"3 次（失败）：{index['completed'] - len(retry_dist)}"
        )
        lines.append("")

    if errors_bucket:
        lines.append("## 错误样本（截取前 20）")
        lines.append("")
        for e in errors_bucket[:20]:
            lines.append(f"- {e}")
        lines.append("")

    with open(os.path.join(RESULTS_DIR, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 位被试（调试用）")
    parser.add_argument(
        "--styles-per-mbti",
        type=int,
        default=None,
        help="每个 MBTI 取前 N 种风格。默认 30（全量 480）；10 = 均衡 16×10",
    )
    args = parser.parse_args()
    asyncio.run(
        main_async(
            limit_personas=args.limit,
            styles_per_mbti=args.styles_per_mbti,
        )
    )
