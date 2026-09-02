---
name: swarm-collaboration
description: "Decompose tasks so sub-agents report directly to slots."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [delegation, multi-agent, swarm, sub-agent, context-economics]
    related_skills: [agent-intelligence, systematic-debugging, codebase-inspection]
    notes: |
      Distilled from a published experiment by EvoMap / EvoX where
      "swarm" (sub-agents reporting directly into a numbered-result
      pool) outperformed "sub-agent" (sub-agents reporting back to a
      parent that re-summarises) on the same 563-problem benchmark:

        single agent   :  26.29% correct
        sub-agent      :  38.54% correct
        swarm          :  70.69%-70.87% correct

      Sub-agents in the sub-agent mode answered 373 of 563 problems
      correctly internally, but only 217 survived the parent
      re-summarisation step — 55.5% retention. The lost 156 were
      correct answers the parent rewrote incorrectly on the way up.

      This skill encodes the structural rules behind that delta.
---

# Swarm Collaboration

A meta-skill that shapes how Hermes delegates multi-step work. When
you have a non-trivial task that could be split into independent
parts, this skill makes sure the split + join protocol doesn't lose
correctness on the way back to the user.

**Why this matters**: a published 563-problem benchmark compared three
modes on the same model (Claude Haiku 4.5):

- **Single agent**: 26.29% correct
- **Sub-agent mode** (parent re-summarises): 38.54% correct
- **Swarm mode** (sub-agents report directly to slots): 70.69%–70.87% correct

In sub-agent mode, sub-agents internally answered 373 of 563 problems
correctly, but only 217 survived the parent's re-summarisation step
— 55.5% retention. The lost 156 were correct answers the parent
rewrote incorrectly on the way up.

The structural rules below are what closes that gap.

## Prerequisites

This skill is pure guidance — it adds **no new tools, no new
commands, no new schema, no new dependencies**. It works with whatever
tools and `delegate_task` semantics the active session already has.
There is nothing to install.

## When to Use

Load this skill when the user's task meets **all** of:

- The task can be split into 2+ clearly independent subtasks (each
  producing its own deliverable that does not need the others' output
  to be useful).
- Each subtask has a known output shape (file path, JSON schema,
  Markdown heading, etc.) — not free-form prose that a parent would
  have to integrate.
- You would otherwise use `delegate_task` with `tasks=[...]` and
  wait for all results before continuing.

Skip it for single-step lookups, for tasks where subtasks depend on
each other's output (force a sequential plan instead), and for tasks
where the only "join" you need is one-line summaries.

## The Six Principles

### 1. Direct result routing — never re-summarise at the parent

When a sub-agent finishes, its result goes **directly to the
destination** identified by task number, not back to the parent agent
for re-interpretation.

Bad (sub-agent mode, 55.5% retention):

```
parent: "Find me the founders of Stripe"
  ↓
sub-agent A: searches, finds {eric, nicolas, caleb}
  ↓ (result goes back to parent)
parent: re-reads the answer, reformats it
  ↓
user: receives the parent's rewrite (possibly lossy)
```

Good (swarm mode):

```
parent: "Find me the founders of Stripe. Output schema: {founders:[str]}"
  ↓
sub-agent A: produces {"founders": ["Eric Ciarla", "Nicolas Camara", "Caleb Peffer"]}
  ↓ (result goes directly to user-facing slot 1)
user: receives the schema-conformant output as-is
```

### 2. Pre-declare output shape, not just topic

Every subtask must specify:

- **Output type**: Markdown section, JSON file at path X, table at
  path Y, list of bullet points, etc.
- **Output path / slot**: where it lands. Numbered if multiple, named
  if single.
- **Quality bar**: what "done" looks like. (Length, schema fields,
  citation requirement, etc.)

The parent writes the spec **before** delegating. Sub-agents do not
invent their own output shape. This is what lets the parent skip the
re-summarisation step.

### 3. No repeated context in the join

