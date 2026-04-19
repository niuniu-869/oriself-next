# v2.5.0 Benchmark Findings

> **What**：v2.5.0 是对 skill 架构的非功能重构——从 "server 一次性硬塞 42KB 整个目录" 改为 "按 frontmatter driven progressive disclosure，每轮只装需要的片段"。
>
> **Run**：2026-04-19 · 16 MBTI × 10 风格 = **160 场均衡 benchmark** · mimo-v2-pro / flash · RPM=100 · concurrency=100
>
> **Baseline**：v2.4.2 的 480 场全量里挑 **同 160 个 persona_id** 做子集对比（而不是拿全 480 均值比）。

---

## 三句话结论

1. **整体没退化、轻微改进**：`ok` 率 +5.7pt（76→82%），4 字母命中率 +2.6pt（40→43%），median 轮数一致。Layer 2a 的 progressive disclosure **没把对话质量搞坏**，每轮 system prompt 从 ~42KB 压到 ~20-35KB 的成本是零。
2. **F 型普遍提升，T 型微降**：INFP **+30pt**、ISFP **+60pt**、INFJ +19pt；另一边 ISTJ **-27pt**、ESTP -17pt、ENTP -11pt。猜测与 `phase-deep` 只装 `contradiction-probing + situational-questions`（不带 `reflective-listening`）有关——T 型可能少了一个熟悉工具。
3. **两个老顽疾没动**：ENTJ **0/8 (0%)**、literary 风格 **1/14 (7%)**——v2.4.3 原本就想修，v2.5.0 是架构重构，本就没 focus 这里，结果和 v2.4.2 完全一致。下一版 (v2.5.1 或 v2.6.0) 再回头。

---

## Outcome 分布对比

| Outcome | v2.5.0 (N=160) | v2.4.2 subset (N=160) | Δ |
|---|---|---|---|
| `ok` | 131 (**81.9%**) | 122 (76.2%) | **+5.7pt** 🟢 |
| `need_user_halt` | 16 (10.0%) | 24 (15.0%) | -5.0pt 🟢 |
| `converge_failed` | 13 (8.1%) | 14 (8.8%) | -0.7pt |
| `truncated_no_converge` | 0 | 0 | 0 |

`need_user_halt` 下降最值得注意：v2.5.0 的 LLM 更少在 R11 前后声明"卡住了"。可能和 SKILL.md body 里 STATUS 协议说明更清晰、以及 Runtime State 更简短有关。

---

## 整体命中率

| 指标 | v2.5.0 | v2.4.2 subset | Δ |
|---|---|---|---|
| 4 字母全对 | **56/131 (42.7%)** | 49/122 (40.2%) | **+2.6pt** |
| median 轮数 | 19 | 19 | 0 |
| avg 轮数 | 18.2 | 18.3 | -0.1 |

---

## 按 MBTI 类型命中（v2.5.0 vs v2.4.2 subset）

| Type | v2.5.0 | v2.4.2 | Δ |
|---|---|---|---|
| ENFJ | 1/8 (12.5%) | 0/6 (0.0%) | +12.5 |
| ENFP | 3/6 (50.0%) | 4/8 (50.0%) | 0 |
| **ENTJ** | **0/8 (0.0%)** | **0/6 (0.0%)** | **0** · 老顽疾 |
| ENTP | 2/9 (22.2%) | 3/9 (33.3%) | -11.1 |
| ESFJ | 2/5 (40.0%) | 3/8 (37.5%) | +2.5 |
| ESFP | 4/8 (50.0%) | 2/5 (40.0%) | +10.0 |
| ESTJ | 2/8 (25.0%) | 2/6 (33.3%) | -8.3 |
| ESTP | 4/10 (40.0%) | 4/7 (57.1%) | -17.1 |
| INFJ | 4/9 (44.4%) | 2/8 (25.0%) | +19.4 🟢 |
| **INFP** | **7/8 (87.5%)** | 4/7 (57.1%) | **+30.4** 🟢 |
| INTJ | 3/9 (33.3%) | 4/9 (44.4%) | -11.1 |
| INTP | 6/10 (60.0%) | 6/8 (75.0%) | -15.0 |
| ISFJ | 4/9 (44.4%) | 4/9 (44.4%) | 0 |
| **ISFP** | **5/7 (71.4%)** | 1/9 (11.1%) | **+60.3** 🟢 |
| **ISTJ** | **2/7 (28.6%)** | 5/9 (55.6%) | **-27.0** 🔴 |
| ISTP | 7/10 (70.0%) | 5/8 (62.5%) | +7.5 |

**模式**：16 型里 F 类（INFP/ISFP/INFJ/ENFJ/ESFP）5 个涨、1 个平；T 类（ISTJ/ESTP/ENTP/INTJ/INTP/ESTJ）6 个降、ISTP 和 ENTJ 例外。

---

## 按风格命中

| Style | v2.5.0 | v2.4.2 | Δ |
|---|---|---|---|
| casual_verbal | 12/14 (85.7%) | 10/15 (66.7%) | **+19.0** 🟢 |
| **silent** | 4/6 (66.7%) | 1/2 (50.0%) | +16.7 · 但 N 小 |
| hesitant | 4/12 (33.3%) | 2/10 (20.0%) | +13.3 |
| jumpy | 7/12 (58.3%) | 6/13 (46.2%) | +12.2 |
| verbose | 11/16 (68.8%) | 10/15 (66.7%) | +2.1 |
| energetic | 10/16 (62.5%) | 8/13 (61.5%) | +1.0 |
| **literary** | **1/14 (7.1%)** | 1/14 (7.1%) | **0** · 老顽疾 |
| tired | 3/12 (25.0%) | 3/10 (30.0%) | -5.0 |
| introspective | 2/16 (12.5%) | 3/16 (18.8%) | -6.2 |
| **analytical** | **2/13 (15.4%)** | 5/14 (35.7%) | **-20.3** 🔴 |

