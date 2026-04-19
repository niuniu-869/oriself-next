# OriSelf skill · Benchmark 压测套件

> 16 MBTI × 10 风格 = **160 场**端到端对话，全链路完整归档。
> 两位 LLM 扮演攻守双方：
>
> - **mimo-v2-pro** 作为 OriSelf（对话主理人 + 报告生成器）
> - **mimo-v2-flash** 作为被试者（每位有自己的真实 MBTI、生活剧情和说话风格）
>
> 每场对话从 R1 被试者开口到最终 `report.html` 写盘，中间每一次 LLM 调用的
> 完整 request/response 都会落到 `results/<persona_id>/` 目录，方便未来回看与迭代。

---

## 目录结构

```
benchmark/
├── README.md               ← 你在读的这份
├── config.py               ← API key、模型名、RPM、并发、token 预算
├── personas.py             ← 160 位被试者人设生成（确定性，可复现）
├── rate_limiter.py         ← 异步令牌桶 · 保证整个 benchmark RPM ≤ 95
├── mimo_backend.py         ← 小米 OpenAI-compatible backend，挂 rate limiter，抓完整 call record
├── subject_simulator.py    ← 被试者 LLM 封装（视角反转：flash 作为 assistant 回应）
├── session_recorder.py     ← 每场对话一个目录的归档器
├── runner.py               ← 主入口：调度 160 场 + RPM 限流 + 汇总
├── logs/                   ← 运行时日志
│   ├── bench_YYYYMMDD_HHMMSS.log
│   └── stdout.log
└── results/
    ├── index.json          ← 160 场汇总（人设 + outcome + 预测 MBTI + 报告 metadata）
    ├── summary.md          ← 人类可读统计
    └── <PERSONA_ID>/       ← 例如 INTJ_literary / ENFP_jumpy / ISFJ_silent
        ├── metadata.json   ← 本场人设 + 每轮统计 + converge 结果
        ├── transcript.md   ← 人类可读的对话全文（被试 ↔ OriSelf 交替）
        ├── turns/
        │   └── turn_XX.json  ← **每轮**完整 system prompt、message history、LLM 响应、usage
        ├── subject/
        │   └── subject_XX.json ← 被试者每轮的完整 prompt + flash 回复
        ├── converge_call.json  ← 报告生成的 3 次 attempt（含 retry hint、拒绝原因、usage）
        └── report.html          ← converge 成功时的最终网页（与产品线上一致的 HTML）
```

---

## 一次跑整套的做法

```bash
# 0) 前置：确保 server/ 已被 Python 能 import（runner 会把它加进 sys.path）
#    默认 API key/base_url 写在 config.py 里，用 env 覆盖也行：
#    export MIMO_API_KEY=... MIMO_BASE_URL=...

# 1) dry-run（1 场，校验链路通）
cd /niuniu869_dev/oriself-next-app/skill-repo/skills/oriself
python3 -m benchmark.runner --limit 1

# 2) 全量（160 场 · 50 并发 · 95 RPM）
python3 -m benchmark.runner
```

跑的过程中 `logs/bench_*.log` 和 `logs/stdout.log` 会持续有每场完成的一行摘要：

```
[12/160] INFP_literary outcome=ok rounds=22 mbti=INFP elapsed=287.4s
```

跑完后：
- `results/index.json` 是机器可读的全量
- `results/summary.md` 是人类可读的总结（outcome 分布、轮数分布、MBTI 命中率按类型/按风格分桶、重试分布、错误样本）

---

## 架构决策

### 1. 直接复用生产线 server 代码

没再写一份 TurnRunner / ReportRunner / guardrails。runner.py 第一件事就是：

```python
sys.path.insert(0, parents[4]/"server")
from oriself_server.skill_runner import TurnRunner, ReportRunner, ...
from oriself_server.guardrails import verify_report_html_shape, ...
from oriself_server.skill_loader import load_skill_bundle
```

**理由**：这次压测的目的是"压这个 skill"，不是"压一个复刻版"。生产用哪套 system prompt 拼装、哪套 STATUS 解析、哪套 guardrails，benchmark 就用哪套——任何差异都会让分析结论跑偏。

### 2. 双 backend · 三种 purpose

`MimoBackend` 派生了三种实例：

| purpose   | model         | max_tokens | 用途                        |
|-----------|---------------|------------|-----------------------------|
| `turn`    | mimo-v2-pro   | 4096       | OriSelf 每轮流式回复         |
| `converge`| mimo-v2-pro   | 32768      | 报告生成（含长 HTML）        |
| `subject` | mimo-v2-flash | 1024       | 被试者每轮回复               |

pro 的 `reasoning_tokens` 会吃掉一大半 max_tokens，所以对话轮给 4096、converge 给 32k；
flash 不推理，1k 够用且便宜。

### 3. 被试者视角反转

`SubjectSimulator.respond()` 做的一件关键事：把 conversation 翻过来喂给 flash——
**OriSelf 说的话作 `user` 角色，被试者自己说的话作 `assistant` 角色**。
这样 flash 自然扮演"下一个 assistant = 被试者"。如果角色对了但 flash 偶发破戏
（跳出人设承认自己是 AI），就走 `_safe_fallback_line()` 按风格给一句人设安全话，
不 retry 也不阻塞。

### 4. RPM 限流：单一全局令牌桶

