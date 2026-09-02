---
name: agent-intelligence-lite
description: "Always-on: context economics and tool trust tiers."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [agent, context-economics, tool-trust, decision-routing, lite]
    related_skills: [agent-intelligence]
    notes: |
      This lite version is NOT auto-loaded by Hermes's current
      architecture — there is no config.yaml key or skill-frontmatter
      flag that triggers automatic injection. The full agent-intelligence
      contract lives in the user's SOUL.md ("智能调度铁律" section),
      which Hermes reads on every session. This lite skill ships as a
      reference that users can load with `-s agent-intelligence-lite`
      when they want to re-read the contract without opening SOUL.md.
---

# Agent Intelligence (lite)

Reference copy of the three-question / five-tier contract. For
permanent guidance, see the user's `SOUL.md` "智能调度铁律"
section — Hermes reads that on every session start. For the full
version with patterns, pitfalls, and references, load the
`agent-intelligence` skill explicitly.

## Three questions (before any non-trivial task)

1. **Context** — what 5 things do I actually need to read? (no full
   directories, no full catalogs)
2. **Source** — which source is most trustworthy + fresh + structured?
   Rank: live primary > crawler > search > recall.
3. **Blast** — what's the blast radius if I am wrong?

## Trust tier for every tool call

| Tier | Example | Action |
|------|---------|--------|
| 1 read-only public | `web_search`, `read_file` | call |
| 2 read-only authenticated | MCP `get_*`/`list_*`, `git_log` | call, verify shape once |
| 3 local sandbox write | `patch`, `write_file` in repo | call, show diff |
| 4 remote write | GitLab/Datadog/Cloudflare update | show change, get approval, then call |
| 5 destructive | `rm -rf`, force-push, key rotation, billing | per-action human approval. Never batch. |

If unsure which tier, default one higher than your guess.

## Hard rules

- **Cache stability**: do not change system prompt, toolset, or
  memory mid-session. Cache invalidation dwarfs the savings from
  "fresh" context.
- **Citation**: for every non-trivial claim, attach a URL + fetch date
  (or say "from training-data recall, may be stale").
- **Tier 4/5**: write the operation as a sentence ("I am about to
  delete branch X in repo Y via Z") and pause for approval.

For the long form — patterns, pitfalls, references — load the full
`agent-intelligence` skill.