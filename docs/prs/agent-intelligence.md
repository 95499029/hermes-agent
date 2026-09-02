# PR Title (paste this exactly)

```
feat(skills): add agent-intelligence meta-skill for context economics and tool trust tiers
```

71 chars — under the 72-char GitHub soft cap.

---

# PR Body

## What

Adds a new bundled skill, **`agent-intelligence`**, that teaches Hermes
how to decide *which tool to use, against which source, with what blast
radius* on every non-trivial task. The skill is **pure guidance** — it
adds zero tools, zero schema, zero commands. Its only cost is ~13.8 KB
of preloaded text when the user passes `-s agent-intelligence`.

Also includes two local customisations the user has been running with:

- **MoA picker entry disabled** (`hermes_cli/inventory.py`,
  `hermes_cli/models.py`)
- **`opencode-free` provider renamed to `_opencode-free`** so the plugin
  loader skips it (`plugins/model-providers/_opencode-free/`)

## Why

The skill distils two lessons from real-world agent design into a
concrete decision procedure:

1. **Context economics** — tool schemas, MCP catalogs, and skill
   manifests all consume prompt tokens that could otherwise be used for
   reasoning. Load only what the current task needs, and never mutate
   the system prompt / toolset / memory mid-session.
2. **Coverage × structured output** — the ceiling on agent capability
   is usually the *quality* of the data it can pull in, not the model.
   Prefer tools that return structured, complete, current results
   over tools that guess from memory.

The decision procedure is a **3-question preflight** (context / source /
blast radius) plus a **5-tier trust ladder** for every tool call, plus
a **4-tier source ranking** (live primary → crawler → search →
recall). The skill ships with **four canonical patterns**, **seven
anti-patterns**, and a **post-task self-check**.

The MoA and opencode-free changes are unrelated to the skill but were
uncommitted in the user's working tree; collecting them here keeps
their history together.

## Files

```
 hermes_cli/inventory.py                                                 |   1 +
 hermes_cli/models.py                                                    |   2 +-
 plugins/model-providers/_opencode-free/__init__.py                      |  67 ++++
 plugins/model-providers/_opencode-free/plugin.yaml                      |   5 +
 skills/software-development/agent-intelligence/SKILL.md                 | 344 ++++++++++
 skills/software-development/agent-intelligence/references/
   trust-tier-examples.md                                                | 105 ++++
   source-ranking-heuristics.md                                          | 100 ++++
   preflight-checklist.md                                                |  42 +++
   conversation-1-gitlab-issue.md                                       | 101 +++++
 skills/software-development/agent-intelligence/scripts/verify_skill.py  | 194 ++++++++++
 tests/skills/test_agent_intelligence_skill.py                           | 142 +++++++
 tests/skills/test_agent_intelligence_e2e.py                             | 338 ++++++++++
 12 files changed, 1440 insertions(+), 1 deletion(-)
```

## What the skill does in practice

Three worked examples live in the skill body and in
`references/conversation-1-gitlab-issue.md`. The headline comparison:

> **"What's the status of GitLab issue #1234?"**
>
> **Without the framing**: 4 tool calls (`web_search × 2`,
> `browser_navigate × 2`), ~3,200 tokens, no answer (login wall).
>
> **With the framing**: 1 tool call (`gitlab.get_issue(id="1234")`),
> ~450 tokens, complete answer with URL + fetch date.

The framing costs ~50 words of internal scratch. The savings are 7× on
tokens and 0 vs 1 on answer quality.

## Tests

Two test files, **53 tests total**, all green:

- **`tests/skills/test_agent_intelligence_skill.py`** — 13 tests on
  frontmatter compliance and static body contracts (description ≤ 60
  chars, no marketing words, three required sections, three framing
  questions, five trust tiers, source ranking, four patterns, no
  always-invocation flag).
- **`tests/skills/test_agent_intelligence_e2e.py`** — 40 tests that
  exercise Hermes's **real production code path** (`skill_view` →
  `_load_skill_payload` → `build_preloaded_skills_prompt`), asserting
  that the injected prompt contains every contract the skill promises
  *and* that the trust tiers appear in in risk-ascending order
  (reordering would invert the safety gradient).

```
$ pytest tests/skills/test_agent_intelligence_skill.py \
          tests/skills/test_agent_intelligence_e2e.py
============================= 53 passed in 8.25s ==============================
```

The skill also ships a zero-dependency **`scripts/verify_skill.py`**
that does the same structural checks without pytest. Both are tested
against each other — a regression test copies the skill to a temp dir,
removes a required phrase, and asserts the verify script catches it.

```
$ python skills/software-development/agent-intelligence/scripts/verify_skill.py
Verifying skill: agent-intelligence (...)
OK: skill is intact.
```

## Out of scope (deliberately)

- **No new core tools** — the skill adds zero schema. Everything it
  teaches is about how to use the tools Hermes already has.
- **No changes to `model_tools.py` or `toolsets.py`** — the skill is
  pure guidance, loaded only when the user opts in with
  `-s agent-intelligence`.
- **No installer changes** — `SKILL.md` lands in
  `skills/software-development/agent-intelligence/` and is discovered
  by the existing skill scan; no registration code touches it.
- **No new MCP server or catalog entries** — this is a reasoning
  skill, not a data source.
- **No prompt-cache breaking** — the skill is loaded once at session
  start and never re-injected.

## Checklist

- [x] Tests pass (`pytest tests/skills/test_agent_intelligence_*`)
- [x] Self-verification script passes (`scripts/verify_skill.py`)
- [x] Frontmatter follows `AGENTS.md` §"Skill authoring standards"
  (description ≤ 60 chars, ends with period, no marketing words,
  platforms declared, related_skills populated)
- [x] No new schema footprint; existing toolsets unchanged
- [x] Skill lands in the standard
  `skills/<category>/<name>/SKILL.md` location
- [x] Companion files in `references/` and `scripts/` are linked
  from the SKILL body via a `## References` and `## See also`
  section

## How to test locally

```bash
# Run the test suite
pytest tests/skills/test_agent_intelligence_skill.py \
       tests/skills/test_agent_intelligence_e2e.py

# Verify the skill loads via Hermes's real code path
hermes -s agent-intelligence --version     # exits cleanly
python -c "import sys; sys.path.insert(0, '.'); \
           from tools.skills_tool import skill_view; \
           print(skill_view('agent-intelligence'))"

# Run the no-deps verifier
python scripts/verify_skill.py -v
```

## Note on the source branch

This PR is opened from `feat/agent-intelligence-skill` on the
contributor's fork (`github.com:95499029/hermes-agent`). The fork's
`main` is far behind upstream; the branch was pushed as a feature
branch rather than rebased onto the fork's `main` to keep history
reviewable. If reviewers prefer a rebase onto upstream `main`, the
contributor can rebase; the diff of this PR will not change in any
way that affects behaviour (the new files are entirely additive).