# Banned Outputs · 权威源

> **这是 `guardrails.detect_banned_phrases` 的权威源**。每条下面的 `pattern` 字段被加载为检测规则。
>
> 改这里 = 自动生效。不要在 `guardrails.py` 里 hardcode 规则。

## 加载格式

每条 banned pattern 是一个 YAML block，紧跟一段 BAD/GOOD 说明。启动时 `guardrails.py` 解析所有 `yaml pattern` block。

---

## BP1 · 空话式对立

```yaml pattern
id: BP1
kind: regex
pattern: '既.*又.*[渴喜爱想]|既想.*又想|既[是]?[A-Za-z\u4e00-\u9fff]{1,8}又[是]?[A-Za-z\u4e00-\u9fff]{1,8}'
severity: critical
applies_to: [next_prompt, insight_body]
```

- BAD: "你既享受独处又渴望连接。"
- GOOD: "第 7 轮你说'最放松是独自散步'，第 19 轮又说'突然希望谁发微信'。享受的是无任务的独处，怕的是无关注的独处。"

---

## BP2 · 导师腔

```yaml pattern
id: BP2
kind: regex
pattern: '你要学会|你应该|你需要.*去|建议你|试着去'
severity: high
applies_to: [insight_body]
```

- BAD: "你要学会拥抱自己的复杂性。"
- GOOD: 不给建议。描述你看到的。

---

## BP3 · 塔罗式开场

```yaml pattern
id: BP3
kind: regex
pattern: '你是一个(有深度|独特|特别|复杂|有意思|不一样)的人'
severity: critical
applies_to: [next_prompt, insight_body]
```

- BAD: "你是一个有深度的人。"
- GOOD: "上周有没有一个你主动开口、但开完口就后悔的时刻？"

---

## BP4 · 模糊概括

```yaml pattern
id: BP4
kind: regex
pattern: '你在.*中.*既.*又|你在.*方面.*需要'
severity: high
applies_to: [insight_body]
```

- BAD: "你在人际关系中既需要空间又需要陪伴。"
- GOOD: 引用用户某轮原话，说"你当时具体说的是……"。

---

## BP5 · 认同式套话

```yaml pattern
id: BP5
kind: regex
pattern: '(很|非常|挺)常见|很多人都(这样|会|觉得)|这挺正常|这很(正常|普遍)|别担心|不用担心'
severity: critical
applies_to: [next_prompt, insight_body]
```

- BAD: "这很常见，很多年轻人都有这种感觉。"
- GOOD: 不说"很常见"。追问一个更具体的画面，或复述他的关键词。

---

## BP6 · 总结式结尾

```yaml pattern
id: BP6
kind: regex
pattern: '总(的|体)来说|总结.?一下|综上(所述)?|简而言之'
severity: medium
applies_to: [insight_body]
```

- BAD: "总的来说，你是一个外冷内热的 I 人。"
- GOOD: 引用 3 处用户原话，把话题揉回 TA 的具体生活。

---

## BP7 · 心理学术语堆

```yaml pattern
id: BP7
kind: regex
pattern: '认知功能栈|[NSTF][ei]-[NSTF][ei]主导|荣格|人格维度|投射|阴影自我|自我实现'
severity: high
applies_to: [next_prompt, insight_body]
```

- BAD: "你展现出典型的内向直觉思考者的认知功能栈 Ni-Te 主导。"
- GOOD: 用大白话："你想事情先在脑子里反复跑很多遍，再开口。"

---

## BP8 · 两头讨好

```yaml pattern
id: BP8
kind: regex
pattern: '既适合.*也适合|可以是.*也可以是|不管是.*还是.*都'
severity: medium
applies_to: [insight_body]
```

- BAD: "你既适合做技术也适合做管理。"
- GOOD: 选一边站。从对话里的具体证据出发。

---

## BP9 · 类型化过早（HARD-GATE 1 强化检测）

```yaml pattern
id: BP9
kind: regex
pattern: '你(听起来|看起来|明显|显然|应该)(是|像)?\s*[EINSTF]{2,4}\s*(人|型|人格)?|你的\s*MBTI\s*(应该|可能|是).*[EINSTF]'
severity: critical
applies_to: [next_prompt]
note: 仅在 round_number < 20 且 action != "converge" 时触发
```

- BAD（第 5 轮）: "你听起来像 INTJ 型。"
- GOOD: 继续问情境题。

---

## BP10 · 空洞抽象词

```yaml pattern
id: BP10
kind: regex
pattern: '独特的灵魂|内心的光|生命的意义|成长的道路|找到自我|拥抱真实的自己'
severity: high
applies_to: [next_prompt, insight_body]
```

- BAD: "拥抱真实的自己，你会找到内心的光。"
- GOOD: 不输出这种话。不存在。

---

## BP11 · Frequency 问法（情境坍塌）

```yaml pattern
id: BP11
kind: regex
pattern: '经常(这样|会|发生|想)|多吗[？?]?$|是偶尔.*还是经常|平时会不会|通常.*吗[？?]?$'
severity: high
applies_to: [next_prompt]
```

- BAD: "你这种联想的时刻多吗？"
- BAD: "这种事在你生活里是偶尔一次，还是经常发生？"
- GOOD: "上一次你在课堂上突然联想到一个不相关的东西，是什么时候？讲讲那次的具体场景。"

频率题把对话变成问卷。总是改成"上一次 / 最近一次 + 具体场景"。

---

## 测试要求

**每条 banned pattern 在 `tests/test_guardrails.py::test_banned_phrases` 自动生成 1 个 case**：
- 构造一条命中 pattern 的文本 → 断言 `detect_banned_phrases` 返回非空
- 构造一条看起来相似但合法的文本 → 断言返回空（或不含该 BP id）

guardrails 从本文件加载 pattern。改这里 → 重跑测试 → 自动覆盖新 case。
