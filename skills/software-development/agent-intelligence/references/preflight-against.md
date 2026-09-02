# Failure Modes the Skill is Built to Prevent

This file documents the **failure patterns** the agent-intelligence
skill exists to prevent. Each entry names a class of mistake, not a
specific incident. Use it as a checklist when reviewing your own
work, or when training another agent on the skill.

The point is that these are **patterns** — they keep happening
across sessions, across users, across task types. Knowing the
specific session that exhibited one is less useful than knowing
the shape it takes, so you can recognise it the next time.

---

## Tier 1 — read-only public

### Mode 1.1 — Recency-as-authority

> "According to <vendor docs URL>..." — but the docs describe
> version 4.2 and you're on version 3.8.

**Shape**: the model cites a primary source that describes the
latest stable release, then applies it to a context running an
older version. The citation looks correct; the answer is wrong.

**Defence**: confirm the version selector in the URL matches the
running version. If it doesn't, fall back to a Tier 1 source that
documents the older version (changelogs, archived docs,
`git log` on the upstream).

### Mode 1.2 — Marketing-as-truth

> "Setting up OAuth is easy with our SDK — just call `oauth.init()`
> and you're done!"

**Shape**: vendor docs overstate ease-of-use and understate
failure modes. The tutorial path glosses over auth refresh, rate
limits, pagination, and corner cases. The agent takes the
"happy path" and fails in production.

**Defence**: read the **reference** page, not the tutorial. Look
for "limitations" and "errors" sections explicitly.

---

## Tier 2 — read-only authenticated

### Mode 2.1 — MCP default vs production

> "I'll just call `gitlab.get_issue(id=1234)` — that's what the
> MCP exposes."

**Shape**: the MCP defaults to a sensible endpoint (often
`gitlab.com` or a staging instance). Production has a private
GitLab behind SSO. The agent picks the obvious tool name and
silently hits the wrong host.

**Defence**: when an MCP first exposes both a public and a private
target, the skill says "trust the catalogue entry that matches
your network", not "trust the most obvious endpoint".

### Mode 2.2 — Token scope creep

> "I have a read token, but `git push` is also a `git` command — let
> me just try."

**Shape**: a read-only token is good for `git_log`, `git_diff`, and
`git_show`. The agent pattern-matches the `git` prefix and
attempts `git push`, which 403s. The agent retries with the
same token, gets the same 403, and surfaces a confusing error.

**Defence**: classify every tool call by trust tier **before**
attempting. Tier 2 means "read-only authenticated" — push is not
in that set.

---

## Tier 3 — local sandbox write

### Mode 3.1 — Diff-blind edit

> "I'll fix this by patching the file." *patches the wrong file*.

**Shape**: agent reads the codebase to find the issue, identifies
a likely file, edits it — without showing the diff first. The
edit goes to a wrong file because the codebase has duplicates
(e.g. `service/v2/foo.py` and `service/v3/foo.py`), and the
agent picked the wrong one.

**Defence**: Tier 3 contract says "show diff, then call, then
sanity-check". Diff preview catches file selection errors
because the developer sees the path.

### Mode 3.2 — Test blindness

> "I edited the function; I'm sure it's right."

**Shape**: agent makes a code change but does not run the tests
because "the change is small". A test fails because the change
broke an unrelated invariant. Production sees the regression
later.

**Defence**: Tier 3 says "sanity-check after". For Python code,
"run pytest on the touched module" is the cheapest sanity check.
For JS, "run the linter + type-checker".

---

## Tier 4 — remote write

### Mode 4.1 — Confirmation theatre

> "Updating DNS now."
>
> `cloudflare.update_dns_record(...)` → done.

**Shape**: the agent sends the confirmation and the tool call in
the same breath. The user has no chance to read what changed
because the message is already followed by the call. The call
goes to whatever defaults the MCP chose — often the production
zone, not the staging zone the user asked about.

**Defence**: write the confirmation **first**, wait for the
explicit reply ("go", "yes", "do it"), then call. The agent's
"now" is not the user's "now".

