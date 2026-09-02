---
name: agent-intelligence
description: "Apply context economics and tool trust tiers on every task."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [agent, context-economics, tool-trust, tool-search, decision-routing]
    related_skills: [systematic-debugging, requesting-code-review, hermes-agent, source-driven-development, doubt-driven-development, simplify-code, security-and-hardening]
---

# Agent Intelligence

A meta-skill that shapes how Hermes picks tools, loads context, and ranks
trust for every task. It encodes two lessons from real-world agent design:

1. **Context economics** (from Teknium's "Tool Search" note) — tool
   definitions, MCP catalogs, and skill manifests all consume prompt
   tokens that could otherwise be used for reasoning. Load only what the
   current task actually needs.
2. **Coverage + structured output** (from Firecrawl's design) — the
   ceiling on agent capability is usually the quality of the data it
   can pull in, not the cleverness of the model. Prefer tools that give
   structured, complete, current results over tools that guess from
   memory.

This skill contains no new tools and zero schema footprint. It changes
**how** Hermes decides to use the tools it already has.

## Prerequisites

This skill is pure guidance — it adds **no new tools, no new commands,
no new schema, and no new dependencies**. It works with whatever tools
the active session already has. There is nothing to install.

## When to Use

Load this skill whenever a task involves any of:

- Choosing among several available tools or MCP connectors (e.g. GitLab
  MCP vs `browser_navigate`, `web_search` vs `web_extract`)
- Pulling information that may have changed since training (library
  versions, API signatures, service status, pricing, policies)
- Touching systems with side effects (production APIs, infra, databases,
  messaging)
- Working in a long-running session where prompt caching must survive
- Any time you would otherwise be tempted to dump a long file, full
  directory listing, or full tool catalog into the prompt

Skip it only for trivial single-step lookups where the right tool is
obvious and the answer fits in a sentence.

## The Three Questions

Before the first tool call, answer these three questions in order. They
take ~5 seconds and they prevent most downstream waste.

### 1. What context do I actually need right now?

Ask: "If I read 5 things to answer this, which 5?" Then load exactly those
5. Concrete actions:

- **Tools**: do not enumerate the full toolset for the user. Pick 1-3
  tools that match the task and load their schemas; the rest stay
  implicit. (`registry.list_tools(filter=...)` if available, otherwise
  pick by name.)
- **Files**: read the file you need, not the directory. If you need
  context on a module, read its public surface (`__init__.py` exports,
  README, top-of-file docstring), not the implementation.
- **Web**: when the answer is "current state of X", prefer `web_extract`
  with a specific URL over `web_search` with a vague query.
- **Memories / skills**: load one specific skill, not the whole index.
- **Prompt caching**: never change system prompt, toolset, or memory
  mid-conversation. The cost of cache invalidation dwarfs the savings
  from "fresh" context.

### 2. What's the most reliable source for this information?

Rank candidate sources by **coverage × structure × freshness**:

- **Live primary source** (vendor docs, repo source, official API) —
  highest trust, freshest, structured if the API gives JSON
- **Crawler-grade secondary** (`web_extract` of a known-stable URL) —
  high trust if URL is canonical, otherwise medium
- **Search-aggregated** (`web_search`) — medium trust, useful for
  discovery but noisy
- **Memory / training-data recall** — only when no live source exists;
  flag the answer as "from recall, may be stale"

When two sources disagree, prefer the lower-numbered one and explicitly
say which one you used.

### 3. What's the blast radius if this tool call is wrong?

Map the call onto a trust tier before invoking:

| Tier | Examples | Action |
|------|----------|--------|
| **Read-only public** | `web_search`, `web_extract` to public URL, `read_file` on local docs | Just call it |
| **Read-only authenticated** | MCP server read endpoints, `git_log`, `terminal` for `cat`/`grep` | Call, but verify the data shape once before trusting it |
| **Write to local sandbox** | `patch`, `write_file` in `/tmp`, `terminal` running test commands | Call, but show diff and run a sanity check after |
| **Write to remote** | GitLab PR create, Datadog alert update, Railway deploy, Cloudflare DNS change | List the exact change first, get approval, then call |
| **Destructive** | Delete, drop, force-push, rotate keys, billing change | Always require explicit human approval per action; never batch |

If a tool's tier is unclear, default to the **next higher** tier
(more cautious) until proven otherwise. "I don't know what this tool
does in production" is always Tier 4, not Tier 1.

## How to Run

At the start of each non-trivial task:

1. State the three answers in one or two lines (internal scratch is
   fine; user does not need to see this unless asked).
2. Pick 1-3 tools that match the answer to Question 2 and the
   trust tier from Question 3.
3. Make the first call with the most specific query you can.
4. If the result contradicts prior context or memory, re-rank sources
   and re-run rather than patching the bad output.
5. Before any Tier 4 / Tier 5 call, **write the exact operation as a
   sentence** ("I am about to delete branch `prod-fix` in repo
   `payments`") and pause for approval.

## Patterns to Apply

### Pattern A — "Look up current API" (the canonical case)

Bad: answer from training-data recall, possibly stale.
Good:

1. Identify the canonical docs URL (vendor docs, GitHub README, PyPI).
2. `web_extract` that URL — prefer a deep link to the specific API
   page, not the docs index.
3. If the page is JS-rendered and `web_extract` returns an empty body,
   fall back to a static mirror (e.g. the package's GitHub raw README,
   `html.duckduckgo.com/html/?q=...` cache) before giving up.
4. Cite the URL and the date you fetched it in the answer.

### Pattern B — "Act on a system I have an MCP for" (Cloudflare case)

Bad: enumerate all Cloudflare tools, pick one, mutate.
Good:

1. List only the MCP connector you need (e.g. `cloudflare`).
2. Use its `list_*` / `get_*` / `search_*` to discover the specific
   resource you want to change.
3. Construct the mutation, then read back the current state and
   diff against what you intend to change.
4. Surface the diff to the user, ask for approval, then apply.
5. Read back after applying to confirm.

### Pattern C — "Long session, lots of tools available" (cache survival)

Bad: every turn re-decides which tools to expose; prompt cache
invalidates constantly.
Good:

1. At session start, commit to a small fixed toolset that covers the
   session's likely needs.
2. Only swap a tool out when a task provably cannot proceed without
   it.
3. Never edit system prompt or memory mid-session; defer changes to
   the next session unless the user explicitly opts in with `--now`.

### Pattern D — "Data is behind a JS-heavy SPA" (Firecrawl case)

Bad: declare "can't fetch this page" after one `web_extract` attempt.
Good:

1. Check whether the SPA exposes a JSON endpoint (look in network tab
   patterns, `__NEXT_DATA__`, `window.__INITIAL_STATE__`).
2. If yes, hit the JSON endpoint directly — cleanest structured
   source.
3. If no, try a different surface: the project's docs site (often
   static), the GitHub repo README, the package's `*.json` schema on
   npm/PyPI.
4. Only after exhausting structured sources should you fall back to
   browser automation.

## Examples

Two worked conversations showing how the three questions change the
agent's tool choice. Each shows the same user request answered two
ways: once without the skill's framing (typical), once with it.

### Example 1 — "What's the status of GitLab issue #1234?"

**Without the framing**: agent sees `gitlab` MCP, `web_search`,
`web_extract`, `browser_navigate` all available. Tries `web_search`
("gitlab issue 1234 <project>"), gets a noisy list, picks the first
hit, falls back to `browser_navigate` to load the actual issue page.
Burns 4 tool calls and several thousand tokens. May fail with login.

**With the framing**:

1. Q1 — Context: I need the JSON for issue 1234 — title, state,
   assignee, last update. One source.
2. Q2 — Source: project-local GitLab is on this network, I have the
   MCP, and its `get_issue` endpoint is Tier 2 (authenticated read).
   No JSON endpoint exposed publicly, but the MCP is the canonical
   path.
3. Q3 — Blast radius: read-only. Tier 2 — call directly.

Result: one tool call (`gitlab.get_issue(id="1234")`). Answer
includes the URL `https://gitlab.<host>/<group>/<repo>/-/issues/1234`
and the fetch date.

### Example 2 — "Update Cloudflare DNS for staging"

**Without the framing**: agent calls Cloudflare MCP's
`update_dns_record` directly, the user asked so it must be fine,
change goes through. Two hours later, staging goes dark because the
record pointed at a decommissioned IP.

**With the framing**:

1. Q1 — Context: I need the current record (so I know what I'm
   changing), the target IP, and confirmation of which zone is
   "staging".
2. Q2 — Source: Cloudflare MCP for both read and write — Tier 2
   read to verify current state, Tier 4 write to change.
3. Q3 — Blast radius: Tier 4. Production DNS change. Stop here.

> I am about to change DNS record `staging.example.com` (currently
> `1.2.3.4`) to `5.6.7.8` in zone `example.com` via Cloudflare MCP.
> Reply "go" to apply.

User replies "go". Agent reads current state, applies change, reads
back the new state to confirm. Includes the before/after diff in the
final message.

## Quick Reference

```
Before any non-trivial task:
  Q1 What 5 things do I need to read?
  Q2 Which source is most trustworthy + fresh + structured?
  Q3 What's the blast radius if I am wrong?

Tier 1 read-only public        → call
Tier 2 read-only auth          → call, verify shape once
Tier 3 local sandbox write     → call, show diff, sanity-check
Tier 4 remote write            → show change, get approval, then call
Tier 5 destructive             → per-action human approval

Cache: do not change system prompt / toolset / memory mid-session.
Source rank: primary > crawler > search > recall.
```

## References

This skill ships companion reference files for deeper coverage of its
central tables, plus a preflight checklist and a worked example. Load
them on demand when the table itself is not enough:

- `references/trust-tier-examples.md` — concrete real-Hermes examples
  per trust tier, plus the "default-unknown" rule for when you're not
  sure which tier applies.
- `references/source-ranking-heuristics.md` — how to recognise each
  source tier in the wild, the failure modes of each, and when to
  switch tiers mid-task.
- `references/preflight-checklist.md` — a 7-line checklist to paste
  into your scratchpad before the first tool call. Use it on every
  non-trivial task.
- `references/conversation-1-gitlab-issue.md` — full multi-turn
  transcript for the "What's the status of GitLab issue #1234?"
  request, showing the same conversation done two ways (without the
  three questions: 4 tool calls, no answer; with the three
  questions: 1 tool call, complete answer with citation).

## See also

- `scripts/verify_skill.py` — zero-dependency stdlib script that
  checks the skill's structural integrity. Run with
  `python scripts/verify_skill.py` (no pytest / pip required). Exit
  code 0 = intact; non-zero = at least one issue.

## Pitfalls

1. **Listing tools to "show the user what's available"** — this leaks
   schema into the prompt for no benefit. If the user asks what tools
   exist, `web_search` the public catalog or read
   `toolsets.py` once, then summarize in prose.
2. **Reading a whole repo because "I might need context"** — pick the
   file. If unsure which file, use `search_files` to locate it, then
   `read_file` on the result.
3. **Calling a write-tier tool because "the user said so"** — Tier 4+
   always requires showing the exact change and getting explicit
   approval, even when the user just said "do it". The cost of an
   extra confirmation is tiny; the cost of an unreviewed production
   mutation is not.
4. **Trusting memory over a fresh source** — if a live source exists,
   the live source wins. Memory is for "I remember we discussed
   this" context, not for "here is the current API signature".
5. **Re-deciding the toolset every turn** — every toolset swap
   invalidates prompt cache. Pick at session start, hold steady.
6. **Calling `web_search` when you already have a URL** — `web_search`
   is for discovery; once you have the URL, `web_extract` is cheaper
   and more accurate.
7. **One `web_extract` failure means "can't read this site"** — try a
   JSON endpoint, a GitHub raw file, the package's CDN before giving
   up.

## Self-check

Before declaring the task complete, run this 7-line mental check
against your own work. A copy of it lives at
`references/preflight-checklist.md` for pasting into a scratchpad.

- **Context**: did I load only what I needed? (no full directories,
  no full catalog dumps)
- **Source**: for every non-trivial claim, do I have a URL + fetch
  date? (or did I cite recall and say so?)
- **Blast radius**: for every write call, did I show the diff and get
  approval before the call?
- **Cache**: did I leave system prompt / toolset / memory constant
  through this session?
- **Trust tier**: was the highest tier I called a Tier ≤ what this
  task actually required?
- **Pattern fit**: does the closest Pattern (A / B / C / D) match what
  I did, or did I improvise?
- **Pitfall check**: did I avoid the seven pitfalls listed above?

If any item fails, the failure usually traces back to skipping one of
the three questions at the start. Re-run with the questions explicit.

## Verification

After applying this skill on a real task, check:

- **Token use**: did the toolset stay small? Did you avoid dumping
  directories or full catalogs?
- **Source ranking**: in your final answer, can you point at the
  exact URL/source for each non-trivial claim?
- **Trust tier**: for every write call, was there a visible diff and
  approval before the call?
- **Cache stability**: did system prompt / toolset / memory stay
  constant through the session?

If any of these fail, the failure usually traces back to skipping one
of the three questions at the start. Re-run with the questions
explicit.