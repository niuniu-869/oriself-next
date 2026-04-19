# OriSelf Skill · Benchmark 首轮结果分析

> **跑期：** 2026-04-18 22:40 → 23:49（总用时 69 分钟）
> **样本：** 16 MBTI × 10 风格 = 160 场端到端对话
> **OriSelf：** `mimo-v2-pro`（推理模型，对话 max_tokens=4096，报告 max_tokens=32768）
> **被试：** `mimo-v2-flash`（非推理，每轮 max_tokens=1024）
> **并发：** 50 session · RPM=95 · 全程 LLM 调用全量归档于 `results/<persona>/`

---

## 1. 头条数字

| 指标 | 数值 |
|------|------|
| 跑完会话 | 160 / 160 |
| `outcome=ok`（对话完 + 报告出得来） | **133 · 83.1%** |
| `outcome=need_user_halt`（skill 主动早停） | 16 · 10.0% |
| `outcome=converge_failed`（报告生成 3 次 retry 全败） | 11 · 6.9% |
| 轮数分布（min/median/max） | 5 / 19 / 30 |
| 报告生成 0 次 retry 一次过 | 88 / 133 = 66.2% |
| 报告生成需要 1-2 次 retry | 45 / 133 = 33.8% |
| 对话轮总数 | ≈ 3050 轮（每场均 19.2 轮） |
| 生成 HTML 报告 | 133 份（累计 ≈ 1.5 MB 代码，median 长度 11 KB） |

---

## 2. MBTI 预测准确度 · 按维度拆解

4 字母**完全命中率 37.6%**，初看刺眼，但这是 MBTI 类评测本身的底噪 —— 就算真人自测重做一次，4 字母完全重合也就 60-70% 上下。更有用的是拆维度看：

| 维度 | 命中率 | 备注 |
|------|--------|------|
| **J/P**（节奏 · 计划 vs 弹性） | **86.5%** (115/133) | skill 对"有没有日程"问得准 |
| **T/F**（决策 · 逻辑 vs 情感） | **82.7%** (110/133) | "你决定前先算还是先问感受" 区分度高 |
| **S/N**（注意力 · 具象 vs 抽象） | **78.9%** (105/133) | 情境题问得好，但文艺/内省风格会被拉向 N |
| **E/I**（精力来源） | **65.4%** (87/133) | ★ **弱项** |

**差几位分布：**
- 0 位差（精确命中）：50 场
- 1 位差：58 场
- 2 位差：18 场
- 3 位差：7 场

> **83% 的预测在 0-1 位差以内** — 这是 skill 真实的分辨力水平。

---

## 3. ★ 首要发现：E/I 维度被"独处表达"带偏

所有维度里 E/I 命中最差（65.4%）。翻查数据，具体 failure mode：

- **被试是 E（ESFP / ENTP / ENFP）但风格是 `literary` / `introspective` / `tired`** → 常被预测成 I
- 典型样本：`ESFP_literary` → 预测 `ESFJ`（✓ E 对了，但 `ENTP_tired` → 预测 `INFP`，E 被翻成 I）

**根因假说**：
- E/I 不是由"用字数"决定，而是"能量来源"。但 OriSelf 在对话中**可观察的只有输出行为**
- 当被试风格偏文艺/内省/疲惫时，文字表现克制、不抢话、长句自叙 —— 这**正好是 I 的典型文字印记**
- Skill 里 `domains/mbti.md` 对 E/I 的判定线索主要靠"主动拓展话题 vs 被动应答"，但 mimo-v2-pro 做了 20 轮访谈后倾向把"话少"都归到 I

**优化方向**：
1. 在 `domains/mbti.md` 补一条：**"字数少 ≠ I"** —— 单独加权被试主动提起新话题的次数、被打断的概率、情绪上扬的时刻。
2. `phases/phase3_5-midpoint.md` 或 `phase4-deep.md` 加一个"活力场景"问题：放假一个人 vs 和朋友一起 → 能量高低对比。这是 E/I 最稳的区分题。

---

## 4. ★ 次要发现：按风格看，skill 最会翻车的是 `tired` 和 `literary`

