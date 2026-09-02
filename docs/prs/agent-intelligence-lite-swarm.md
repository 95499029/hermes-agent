# PR Title (paste this exactly)

```
feat(skills): agent-intelligence-lite + templates + swarm-collaboration
```

67 chars — under the 72-char GitHub soft cap.

---

# PR Body

## What

Three additions that all extend the agent-intelligence surface area
without modifying Hermes core:

1. **`agent-intelligence-lite`** — a 2.5KB compressed copy of the
   agent-intelligence contract (three questions, five trust tiers,
   hard rules). Reference, not auto-load.
2. **Templates and i18n** for `agent-intelligence` — three Tier 3/4/5
   pre-formatted statements, a source-bias checklist, and a Chinese
   version of the SKILL.md body.
3. **`swarm-collaboration`** — new meta-skill distilling the EvoMap /
   EvoX benchmark where "swarm" (sub-agents report directly into
   numbered slots) outperformed "sub-agent" (parent re-summarises)
   on the same 563-problem benchmark.

Plus one trivial bug fix:

4. `optional-skills/creative/pixel-art/scripts/__init__.py` was a
   zero-byte file. Add a docstring so it's no longer an unfinished
   marker.

## Why

The first PR (`feat/agent-intelligence-skill`) introduced the
agent-intelligence meta-skill. This follow-up fills in the gaps that
reviewers and users surfaced:

- The full SKILL.md (15KB) is too large to load on every session.
  The lite version (2.5KB) is a reference users can pull with
  `-s agent-intelligence-lite` when they want to re-read the
  contract without opening SOUL.md.
- Tier 3/4/5 tool calls need standard statement formats so the
  approval gate is legible. The templates package those.
- The Chinese version saves the model the English-to-Chinese
  translation on every turn in a Chinese-speaking session.
- The swarm skill closes a real retention gap. Hermes's
  `delegate_task` default is sub-agent mode; the EvoX benchmark
  shows it loses 44.5% of internally-correct answers to parent
  re-summarisation. Swarm mode cuts that loss.

## Files

```
 optional-skills/creative/pixel-art/scripts/__init__.py          |   6 +
 skills/software-development/agent-intelligence-lite/SKILL.md     |  61 ++++
 skills/software-development/agent-intelligence/SKILL.zh.md       |  50 ++++
 skills/software-development/agent-intelligence/
   references/source-bias-checklist.md                            | 105 ++++++
 skills/software-development/agent-intelligence/
   templates/trust-tier-decision.md                               |  68 +++++
 skills/software-development/agent-intelligence/
   templates/source-citation.md                                   |  73 +++++
 skills/software-development/agent-intelligence/
   templates/blast-radius-confirmation.md                         |  86 +++++
 skills/autonomous-ai-agents/swarm-collaboration/SKILL.md       | 231 ++++++
 tests/skills/test_swarm_collaboration_skill.py                   | 161 ++++++++
 9 files changed, 841 insertions(+), 1 deletion(-)
```

## What the swarm skill does in practice

Six principles, with the EvoX benchmark (Claude Haiku 4.5, 563
problems) as the lever:

> **Single agent**: 26.29% correct
> **Sub-agent mode** (parent re-summarises): 38.54% correct
> **Swarm mode** (sub-agents report directly to slots): 70.69%–70.87% correct

In sub-agent mode, sub-agents internally answered 373 of 563 problems
correctly, but only 217 survived the parent's re-summarisation step
— 55.5% retention. The lost 156 were correct answers the parent
rewrote incorrectly on the way up.

The six principles encoded in the skill:

1. **Direct result routing** — never re-summarise at the parent.
2. **Pre-declared output shape** — JSON / file / table / slot, not
   "summarise the doc".
3. **No repeated context in the join** — minimum context per subtask.
4. **Failures are inputs, not disposals** — slot, not silent drop.
5. **Persist successful patterns** — one line, dated, in memory.
6. **Independent lifecycle** — fire-and-forward, not wait-for-nudge.

## What the templates package does

The agent-intelligence skill tells the model to "show diff" or
"show blast radius" before Tier 3/4/5 calls. The templates package
turns that into ready-to-use formats:

- `templates/trust-tier-decision.md` — pre-formatted statement
  for each of Tier 3, 4, 5 (action, current state, target state,
  reversibility, blast radius, approval pattern).
- `templates/source-citation.md` — citation format: `<claim>
  (Source: <URL>, fetched <YYYY-MM-DD>)`.
- `templates/blast-radius-confirmation.md` — pre-confirmation
  checklist for Tier 4/5 (action, current/target state, reversible,
  blast radius, trust tier, approval pattern).

## Tests

Two new files; **67 tests total**, all green:

- **`tests/skills/test_swarm_collaboration_skill.py`** — 14 tests
  on frontmatter compliance, six-principles ordering (must appear
  in risk-ascending order), and principle-by-principle content
  contracts:
  - P1 forbids parent re-summarisation
  - P4 forbids silent failures
  - P5 mandates dated one-line memory

- All previous agent-intelligence tests still pass — 53/53.

```
$ pytest tests/skills/test_swarm_collaboration_skill.py \
          tests/skills/test_agent_intelligence_skill.py \
          tests/skills/test_agent_intelligence_e2e.py
============================= 67 passed in 8.71s ==============================
```

## Out of scope (deliberately)

- **No changes to `model_tools.py` or `toolsets.py`** — these skills
  are pure guidance, loaded only when the user opts in.
- **No new core tools** — zero schema footprint.
- **No installer changes** — the new skills land in the standard
  `skills/<category>/<name>/SKILL.md` location and are discovered
  by the existing skill scan.
- **No prompt-cache breaking** — skills are loaded once at session
  start when opted in; never re-injected.

## Checklist

- [x] Tests pass (`pytest tests/skills/`)
- [x] Self-verification script passes (`scripts/verify_skill.py`
      on `agent-intelligence`)
- [x] Frontmatter follows `AGENTS.md` §"Skill authoring standards"
      (description ≤ 60 chars, ends with period, no marketing
      words, platforms declared, related_skills populated)
- [x] No new schema footprint; existing toolsets unchanged
- [x] All new skills land in the standard
      `skills/<category>/<name>/SKILL.md` location
- [x] Swarm skill frontmatter notes the benchmark basis so future
      readers know the claims are not invented

## How to test locally

```bash
# Run the full skill test suite
pytest tests/skills/test_swarm_collaboration_skill.py \
       tests/skills/test_agent_intelligence_skill.py \
       tests/skills/test_agent_intelligence_e2e.py

# Verify the new skills load via Hermes's real code path
python -c "import sys; sys.path.insert(0, '.'); \
           from tools.skills_tool import skill_view; \
           from agent.skill_commands import build_preloaded_skills_prompt; \
           print(skill_view('swarm-collaboration')); \
           print(build_preloaded_skills_prompt(['swarm-collaboration']))"

# Run the no-deps verifier on agent-intelligence
python skills/software-development/agent-intelligence/scripts/verify_skill.py -v
```

## Note on the source branch

This PR is opened from `feat/agent-intelligence-lite-swarm-and-templates`
on the contributor's fork (`github.com:95499029/hermes-agent`). The
fork's `main` is far behind upstream; the branch was pushed as a
feature branch rather than rebased onto the fork's `main` to keep
history reviewable. If reviewers prefer a rebase onto upstream
`main`, the contributor can rebase; the diff of this PR will not
change in any way that affects behaviour (the new files are
entirely additive, the bug fix is a docstring).