# Swarm Collaboration / 蜂群协作

中文版 Skill 内容。同样的六原则，模型在中文语境下不需要英译中。

## 为什么

563 道题的对照实验（同一模型 Claude Haiku 4.5）：

- **单 Agent**：26.29% 正确
- **Sub-Agent 模式**（父 Agent 再汇总）：38.54% 正确
- **蜂群模式**（子 Agent 直接落到 slot）：70.69%–70.87% 正确

在 Sub-Agent 模式下，子 Agent 内部答对 373 题，但经过父 Agent汇总后只剩 217 题，**保留率仅 55.5%**——156 个正确答案在汇总过程中被改错。

下面的六条原则正是关闭这个差距的方法。

## 何时使用

任务同时满足以下全部条件时使用：

- 任务可以拆成 2+ 个明确独立的子任务（每个子任务的产出不依赖其他子任务的输出）
- 每个子任务有已知的输出形式（文件路径 / JSON schema / Markdown 章节等），不是需要父 Agent 整合的自由格式
- 原本你会用 `delegate_task(tasks=[...])` 同步等待所有结果再继续

不适用场景：单步查询、子任务之间有依赖关系的（改为串行）、唯一汇合就是一行摘要。

## 六原则

### 1. 直接结果路由 — 父 Agent 不要二次汇总

子 Agent 完成后，结果**直接**进入按任务编号分配的输出位，不是回到回父 Agent 重新解读。

错的（Sub-Agent 模式，保留率 55.5%）：

```
父: "找 Stripe 创始人"
  ↓
子 A: 搜索，返回 {eric, nicolas, caleb}
  ↓ (回到父)
父: 重新读、重新格式化
  ↓ (可能丢信息)
用户: 拿到重写版
```

对的（蜂群模式）：

```
父: "找 Stripe 创始人。输出 schema: {founders:[str]}"
  ↓
子 A: 输出 {"founders": ["Eric Ciarla", "Nicolas Camara", "Caleb Peffer"]}
  ↓ (直接到 slot 1)
用户: 直接拿到 schema 合规输出
```

### 2. 预先声明输出形式

每个子任务必须事先指定：

- **输出类型**：Markdown 章节 / JSON 文件 / 表格 / bullet list 等
- **输出路径 / slot**：落在哪里
- **质量标准**："完成"长什么样（长度、字段、citation 要求等）

父 Agent 在委派**之前**写好规范。子 Agent 不要自己发明输出形式。

### 3. join 时不重复上下文

每个子任务的 prompt 只携带**它需要的最小上下文**，不是完整用户 prompt + 其他所有子任务输出。如果子任务 B 需要子任务 A 的输出，说明拆分错了——改为串行。

### 4. 失败是输入，不是丢弃

如果子 Agent 输出为空、部分、错误，失败进入**编号失败位**，不是悄悄丢弃。父 Agent 决定 retry / fallback / 上报用户。

错：

```
子 B 返回 {"error": "timeout"}
父: 静默 retry
用户: 只看到成功结果，不知道 B 失败
```

对：

```
子 B 返回 {"error": "timeout", "partial": [...]} 到 slot 2
父: 把 slot 2 当作"B 超时；部分数据: [...]; retry? skip? 用部分?" 上报
用户: 决定
```

### 5. 持久化成功模式

蜂群完成后，如果某个子 Agent 的方法可以泛化（"用这个 query 做 X 类查询"），父 Agent 把模式**一行**写到用户级 memory，附日期戳，不要长篇大论。

格式：

```
2026-09-02  founders-lookup  :  "用 Wikipedia + LinkedIn 交叉验证；
                                 返回 JSON {founders:[str]}；
                                 不要 paraphrase。"
```

### 6. 独立生命周期 — 不依赖父 Agent 续轮

每个子 Agent 应该能独立运行、完成、上报，不需要父 Agent 活"确认"中途。如果你的委派需要父 Agent 戳一下子 Agent，那个"戳"就是失败面——改为 fire-and-forward。

Hermes 中：`delegate_task(background=true)` 是真蜂群；同步 `tasks=[...]` 默认是 Sub-Agent 模式。要有意识地选。

## 何时不要使用

- **子任务之间有共享状态中途**：串行做或合并成单个子任务
- **输出形式未定**：先确定 schema 再拆
- **只拆 1 个子任务**：直接做，不要为了用 skill 而用
- **结果是自由格式散文**：父 Agent 必须整合的那种——重新考虑是否真的能拆

## 反模式

1. **"为了清晰让我总结一下"** — 这是失败面。用户的清晰来自结构化 slot，不是你的散文改写。如果你发现自己在重写子 Agent 输出，停下来想想 slot 为什么没预先结构化
2. **中途共享状态** — 子任务 B 读子任务 A 的输出，没有真正并行。改为串行或合并
3. **自由格式子任务 prompt** — "总结这篇文档"不是规范。"返回 5 个 bullet，每个 ≤30 字，引用页码"才是
4. **静默失败** — 缺失 slot 比失败 slot 更糟。如果子 Agent 没返回，那是数据，要上报
5. **memory 灌水** — 不要写 5 段"什么 work 了"。一个模式一行。未来的你（或未来的蜂群）读标题，不读段落

## 验证

蜂群任务跑完后检查：

- **Slot fidelity**：每个子任务是否在声明的 slot 里产出，而不是自由格式散文
- **保留率**：蜂群输出的正确答案数 vs 已知子 Agent 内部正确的答案数。目标 ≥90%
- **用户侧装配**：用户拿到的是 slot 直接装配，还是父 Agent 改写的？（后者是 bug）
- **Memory hygiene**：每个可泛化模式是否只写了一行？（多了 = 噪音，少了 = 失去学习）

## 与 agent-intelligence 的关系

蜂群协作是 agent-intelligence 三问 + 五档的具体应用：

- **Q1 Context**：每个子任务只拿它需要的 5 件事，不重复全文
- **Q2 Source**：每个子任务自己挑 Tier 1/2/3 工具，父 Agent 不重复决定
- **Q3 Blast**：每个子任务独立评估——如果一个子任务是 Tier 4，整个蜂群要决定是用 Tier 3 fallback 还是用户先批准

完整 patterns / pitfalls / templates 见 `agent-intelligence` skill。