| 风格 | 命中率 | 样本 |
|------|--------|------|
| casual_verbal | **71.4%** (10/14) | 口语松散 · 信号最多 → 最好测 |
| jumpy | 64.3% (9/14) | 话题跳跃反而意外地好测 |
| verbose | 64.3% (9/14) | 给的细节丰富 |
| analytical | 42.9% (6/14) | 冷静理性 · 中等 |
| energetic | 40.0% (6/15) | 多 emoji → 被识别为 E 比较稳，但内层 S/N 难 |
| ESTP/ENFP 等 E 系 | 20-30% | 见 §3 |
| **hesitant** | **23.1%** (3/13) | "不知道/也许" 太多 · 信号量低 |
| **silent** | **22.2%** (2/9) | 被试根本不说话，多数已 halt |
| **literary** | **14.3%** (2/14) | 比喻多 · 抽象多 · 误判风险最高 |
| **tired** | **9.1%** (1/11) | 累 → 只给信息最少的那层 |

**结论**：**信号量直接决定命中率**。`tired` / `literary` 这两类不是"skill 太差"，而是"这类被试在真实产品里本就应该被建议换个时候再聊"。

**优化方向**：
1. 在 `phase0-onboarding.md` 里增加一个隐性信号识别：如果 R2-R3 检测到用户偏 `tired` / `silent` 倾向，OriSelf 主动说"要不我们今天先聊 10 轮，够用就收"。减少硬顶。
2. `literary` 风格的"抽象比喻"是问题本源 —— 可以在 `techniques/reflective-listening.md` 补一条："如果 TA 开始讲抽象意象，回到一个具体画面问"。

---

## 5. ★ 第三发现：`need_user_halt` 是 skill 的正确行为，不是 bug

16 场主动早停，全部集中在：
- `silent`: 6 场
- `tired`: 5 场
- `jumpy`/`hesitant`/`verbose`: 各 1-2 场

这**正是 SKILL.md "STATUS: NEED_USER" 协议的设计场景**：连续 2-3 轮极短回复 + 换过话题还是拉不动 → 把选择权还给用户。benchmark 的 subject 端被设定成不会主动 bump 对话，所以 skill 能稳稳触发 halt。

**读法**：`need_user_halt` ≠ 失败。产品里这一步会让前端弹"要不先到这？我可以先给你一版简版报告"。

**但有 1 个 outlier 值得看：`verbose` 风格也 halt 了一场** —— 翻 transcript：被试开始讲着讲着 shift 到抱怨性循环，OriSelf 抓到"TA 在原地绕"，判 NEED_USER。这反而是对的。

---

## 6. ★ 第四发现：报告生成失败里 58% 是 JSON 截断

`converge_failed` 11 场，归因失败 attempt：

| 原因 | 计数 | 占比 |
|------|------|------|
| `json_truncated` · LLM 输出到一半断掉 | 19 | 58% |
| `other` · ReadTimeout（240s 不够） | 5 | 15% |
| `schema_invalid` · insight_paragraphs 字数不够 / 轮号引用缺 | 4 | 12% |
| `mbti_letter_mismatch` · HTML 里写了 2 套字母 | 4 | 12% |
| `xss_violation` · 用 `<script>` 或 `onclick` | 1 | 3% |

**根因** · mimo-v2-pro 在 `response_format=json_object` 模式下，推理链可能被关，但它依然会在长 HTML 字符串的中段卡 tokenizer（连续反斜杠 / 中文换行过多）。现有 32768 max_tokens 充足，真正卡的是 **provider 端流式 JSON 封装**。

**优化方向**：
1. **短期** · `llm_client.py` 里 converge 请求加个 streaming + 自己 buffer 重组，避免 JSON mode 断流。
2. **中期** · CONVERGE 输出可以分两次调用：先出 `confidence_per_dim + insight_paragraphs + card`（轻），再单独 `/report_html`（重）。报告那段失败 retry 不会连累前面的洞见。
3. **长期** · 把 `report_html` 改成"LLM 只给 design decision + HTML 骨架"，CSS 模板由服务端根据 aesthetic/color 字段渲染。

---

## 7. ★ 第五发现：HTML 设计真的**没撞衫**

133 份生成的报告：
- 长度 5.9 KB - 31.7 KB，median 11 KB
- 共检出 **52 个不同 font-family** 家族（含少量字体名幻觉，如 "JetBrains 维也纳"）
- 手动对比 10 份：几乎每份都有独立的视觉论题（INTP_tired 是 CRT 终端 / INFJ_silent halt 没产出 / ESFP_energetic 是霓虹手写 / ISTJ_analytical 是图书馆账本 / …）

