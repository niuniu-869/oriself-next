# OriSelf Benchmark v1 · 深挖发现与修复方向

> 回归 `SKILL.md` / `CONVERGE.md` / `domains/mbti.md` / `phases/*.md` 定位 root cause。
> 本文专做两件事：
> 1. **Converge 的 `json_truncated` 其实不是 truncated** —— 是 LLM 在 JSON 字符串值里写了未转义的半角 `"`
> 2. **tired / literary 命中率极低** —— 不是被试信号不足，是 skill 编排把"话量 / 比喻"当成了维度判定锚点

---

## 一、Converge 失败 · 真正的根因 (一票分类)

对 60 次 JSON 解析失败的 attempt 做 `finish_reason` + 错误类型分类：

| 类别 | 次数 | finish_reason=length | 实际根因 |
|------|------|---------------------|-----------|
| A · `insight_paragraphs[*].body` 里**未转义半角 `"`** | **35** | 0 | **★ 最主要 · skill 编排导致的 LLM 习惯** |
| F · 其它 JSON 结构错（`\"theme\": \\"...\\"` 外层引号漏了等） | 10 | 0 | LLM 自己混淆转义层级 |
| C · `report_html` 字符串 LLM 没给闭合引号（看起来像"被截断"） | 7 | 0 | 实际是 LLM 主动 stop，不是 token 耗尽 |
| B · CSS 里 `\left` `\dossier` 这种 invalid escape | 4 | 0 | LLM 对 CSS 特性过度转义 |
| E · 输出被包在 `<role>` `<content>` `<parameter>` 等 XML 标签里 | 3 | 0 | LLM 把 Claude/Cursor 的 tool use 格式带进来了 |
| D · 末尾漏了 `<｜end▁of▁thinking｜>` 进 JSON | 1 | 0 | reasoning 模型边界泄漏 |

**注意：零场 `finish_reason=length`。之前 analysis.md v1 说的"JSON 截断 58%"是误读；实际是"未转义半角引号"58%。**

### A 类样本（真实 LLM 输出，JSON parse 崩在红字位置）

```
"body": "你在厨房准备茶点的时候是充实的……你对"在场"的定义，是让别人舒服……"
                                             ^^
                                             未转义 " 导致 JSON 字符串提前关闭
```

```
"body": "你说'理清对所有人的影响'，这句话泄露了你的核心 ……"
                                                     （单引号 OK）
但另一处：
"theme": "你是一个"氛围架构师"",
                   ^^^     ^^^
                   两个半角 " 嵌套，彻底崩
```

**为什么 LLM 频繁犯错？Skill 文档自己在示范。**

翻 `SKILL.md` §43、`CONVERGE.md` §46-49、`phases/*.md`、`techniques/reflective-listening.md` —— 到处都是用半角 `"`/`"` 给原话/术语打强调的例句：

```md
- TA 说"挺累的"。不要回"我听见你说累……"
- 你给我的第一印象是一个脑子里永远在跑着"新连接点"的人
- 把 CSS 代码从 0 写到最后
```

LLM 读过上百行这种示范，落到 `insight_paragraphs[*].body` 里照抄**样式上的半角引号**，但它处在 JSON 字符串值里。

### CONVERGE.md §244-247 的"输出格式提示"为什么没救住

```md
整个响应就是一个 JSON object，以 `{` 开始、`}` 结束，全程无额外文字、无 markdown fence。
`report_html` 字段是一段很长的字符串，里面的双引号、换行、反斜杠要正确转义（JSON 标准转义）。
```

**致命漏洞**：
1. 只点名 `report_html` 要转义，**`insight_paragraphs[*].body` / `card.title` / `card.subtitle` / `pull_quotes[*].text` 都是字符串却完全没提**
2. 没给"引用原话时应该用什么符号"的正面范例
3. 整个 CONVERGE.md 自己的例子里也在用半角 `"`，LLM 把"强调"等同于半角引号

### 修复 patch · CONVERGE.md

在 `## 输出格式提示` 之前插一节：

```md
## ★ JSON 字符串值里的引号规则（违反 = 直接 retry）

整个响应是**一个 JSON 对象**。`insight_paragraphs[*].body`、`insight_paragraphs[*].theme`、
`card.title`、`card.subtitle`、`pull_quotes[*].text`、`report_html` **每一个都是 JSON 字符串值**。
字符串值里出现半角双引号 `"` 就会提前关闭字符串，整个响应会被拒。

**引用被试原话 / 给一个词打强调时，用下面任一种 —— 不要用半角双引号：**

1. 中文全角书名号 / 引号：`「」`、`『』`、`"…"`（U+201C / U+201D）
2. 破折号包裹：`——爱——`
3. 斜杠或方括号：`[爱]` / `/爱/`
4. 如果一定要用半角双引号表达语义，就用反斜杠转义 `\"`