所有 LLM 调用（OriSelf 对话轮 + 报告轮 + 被试者轮）共用一个 `AsyncRateLimiter(95)`。
被试者和 OriSelf 在同一个 session 里严格交替，所以不存在"OriSelf 堵住被试者"的竞争；
但多个 session 之间 50 并发，令牌桶把整体 RPM 压到 95。

*为什么 95 不是 100？* mimo 端实际 RPM 的统计窗口可能不是 60s 精确对齐，留 5% buffer 防突发。

### 5. 错误策略：对话轮不 retry，报告轮 3 次 retry（和生产一致）

生产服务端的做法：对话轮 LLM 输出什么用户就看到什么，不满意用户自己点"重写"；
只有 converge 报告生成会 3 次 retry（schema / xss / 字母一致性）。benchmark 保持一致——
我们就是要看"直接把 skill 丢给压力"的真实分布。

失败的对话轮 / 失败的 converge 都会**如实保留在 metadata + 对应 json 里**，不掩盖。

### 6. 160 人设的确定性生成

`personas.py` 用 MD5(persona_id + salt) 选择 life_seed / opening，保证：
- 同样的 mbti+style 组合每次 run 拿到同一个人设
- 16×10 × 不同 salt 覆盖完整空间，不会出现 10 个 INTJ 都是"凌晨追 bug"

16 MBTI 类型 × 10 风格变体 = 160 位。风格变体（正交于 MBTI）：

1. `literary` 文艺诗意 · 长句比喻
2. `analytical` 冷静理性 · 短精确
3. `casual_verbal` 口语松散 · 语气词多
4. `tired` 忙碌疲惫 · 短而累
5. `introspective` 敏感内省 · 省略号多
6. `energetic` 外向热情 · emoji 感叹号
7. `jumpy` 破碎跳跃 · 话题乱跳
8. `silent` 沉默寡言 · 一两个字
9. `verbose` 话痨详述 · 长段落
10. `hesitant` 犹豫不决 · "不知道"多

这 10 种风格有意**和 MBTI 没有强绑定**——一个 INTJ 也可以是 `energetic` 风格（现实里就有外向型的 INTJ），OriSelf 的挑战就是"穿透风格看本质"。

---

## 怎么看单场数据

```bash
# 挑一场看
cd results/INFP_literary
cat metadata.json | jq '.converge, .turns[:3], .outcome'

# 读对话全文
less transcript.md

# 看 R5 服务端实际拼给 LLM 的 system prompt（含 SKILL.md + phase + techniques + exemplary 全组合）
cat turns/turn_05.json | jq '.oriself_call.request_messages[0].content' -r | less

# 看 converge 第一次 attempt 被拒的原因
cat converge_call.json | jq '.attempts[0].rejection_reasons'

# 浏览器打开最终报告
xdg-open report.html  # 或 open report.html
```

每个 `turn_XX.json` 的关键字段：

```yaml
round: 5
subject_text: "被试者这轮说的话"
phase_key: "phase2-3-exploring"      # runner 给这轮选的 phase
status: "CONTINUE"                    # LLM 自己声明的 STATUS
status_explicit: true                 # false = LLM 漏写，服务端默认 CONTINUE
oriself_visible: "剥除 STATUS 后用户看到的"
oriself_call:
  model: "mimo-v2-pro"
  request_messages:                   # ★ 完整 system + 全部历史，所见即所得
    - role: system
      content: "SKILL.md + ETHOS + domain + 本轮 phase + techniques + exemplary + Runtime State"
    - role: user ...
  request_extra:
    max_tokens: 4096
    stream: true
  response_text: "LLM 原始输出（含末行 STATUS）"
  usage: {completion_tokens, prompt_tokens, reasoning_tokens, cached_tokens}
  wait_seconds: 0.32                  # rate limiter 等了多久
  duration_sec: 7.42
  error: null
```

---

## 跑完后可以问什么问题

`results/summary.md` 会给这些：

1. **outcome 分布**：ok / truncated_no_converge / converge_failed / need_user_halt
2. **轮数分布**：min/max/median/avg —— 是不是大多 15-22 轮就收束了？有没有很多 R30 硬顶？
3. **MBTI 命中率**：
   - 整体命中率
   - 按真实类型分桶（哪些类型最容易被识错？）
   - 按风格分桶（是不是 `silent` 风格普遍识不准？）
4. **报告生成重试分布**：0/1/2/3(失败) 次成功各多少
5. **错误样本**：随机抽的 20 条失败原因

想更深挖的，直接去 `results/<persona_id>/` 看具体对话和 skill prompt 快照。

---

## 压测这个 skill 的初心

v2.4 的 skill 是**用散文当合同**的：`SKILL.md` 讲八条铁则，`CONVERGE.md` 讲
"你是 Awwwards 级设计师"。没有 Pydantic 把关，没有硬规则 retry——唯一硬拦截
是 XSS + 字母一致性。这套设计是赌"LLM 读一页大散文能稳定表现"。

这次 benchmark 就是在问三件事：

1. **赌赢了吗？** 160 个完全没见过的人设扔进来，有多少能走到 `outcome=ok`？
2. **哪些风格会让 skill 翻车？** 是 `silent` 风格？还是 `hesitant`？还是 emoji 狂魔把 pro 带偏？
3. **converge 那段大段的设计指令起作用了吗？** HTML 多样吗，还是都长得像同一个紫色泡泡？

**未来的我 / 未来的你：** 这套数据是你优化这个 skill 的起点。改 `SKILL.md` 前先跑一次 baseline，改完再跑一次，差异直接肉眼可见。

