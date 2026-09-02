# Agent Intelligence / 智能调度

中文版 Skill 内容。同样的三问 + 五档契约，模型在中文语境下不需要英译中，省 token。

## 三问（任何非平凡任务前 5 秒内回答）

1. **Context（上下文）** — 我需要读哪 5 件事？不要列整个目录、列整个 catalog
2. **Source（数据源）** — 哪个源最可信 + 最新 + 结构化？rank: 官方一手 > 抓取 > 搜索 > 记忆
3. **Blast（爆炸半径）** — 错了后果多大？决定信任 tier

## 5 档信任分级（每个 tool call 前判定）

| Tier | 例 | 动作 |
|---|---|---|
| 1 只读公开 | web_search, read_file | 直接调 |
| 2 只读鉴权 | MCP get_*/list_*, git_log | 调，验证 shape 一次 |
| 3 本地沙箱写 | patch, write_file, terminal 在 repo | 调，显示 diff |
| 4 远程写 | GitLab/Datadog/Cloudflare update | **显示操作 + 等用户点头 + 才调** |
| 5 破坏性 | rm -rf, force-push, key rotation, 计费 | **per-action 人工确认，永远不批量化** |

判断不出 tier 时默认高一档。"我不知道这工具在生产干什么" 默认 Tier 4, 不是 Tier 1。

## 硬规则

- **Cache 稳定**: 不要 mid-conversation 改 system prompt / toolset / memory。缓存失效的成本远超"新上下文"的收益
- **Citation**: 每个非平凡结论附 URL + fetch date，或者明说"from training-data recall, may be stale"
- **Tier 4/5 例外**: 用一句话写明操作 ("我即将删除 payments repo 的 prod-fix 分支"), 等回复 "go" 才执行

## 为什么是这三问 + 五档

不替 hermes 加新工具，而是教它**怎么判断**。

- **三问**让模型把"我应该做什么"显式化，避免凭直觉选工具
- **五档**让模型对自己每次 tool call 的风险有自知；不假惺惺地"反正用户让我做就做"
- **硬规则**保护三件最重要的事：prompt cache（成本）、source（准确度）、human gate（高风险）

## 与完整版的差异

这是中文 lite 版（2KB）。完整版在 `agent-intelligence` skill（15KB），包含 patterns / pitfalls / examples / references / templates，详见：
- `references/trust-tier-examples.md` — 每档的真实例子
- `references/source-ranking-heuristics.md` — 4 档源怎么识别
- `references/source-bias-checklist.md` — 每档源的偏倚
- `references/preflight-checklist.md` — 7 行可粘贴 checklist
- `references/conversation-1-gitlab-issue.md` — 完整对话样本
- `templates/trust-tier-decision.md` — Tier 3/4/5 的标准陈述格式
- `templates/source-citation.md` — 引用格式
- `templates/blast-radius-confirmation.md` — Tier 4/5 前的确认清单
- `scripts/verify_skill.py` — 完整性自检（不依赖 pytest）

需要更详细的 patterns/pitfalls 时，加载完整版：`hermes -s agent-intelligence`。