### Mode 4.2 — Cascade blindness

> "Just a small delete — drop the staging record."

**Shape**: the agent sees a delete operation that looks small. The
record has a foreign-key cascade in the database. Dropping the
record triggers three view refreshes, two webhooks, and a
billing-event re-sync. None of this was in the user's brief.

**Defence**: Tier 4 contract says "state blast radius before
call". For deletes specifically, list what depends on the
resource (foreign keys, webhooks, scheduled jobs, billing
events).

### Mode 4.3 — Wrong environment

> "I'll update the alert threshold in Datadog."

**Shape**: Datadog MCP defaults to `prod` if not specified.
The agent doesn't realise and updates the production alert
threshold. The threshold change is innocuous in isolation, but
the next time a real alert fires, the team doesn't notice.

**Defence**: explicitly include the env in the confirmation:
"I'm about to update alert threshold X from Y to Z in env=prod,
via Datadog MCP. Reply go to apply." Env defaults are not the
agent's decision to make.

---

## Tier 5 — destructive

### Mode 5.1 — CASCADE doesn't exist (until it does)

> "DROP TABLE webhook_events_2024 — no foreign keys, safe to drop."

**Shape**: the agent checks the obvious constraints. The database
has a deferred constraint that doesn't show up in the standard
introspection. The drop succeeds; three downstream jobs that
ran every midnight start failing silently. The team notices
two weeks later when a quarterly report comes back wrong.

**Defence**: Tier 5 contract says "verify reversibility, name a
rollback". Even "no foreign keys in introspection" is not the
same as "no downstream effects".

### Mode 5.2 — Auth-then-action

> "I'll just rotate the API key. The user asked me to."

**Shape**: rotating an API key invalidates the old key
immediately. If the user has another service authenticated with
that key (a CI job, a deployed worker, a backup script), they
start failing. The user didn't realise their request would
cascade.

**Defence**: Tier 5 says "per-action human approval, never
batch". For rotations, the confirmation should explicitly ask:
"Are there other services using this key? Have you rotated
those to the new key first?"

---

## Cross-tier patterns

### Mode X.1 — Silent retry

> `tool_call` → error → retry → error → retry → ... → surface.

**Shape**: the agent retries a failed call without changing
anything, hoping the second or third attempt succeeds. This
adds latency and may trigger rate limits. Worse, it hides the
real failure: the call is wrong, not transient.

**Defence**: classify the failure. If it's transient (network
blip, rate limit), retry once with backoff. If it's structural
(the tool is wrong, the argument is wrong), do not retry —
diagnose and re-plan.

### Mode X.2 — Source drift

> "I cited <URL> earlier in this session — let me cite it again."

**Shape**: the agent cites the same URL across multiple turns,
treating it as still valid. But the URL was fetched at session
start; facts on the page may have changed since. By turn 30,
the agent is citing stale information with a 30-turn-old fetch
date.

**Defence**: when citing the same URL again, re-fetch if the
context has shifted (different question, different answer
expected). Don't blindly reuse a stale citation.

### Mode X.3 — Mid-session contract change

> "I just realised agent-intelligence doesn't cover this case;
> I'll add a new tier to the system prompt."

**Shape**: the agent finds a gap in the loaded skill and "fixes"
it by adding new instructions to the system prompt. The change
invalidates the prompt cache and the entire subsequent context
costs more. The skill maintainer, who hadn't intended a new
tier, has to reconcile the divergence.

**Defence**: skill gaps are *not* mid-session fixes. File an
issue, note the gap in the scratchpad, or load a different
skill — but don't mutate the system prompt to "patch" the
skill.

---

## How to use this file

When a session goes wrong, walk down the list of modes and find
the closest match. The match is usually not exact — that's the
point. Once you have a candidate, ask: "what Tier was this
call?" and "what does the Tier X contract say to do about it?".

The match between failure and Tier is the diagnostic. The
defence listed under each mode is the recovery.

For patterns not covered here, add a new mode — but only with a
defence. A failure mode without a defence is just a rant.