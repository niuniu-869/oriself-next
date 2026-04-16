# OriSelf Next

[English](./README_EN.md)

**产品即 skill 的对话式人格测试。** 产品本体就是 `SKILL.md` — 任何支持 skill 的 LLM runtime 加载它，整套访谈方法论就位。无需写代码。

> "不是测试系统，是陪聊的朋友。" — 大约 20 轮自然聊天，交付 MBTI 类型 + 个性化洞见 + 独一无二的 Editorial 报告页面，全程不像在做测试。

大多数人格测试给你 93 道选择题和一份模板报告。OriSelf 不一样：一个 LLM 驱动的访谈者，像朋友一样跟你聊天，观察你的语言模式，最终收敛出一份**基于你实际说过的话**的人格画像 — 而不是勾选框暗示的。

核心创新：**产品是一组 markdown 文件。** `skills/oriself/SKILL.md` 包含了完整的访谈方法论 — 阶段、技巧、护栏、收敛逻辑。把它丢进任何支持 skill 的 LLM runtime 就能跑。

**Apache 2.0** — 免费，开源。访谈方法论随你 fork、改造、做得更好。

---

## 快速开始

### 一句话安装

```bash
git clone --single-branch --depth 1 https://github.com/niuniu-869/oriself-next.git ~/.claude/skills/oriself-next
```

完事。重启 Claude Code，说「我想测 MBTI」。就这样。

---

## 最终交付物

大约 20 轮聊天后，OriSelf 收敛并交付三样东西：

| 交付物 | 说明 |
|--------|------|
| **MBTI 类型** | 如 INTJ，附带每个维度的置信度 |
| **个性化洞见** | 3 段文字，基于你在对话中实际说过的话 — 不是模板 |
| **Editorial 报告页** | 每种人格类型对应完全不同的视觉设计，不是换色换模板 |

报告在收敛时由 LLM 实时生成。没有两份报告长得一样。

---

## Skill 结构

```
skills/oriself/
├── SKILL.md                        # 主指令 — 灵魂
├── domains/
│   └── mbti.md                     # MBTI 域透镜（E/I, S/N, T/F, J/P）
├── phases/                         # 访谈流程，7 个阶段
│   ├── phase0-onboarding.md        #   暖场问候，设定预期
│   ├── phase1-warmup.md            #   轻松话题，建立信任
│   ├── phase2-3-exploring.md       #   开放探索，收集证据
│   ├── phase3_5-midpoint.md        #   中场 check-in
│   ├── phase4-deep.md              #   定向深挖
│   ├── phase4_8-soft-closing.md    #   准备收尾
│   └── phase5-converge.md          #   交付类型 + 洞见 + 报告
├── techniques/                     # 访谈方法论
│   ├── reflective-listening.md     #   镜像，不是复读
│   ├── situational-questions.md    #   "如果……你会怎么做？"
│   └── contradiction-probing.md    #   温和地试探一致性
└── examples/
    ├── exemplary-session.md        #   高质量范本对话
    └── banned-outputs.md           #   LLM 绝对不能说的话
```

---

## 五条灵魂（冲突时，灵魂赢）

1. **模仿 TA 的语气。** TA 简洁你别啰嗦。TA 写 300 字，你不要两句打发。
2. **情绪优先。** TA 讲到沉重的事，先靠近感受，再收集信息。
3. **每轮只问一个问题。** 不要堆问题。
4. **留在对话里。** 不要 meta 评论，不要「好问题！」，不要治疗师腔。
5. **证据必须 grounded。** 每条人格信号都必须引用用户的原话。

---

## Roadmap

- [x] MBTI 域透镜
- [ ] 职业域透镜（`domains/career.md`）
- [ ] 关系域透镜（`domains/relationship.md`）
- [ ] 大五人格域透镜
- [ ] 多语言支持（EN, JA）

---

## 贡献

**最有价值的贡献方向：**

| 方向 | 位置 |
|------|------|
| 新域透镜 | 在 `skills/oriself/domains/` 加一个 `.md` |
| 新访谈技巧 | 在 `skills/oriself/techniques/` 加一个 `.md` |
| 改进 banned phrases | 编辑 `skills/oriself/examples/banned-outputs.md` |
| 改进范本对话 | 编辑 `skills/oriself/examples/exemplary-session.md` |

改产品 = 改 markdown。就这么简单。

---

## 许可证

**Apache 2.0** — 免费，开源。

Skill 文件就是产品本体。Fork 它，改造它，做得更好。访谈方法论是你的。