Each subtask's prompt carries the **minimum context it needs**, not
the full user prompt + every other subtask's output. If subtask B
needs something from subtask A's output, that's a sign the split is
wrong — make it sequential, not parallel.

Why: every duplicated context token costs the parent on the join
turn. Worse, it tempts the parent to re-summarise "for coherence",
which is the failure mode Principle 1 prevents.

### 4. Failures are inputs, not disposals

If a sub-agent's output is empty, partial, or wrong, the failure
goes to a **numbered failure slot** — not silently dropped. The
parent then decides whether to retry, fall back, or surface the
failure to the user.

Bad:

```
sub-agent B returns {"error": "timeout"}
parent: quietly retries
user: gets only successful results, no idea B failed
```

Good:

```
sub-agent B returns {"error": "timeout", "partial": [...]} to slot 2
parent: surfaces slot 2 as "B failed with timeout; partial data:
        [...]. Retry? Skip? Use partial?"
user: makes the decision
```

### 5. Persist successful patterns

After a swarm finishes, if any sub-agent's approach generalises
("use this query for X-type lookups"), the parent writes the pattern
to the user-level memory file with a date stamp, not a long-form
narrative. One-line heuristics beat paragraphs.

Format:

```
2026-09-02  founders-lookup  :  "Use Wikipedia + LinkedIn
                                 cross-check; return JSON
                                 {founders:[str]}. Never paraphrase."
```

Why: this is the "AI for AI" pattern from the EvoX paper. Tomorrow's
swarm should not rediscover what today's swarm already validated.

### 6. Independent lifecycle — no follow-up dependency

Each sub-agent should be able to run, complete, and report without
needing the parent to be alive to "acknowledge" or "approve" mid-run.
If your current delegation pattern waits for the parent to nudge the
child, that nudge is the failure surface — replace with fire-and-
forward.

In Hermes terms: `delegate_task(background=true)` for true swarm; sync
`tasks=[...]` mode where the parent integrates is sub-agent mode by
definition. Choose deliberately.

## Quick Reference

```
Swarm task preflight:
  [ ] subtasks are mutually independent (no shared state mid-run)
  [ ] output shape pre-declared per subtask (JSON, file, table)
  [ ] numbered slots / paths assigned (no "where does this go")
  [ ] minimum context per subtask (no full-prompt duplication)
  [ ] failure handling named (slot, retry, surface)
  [ ] pattern persistence step planned (if success)

After the swarm:
  [ ] each slot received its deliverable (or a failure record)
  [ ] user-facing output assembled by slot, not by re-summarisation
  [ ] any generalisable pattern saved to memory (one line, dated)
```

## Pitfalls

1. **"Let me just summarise for clarity"** — this is the failure
   surface. The user's clarity comes from structured slots, not from
   your prose rewrite. If you find yourself re-writing sub-agent
   output, stop and ask why the slot was not pre-structured.
2. **Shared state mid-run** — if subtask B reads subtask A's output,
   you do not have parallel. Make it sequential or merge them.
3. **Free-form subtask prompts** — "summarise the doc" is not a
   spec. "Return 5 bullet points, each ≤30 words, citing the page
   number" is.
4. **Silent failures** — a missing slot is worse than a failed slot.
   If a sub-agent didn't return, that is data; surface it.
5. **Memory spam** — do not write 5 paragraphs of "what worked". One
   line per pattern. Future you (or future swarm) reads headings, not
   paragraphs.

## Verification

After applying this skill on a real swarm task, check:

- **Slot fidelity**: did each subtask produce output in its declared
  slot, not in free-form prose?
- **Retention rate**: compare the number of correct answers that
  came out of the swarm against the number you knew were correct
  inside individual sub-agents. Target: ≥90% retention.
- **User-side assembly**: did the user receive the assembled output
  directly, or did the parent rewrite it? (The latter is a bug.)
- **Memory hygiene**: did you add at most one line per generalisable
  pattern? (More = noise; less = lost learning.)