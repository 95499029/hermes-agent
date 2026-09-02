# Hermes 完整性 + Bug 检测报告

Date: 2026-09-02
Scope: hermes-agent v0.21.0 on Windows (J:\Hermes\hermes-agent),
HERMES_HOME=J:\Hermes\data, 1483 messages / 14 sessions / 9.4 MB state.db.

This report covers the bugs found during a single audit pass and the
fixes shipped in the follow-up commit on
`feat/agent-intelligence-lite-swarm-and-templates`.

---

## Critical: SOUL.md not actually loaded

**Severity: high — affects every prior session of this user.**

Hermes loads SOUL.md via `_home = get_hermes_home(); soul_path = _home
/ "SOUL.md"`. With `HERMES_HOME=J:\Hermes\data`, this resolves to
`J:\Hermes\data\SOUL.md`.

The user had been editing **J:\Hermes\SOUL.md** (9376 bytes, with
"智能调度铁律" / agent-intelligence triggers / three-question /
five-tier / fork-branch-备忘 sections). But that path was never
read by Hermes — Hermes only ever read `J:\Hermes\data\SOUL.md`,
which contained 667 bytes of stock "Be direct / no filler"
identity text.

**Effect**: every "auto-load agent-intelligence" trigger, every
three-question reminder, and every fork-branch bookmark Hermes
was supposed to pick up from SOUL.md was silently absent from
the actual sessions. All skill loading still required the user
to explicitly type `/skill agent-intelligence`.

**Fix**: appended the contents of J:\Hermes\SOUL.md to
J:\Hermes\data\SOUL.md (now 9527 bytes). Future edits should target
`J:\Hermes\data\SOUL.md` directly — the J:\Hermes\SOUL.md copy is
kept as a project-level artifact, not the live config.

**Regression test**: none yet. The next session's hermes load path
is the only verification.

---

## Bug10 — Codex `cache_write_tokens` hard-coded to 0

**Severity: critical — user-visible cost impact, single-line fix.**

`agent/codex_runtime.py:166` was:

```python
canonical_usage = CanonicalUsage(
    ...
    cache_write_tokens=0,   # <-- always 0
    ...
)
```

The upstream Codex app-server protocol returns
`usage.cacheWriteInputTokens` whenever a cache prefix is created.
Hermes was ignoring this field and hard-coding 0. As a result:

- `session_cache_write_tokens` was always 0 across every session.
- `prompt_caching` cost calculations under-counted cache-creation
  cost (billed at 1.25× input on Anthropic).
- The `cache_read / cache_write` ratio was meaningless in
  diagnostics — a 67M cache_read over 622K input_tok across the
  largest session could not be reasoned about without the
  corresponding write side.

See upstream issue openai/codex#38158 ("Python SDK:
TokenUsageBreakdown is missing the cacheWriteInputTokens field").
This is a known upstream SDK gap; Hermes's wrapper made it worse
by passing the missing field as a literal zero.

**Fix** (one line, plus a defensive coerce):

```python
cache_write_tokens = _coerce_usage_int(usage.get("cacheWriteInputTokens"))
...
canonical_usage = CanonicalUsage(
    ...
    cache_write_tokens=cache_write_tokens,
    ...
)
```

**Regression test**:
`tests/hermes_state/test_hermes_core_bugfixes.py::TestBug10CacheWriteTokens`
pins (a) absence of the literal `cache_write_tokens=0,` in the
module source, (b) presence of the new
`usage.get("cacheWriteInputTokens")` parse, and (c) defensive
coercion of None / string / dict inputs.

---

## Bug8 — SQLite `auto_vacuum=0` (NONE)

**Severity: medium — long-running installs leak disk silently.**

`state.db` was created with the SQLite default `auto_vacuum=0`,
which only marks freed pages as reusable within the same file. The
file size never shrinks. Hermes does compression and message
archival regularly; combined with FTS triggers maintaining secondary
indexes, the file is delete-heavy churn that produces free pages
faster than the page cache absorbs them.