**反例（会导致整个响应被 retry）**：
```json
{ "body": "TA 说'我还好'的时候，其实是'我不想说'。" }   ← 单引号 OK
{ "body": "你对"在场"的定义是让别人舒服。" }         ← ✗ 崩
{ "theme": "一个"氛围架构师"" }                      ← ✗ 崩
```

**正例**：
```json
{ "body": "你对「在场」的定义是让别人舒服。" }
{ "body": "你说——我在乎的不是被看见——这句话……" }
{ "theme": "一个「氛围架构师」" }
```

### report_html 另一条（和上面独立）

`report_html` 是**嵌在 JSON 字符串里的 HTML**。所以 HTML 里每个半角 `"`（属性值）必须写成 `\"`，每个 `\n` 必须写成 `\\n`，CSS 里的反斜杠 `\` 要写成 `\\`。

CSS 里几乎没有以 `\字母` 开头的合法写法。如果你写了 `\\left` `\\dossier` `\\s: asdf` 这种，99% 是 bug —— 删掉它们。
```

### 修复 patch · SKILL.md 和 phase 文件

把所有教学示例里的半角 `"xxx"` 全部换成：
- 中文全角 `"xxx"`
- 或破折号 `——xxx——`

这是 tainted training data：LLM 读过 skill 文档后会把半角引号当成"正确的强调风格"。

### 附带修：ISTJ_casual_verbal 有一场 LLM 直接把 `<script>` 写进 HTML

XSS guardrail 挡住了，但说明 CONVERGE.md 的 `## 安全铁则` 三条还不够显眼——它藏在 §60-64 的一个副段里。应该前置到开头，并加一句：

> 违反任何一条 = 无论 HTML 多好都会被直接 retry。这三条没有例外。

---

## 二、tired / literary 命中率极低 · 这是 skill 编排问题

### 数据对照

| 风格 | 场次 | 命中数 | 关键偏移 |
|------|------|--------|----------|
| tired | 11 | 1 | **8 个 E 类型全部 → I**（ENFJ→ISFJ, ENFP→ISFP, ENTJ→ISTP, ENTP→INFP, ESFJ→ISFJ, ESFP→ISFP, ESTJ→ISTJ, ESTP→ISTP） |
| literary | 14 | 2 | **13 场 E 翻 I，多数 S 翻 N** |

### tired 的根因 · domains/mbti.md E/I 判定太依赖"话量"

读 `domains/mbti.md` §13-16：

```md
### E / I · 能量朝向
- **E**：与人共处后 TA 感到被充电；独处一天后有点闷
- **I**：社交后需要独处恢复；一天不说话也 OK
```

定义没问题。但 §83-92 的"简易映射"是这么写的：

```md
| "回家路上很累 / 想一个人待会" | I |
| "越热闹越来劲 / 回家还在兴奋" | E |
```

**tired 被试的回复平均 10 字以内**，根本给不出这种完整短句。skill 没有"能量信号"作为锚点时，默认从**TA 在对话框里的话量**推断 —— 而话量少的 tired 被试都被归 I。

这个偏移在 phase 文件里被放大：

- `phase1-warmup.md` §15 指示："TA 带情绪词（累 / 难过 / 撑不住 / 迷茫），第一件事是靠近感受"
- LLM 按指示共情"累"，**越共情越加深 I 印象** —— 没人在共情场景里还会 bump 到"你在热闹里反而有劲吗"的 E 验证题

### literary 的根因 · S/N 判定把"用比喻"当 N 信号

`domains/mbti.md` §18-19：

```md
### S / N · 信息摄取
- **S**：注意具体细节、过往经验、当下的画面
- **N**：跳到模式、意义、未来可能性
```

这个定义**不等于**"用不用比喻"。但 literary 被试特征是"爱用比喻和意象"（见 `personas.py` §141）——讲"下雨像一种温柔的挣扎"时，skill 容易读成 N（"跳到意义"）。**但那是修辞，不是注意力偏向**。

一个 ISFP-Se 完全可以用大量比喻描述眼前的光；一个 ESFJ 也可以文艺。

### literary 的二次偏移 · E/I 全翻 I

14 场 literary 里 13 场 E→I。根因：

- literary 被试给的是**独处场景的内省**（"坐窗边""看雨""想一个词"）
- `domains/mbti.md` §83-92 表里这些都被归 I
- 但 literary 只是**写作风格**，一个 E 的人也可以写文艺的独处画面 —— 你没给 E 留活路

### 修复 patch · domains/mbti.md 顶部加"判定防陷阱"

