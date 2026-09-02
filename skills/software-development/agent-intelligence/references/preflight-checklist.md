# Preflight Checklist

A 7-line checklist you can paste into the start of any non-trivial task.
Tick the boxes before the first tool call; if you can't tick a box, stop
and answer that question first.

```
[ ] Q1 Context — what 5 things do I actually need to read?
[ ] Q2 Source  — which source is most trustworthy + fresh + structured?
[ ] Q3 Blast   — what's the blast radius if I am wrong?
[ ] Tier       — Tier 1 / 2 / 3 / 4 / 5?
[ ] Citation   — for every non-trivial fact: URL + date fetched?
[ ] Cache      — am I about to change system prompt / toolset / memory mid-session? If yes, don't.
[ ] Diff       — for Tier 3+: have I shown the user the change before applying?
```

## How to use it

1. Copy the block above into your scratchpad or response.
2. Tick each box mentally (or literally). If you can't tick a box
   after 5 seconds, that's the box telling you what to do next.
3. If **any** box ends up unchecked when you're about to call a tool,
   answer it before the call.

## When the checklist is overkill

- Tier-1 read-only public single-shot lookups (e.g. "what's the
  weather in Shanghai")
- Trivial local edits inside the working repo where the blast radius
  is one file
- Conversations where the user is mid-thought and just wants you to
  finish their thought

When in doubt, run the checklist anyway — 30 seconds of discipline
beats 30 minutes of cleanup.

## When the checklist catches a real problem

The most common pattern is **Q3 Blast** catching that what looked
like a "small edit" was actually a Tier 4 production change. The
second most common is **Citation** catching that you were about to
answer from recall when a live source was one URL away.