---

## 关键退化（需要盯）

### 🔴 ISTJ -27pt
v2.5.0 ISTJ 2/7 = 28.6% vs v2.4.2 5/9 = 55.6%。ISTJ 本来应该是 skill 最稳的类型之一（具体、有纪律、乐于给细节）。需要抽样看几份具体对话：

```
results/ISTJ_*/transcript.md
```

可能原因：
- phase-deep 的 needs 删掉了 `reflective-listening`，ISTJ 的 J 特征可能需要 LLM 更多"总结你刚说的"来反馈
- 或仅仅是 N=7 的小样本抖动（v2.4.2 N=9 也不大）

### 🔴 analytical 风格 -20pt
v2.5.0 2/13 = 15.4% vs v2.4.2 5/14 = 35.7%。`analytical` 风格的人说话短而精确，可能 v2.5.0 更轻的 exemplary（仅 R1-R3）让 LLM 没见够"短句怎么追问"。

### ⚪ ENTJ 0% · 老顽疾
`findings_v1.md` 已经记录过"思考型被试的 E 信号被持续深挖的认知层吃掉"。v2.4.3 想修这个，v2.5.0 完全没碰。下版本专项修。

### ⚪ literary 7% · 老顽疾
SKILL.md 里"不做诗人"铁则在，但 LLM 仍然会被 literary 用户带偏。同上，专项修。

---

## 关键改进（值得复用）

### 🟢 INFP +30pt / ISFP +60pt / INFJ +19pt
F 型大幅提升。猜测触发机制：
- v2.5.0 的 `phase-exploring.needs = [reflective-listening, situational-questions]` 刚好命中 F 型（情绪具象化）
- 前几轮的 exemplary-session 依然在 prompt 里，R1-R3 给 LLM 找到柔软语气
- 删掉固定塞的 contradiction-probing 后，F 型前半场少被"温柔挑刺"

这是**意外的正向收益**。下次要不要回装 reflective-listening 到 phase-deep，先看 T 型退化的真实样本。

### 🟢 `need_user_halt` -5pt
v2.5.0 的 LLM 更少卡住。这个是架构质量的直接信号。

### 🟢 progressive disclosure 生效
按 log 里 `[skill-compose] system_bytes=N` 统计：R1 ~33KB、R12 phase-deep ~35KB、R18 phase-soft-closing ~26KB。对比 v2.4.x 每轮硬塞 42KB，节省 15-40%。Gemini flash 成本 / 延迟有直接收益。

---

## 下一步建议

### 立即可做（不改架构）

1. **抽样看 ISTJ 退化**：读 5 份 ISTJ_* transcript，对比 v2.4.2 和 v2.5.0 的具体对话差异，找出是否确实 `reflective-listening` 缺失导致
2. **抽样看 analytical 退化**：同上
3. 如果 1/2 证实猜想，在 `phase-deep.needs` 加回 `reflective-listening`，再 16×10 跑一遍（30 分钟重测一个假设）

### 短期要做（v2.5.1 补丁）

4. **ENTJ 专项补丁**：这是跨 v2.4.2→v2.4.3→v2.5.0 三版本的老顽疾。需要 skill 层面而非架构层面干预：
   - 在 `phase-exploring.md` 里加一段"思考型 E 信号提示"（决策速度、主导话题倾向、对环境主动塑形）
   - 可能 phase-deep 要加 situational socialization pivot（类似 v2.4.3 试过的）

5. **literary 专项**：仍然 7%。SKILL.md 的"不做诗人"铁则可能不够硬。需要在 phase-exploring 里加"literary 用户识别 + 回拉具体画面"的操作指南。

### 中期（Phase D · tool-use）

6. **按计划推进 Phase D**：v2.5.0 的 progressive disclosure 已经是 static-compose 版的进化极限。要真的"LLM 自己决定读什么"，必须 tool-use loop。Gemini flash 的 function calling 质量是未知。
7. Phase D 先写最小 POC（server `ORISELF_TOOL_USE=on` feature flag），跑 16×10 benchmark 看延迟 + 质量

### 可选

8. `results.v2.5.0_partial111/` 里的 111 场 T 型偏向数据可以抛弃（不均衡，无用）
9. 保留 `results.v2.4.3/` (211 场不完整) 也可以清掉——baseline 现在用 `results.v242`

---

## 相关文件

- 本次跑的全量：`benchmark/results/`（160 个 persona 目录 + index.json + summary.md）
- v2.4.2 baseline：`benchmark/results.v242/`（480 场完整）
- 前一次 v2.5.0 不均衡跑：`benchmark/results.v2.5.0_partial111/`（可删）
- 过往 findings：`benchmark/findings_v1.md`（v2.4.3 补丁分析）、`benchmark/analysis.md`

---

## Run 元数据

- `started`: 2026-04-19 13:09
- `finished`: 2026-04-19 14:11（62 分钟 wall-clock）
- `config`:
  - model_oriself: mimo-v2-pro
  - model_subject: mimo-v2-flash
  - RPM: 100
  - concurrency: 100
  - max_rounds: 30
  - min_converge: 6
- `skill_version`: 2.5.0 (`refactor/v2.5.0-frontmatter` 分支)
- `server branch`: `feat/skill-frontmatter-v2.5.0`
- 每轮 system prompt 字节数 log：`server/logs/` (启用了 `[skill-compose]` INFO log)