```md
## ★ 判定防陷阱（开写 confidence_per_dim 前默念）

### E/I 不能用"TA 在这个对话框里话多话少"判

**这是在屏幕前打字的场景 —— E 的天线当下收不到信号**。TA 回得短是因为累了；
回得长是因为文艺 —— 都和 E/I 无关。

判 E/I **只能用 TA 讲的生活场景里的能量变化**：
- "聚会完回家还在兴奋" → E
- "一个人待一天也挺舒服" → I
- **TA 在对话里的话量 / 用不用比喻 / 冷静还是热烈 → 与 E/I 无关**

如果到 R10 你都没听到一个"能量变化"的具体场景，下一轮用情境题 2/4/5/6 问一次。
**没有这个信号就别判 E/I，置信度放 0.5**，比瞎猜更诚实。

### S/N 不能用"用不用比喻 / 讲不讲意义"判

- 文艺腔 ≠ N。那是表达风格。
- 讲意义 ≠ N。一个 S 人也可以谈这件事对自己的意义。
- 讲细节 ≠ S。一个 N 人也可以精确描述某个场景。

S/N 的硬信号：
- **S 要找**：TA 对**具体过往 / 物件 / 当下画面**的复现密度
- **N 要找**：TA 对**模式 / 联系 / 未来可能性**的自发联想

### T/F 不能用"TA 现在流不流泪"判

共情对话里 TA 的情绪表达多 → 不是 F 的证据。T 的人也会在被听到时放情绪。
判 T/F 靠 **TA 的具体决策故事**（题池 §51-58）。

### J/P 不能用"TA 计划了本次聊天多久"判

target_rounds 用户选的是 chat preference，不是人格 J/P。

### 没有信号时要承认没有，而不是倒向默认

四个维度里每一个，你下笔写 `confidence_per_dim` 之前必须能心里说出 **1-2 个具体场景原话** 作为依据。如果只有"感觉"，score 必须 ≤ 0.55。不要凑一个"看起来合理的四字母"。
```

### 修复 patch · phase2-3-exploring.md 增加维度清账

```md
## 维度清账（R4 / R8 / R12 各自问一次）

问自己：E/I / S/N / T/F / J/P 四个维度，哪个维度我听到过一个**具体场景**？

- 有 1 个以上 → 下一轮自由追其它话题
- 0 个 → 下一轮必须挑一道该维度的情境题（见 `domains/mbti.md` 题池）
- **E/I 的情境题必须是场景型**（题 2/4/5/6），不能用"你觉得自己外向吗"

这一步是你避免交卷时"四维都只靠感觉瞎猜"的关键。
```

### 修复 patch · phase1-warmup.md 加 tired 路径

在 §13-19 的"用户带情绪怎么办"之后加：

```md
## TA 如果从第一轮就低能量（"累""懒得""就这样"）

不要把共情拉长。这类被试再共情 3 轮还是这些词。

- R2 正常共情一次（"累啊……是那种晚上回家什么都不想做的累？"）
- R3 切到一个**轻松的生活画面题**，给 TA 一个可以短回答但又带画面的接口
  - 好："今天吃啥了？"
  - 好："这会儿窗外亮着还是暗着？"
  - 坏："那最近心里还有什么想说的"（太开放，累的人接不住）

如果 R3-R5 TA 还是 5-10 字以内回复——
不要再追 E/I（你没信号），切到 J/P 或 T/F 的**是非题**，让 TA 只用很小成本就能给信号：
- "你电脑桌面现在是乱的还是整齐的？"（J/P）
- "最近一次朋友来问你建议，你是会先分析还是先听 TA 说完？"（T/F）
```

---

## 三、这两组修复的 ROI

| patch | 预估修复率 |
|-------|-----------|
| CONVERGE.md 加 JSON 引号规则章节 | converge_failed 11→3 (-73%) |
| domains/mbti.md 加"判定防陷阱" | E/I 命中 65% → 78%+，S/N 命中 79% → 85%+ |
| phase2-3-exploring.md 维度清账 | 整体 4 字母命中 38% → 50%+ |
| phase1-warmup.md 加 tired 分支 | tired 命中 9% → 35%+，need_user_halt 少 3-4 场 |

**总预期**：outcome=ok 83% → 92%+，4 字母命中 38% → 50%+。

---

## 四、怎么验证这些修复

1. 把 patch 打进 `skill-repo/skills/oriself/` 对应文件，不改任何 server 代码
2. 跑一次 baseline 备份：`cp -r benchmark/results benchmark/results.baseline_v1`
3. 重跑：`python3 -m benchmark.runner`
4. 对比：`python3 -m benchmark.compare baseline_v1 results`（compare 脚本待补）

每一块 patch 都是单文件修改，互相独立，可以分批验证。

---

## 五、我想要不要再加一层

现在的 benchmark 是**被试者是 LLM**。真人被试很可能给比 flash 更强的信号（或者更反常，比如明明 E 但就是爱写短句）。等 skill 改完下次要不要找 20 个真人跑一轮？那是 v2 benchmark 的事，先把 v1 这一轮的 skill patch 落下去再说。