Across this audit, state.db was 9.4 MB and growing; the upper bound
is set only by disk-full, not by any hermes-side guard.

**Fix**: hermes_state.py now sets
`PRAGMA auto_vacuum=2` (INCREMENTAL) at db-init, configurable via
`database.auto_vacuum` in config.yaml (`none` / `full` /
`incremental`, default `incremental`). The pragma cannot be
applied retroactively without a full VACUUM; the new value applies
to the file created next time, and an operator-driven VACUUM is
logged for the existing file.

**Regression test**:
`tests/hermes_state/test_hermes_core_bugfixes.py::TestBug8AutoVacuum`
runs an SQLite behavioural test against `PRAGMA auto_vacuum=INCREMENTAL`
+ `DELETE` + `incremental_vacuum(N)`, asserting the file actually
shrinks — independent of hermes_state internals, so a SQLite
regression would also be caught.

---

## Bug9 — `messages.token_count` NULL for assistant rows

**Severity: low — observability gap.**

Across 714 assistant messages, `token_count` was NULL 100% of
the time. The same data is written into `sessions.input_tokens /
output_tokens / cache_* / reasoning_tokens` aggregates, so the
*per-session* totals are correct — but per-message breakdowns
are not retrievable for post-hoc diagnosis (e.g. "which turn in
session X consumed the most cache_write tokens").

The path is: `_record_codex_app_server_usage` calls
`agent._session_db.queue_token_counts(...)` with token counts as
kwargs; this writes the session-level totals but the per-message
`messages.token_count` is never written because the message row
was already inserted (by `_session_db.append_message` earlier in
the turn) before the API response returned.

**Status: not fixed in this pass.** The fix is to call
`update_message_tokens(message_id, canonical_usage)` after the API
response, threading the message_id through `_record_codex_app_server_usage`.
Marked as known follow-up.

---

## Bug11 — 13/14 sessions have `ended_at IS NULL`

**Severity: low — resource leak, not a correctness issue.**

13 of 14 sessions show `ended_at IS NULL` and `end_reason IS NULL`,
meaning Hermes was not allowed to run the atexit / clean-shutdown
path. The user profile shows these come from window-close (the
tasklist shows hermes processes running normally otherwise).

**Fix**: not a code bug. The user can `exit` / `Ctrl-D` from the
CLI to gracefully close. If running under a process manager
supervisor, configure it to send SIGTERM (not SIGKILL) so the
atexit hook fires.

---

## Bug6 — `web_extract` ddgs backend error message is unhelpful

**Severity: low — UX.**

When the active web-search backend is DuckDuckGo (`ddgs`) and
`web_extract` is called on a URL, the tool returns:

```
DuckDuckGo (ddgs) is a search-only backend and cannot extract
URL content. Set web.extract_backend to firecrawl, keenable, exa,
or parallel.
```

The error message contains the fix but only after the failure has
already wasted a turn. Hermes should detect the case *before*
calling the backend and surface the suggestion upfront, or
auto-fallback to a configured secondary backend.

**Status: not fixed in this pass.** This is a hermes core
behaviour; patching it requires editing
`tools/web_extract.py`'s entry point, which is in the agent-tools
area, not the agent core. Marked as known follow-up.

---

## What was already working

- All 67 skill tests pass (`tests/skills/`).
- `scripts/verify_skill.py` (per-skill self-check) passes for both
  `agent-intelligence` and `swarm-collaboration`.
- CI runs the skill tests (`.github/workflows/tests.yml` step
  added in commit a6a8425456).
- state.db schema is well-formed (no FTS corruption, no missing
  indexes).
- All custom skills resolve via `tools/skills_tool.skill_view()`
  and load via `agent/skill_commands.build_preloaded_skills_prompt()`.
- All work pushed to fork under `feat/agent-intelligence-lite-swarm-and-templates`
  (hash `a6a8425456` pre-bugfix, see follow-up commit for the new
  hash).