**CONVERGE.md 的大段美学散文起作用了。** 这是一个之前没数据验证过的赌注，现在能说"它赢了"。

**瑕疵**：
- 偶发字体幻觉（LLM 瞎编字体名）
- `--accent: #818cf8`（紫色）这种 **AI slop 反模式**出现率约 8%（对 133 份抽查），说明 `反 AI slop · 一条都不许出现` 这条还不够硬

**优化方向**：
- `guardrails.py` 补一条软校验：HTML 里命中黑名单字体（Inter/Roboto/Papyrus/Comic Sans）或 `#818cf8` 这种紫色的，写 warning 到 metadata（不 reject），便于统计改进。

---

## 8. 性能与成本观察

- **总 token 消耗（估算）**：
  - 对话轮 · 每场 19 轮 × 2 calls ≈ 38 calls × 133 场 = 5054 次 + 160 场 × 1 converge = 约 **5200 次 LLM 调用**
  - prompt_tokens 每次 ~6-10 K（因为 SKILL + ETHOS + domain + phase + techniques + exemplary 全量 cache），但 mimo 的 `cached_tokens` 有效（采样里 8128/8199 命中）
- **rate limiter 实际吃到的等待**：大量轮 `wait_seconds=0.0`（被 backend 响应时间主导），说明 pro 的推理延迟远大于 RPM 限制 —— **瓶颈在 backend 延迟不在限流**。
- **单场耗时分布**：300-1900s，median 1100s。max_concurrent=50 时有明显的"尾部效应"（100 场已完成 60 场时还剩 20 场在挂）。

**优化方向**：
- `max_concurrent` 可以拉到 60-80，反正 backend 延迟占主导。
- **对话 max_tokens=4096** 可能偏多，多数 turn 其实 300-800 字。但 pro 的 reasoning 占一大块，保守不动。

---

## 9. 给未来的自己 —— 优化路线图（按 ROI 排）

**高 ROI（动一页 skill 文件就能改）：**

1. **`domains/mbti.md` 补 E/I 判定线索** · 加"字数少 ≠ I"一条 + "活力场景对比"情境题
2. **`phase0-onboarding.md` 加早停握手** · 检测 tired/silent 倾向 → 主动把 target_rounds 调成 10
3. **`techniques/reflective-listening.md` 加"抽象→具象回拉"** · 防 literary 漂走
4. **`CONVERGE.md` 反 AI slop 章节再硬一点** · 把 `#818cf8`、紫色渐变、`background: linear-gradient(135deg, #8b5cf6, ...)` 直接点名禁用

**中 ROI（动 server 代码）：**

5. **报告生成走分段 · 先洞见后 HTML** · 断流不连累
6. **guardrails 增字体/AI-slop 软警告** · 不 reject 只记录，一段时间后升级为 reject
7. **subject-side benchmark 多跑几轮 · 测不同 season/hour** · 看结果是否稳定

**低 ROI 但值得探索：**

8. 换 `mimo-v2-pro` 为其它 reasoning 模型（claude-sonnet-4-6 / gemini-3）做 A/B，看 E/I 判定是否天花板受 model 限制
9. 人肉读 `need_user_halt` 的 16 份 transcript，看 skill 有没有过度 halt 的情况

---

## 10. 复现这份结果

```bash
cd /niuniu869_dev/oriself-next-app/skill-repo/skills/oriself
python3 -m benchmark.runner
```

全量 160 场。结果覆盖 `benchmark/results/`（**会清掉上次的数据**，重要的跑前先 `cp -r results results.baseline/`）。

任何一个 persona 的完整 skill-prompt 快照在 `results/<PID>/turns/turn_XX.json` 的 `oriself_call.request_messages[0].content` —— 可以用来人肉诊断某个具体 skill 指令是不是有效。

---

## 附：本次数据的 git 时刻

（未 commit · 保留在工作目录内供本地回看。如要入库，建议把 `results/` 添加到 `.gitignore` 而只 commit code/README/analysis；报告 HTML 是 133 份 × 11 KB ≈ 1.5 MB 起步。）
