# Trust Tier Decision Statement

When you have classified a tool call as **Tier 3, 4, or 5**, you must
state the decision before invoking the tool. Copy the format below,
fill in the placeholders, and let the user see your reasoning.

## Tier 3 — local sandbox write

> **Action**: I'm about to `<verb>` `<path>` — `<one-line summary>`.
> **Reversible**: yes (`git checkout` / `git stash` / re-run install).
> **Risk**: scope is this working directory only.
> Proceeding.

Use this when the change is small, local, and reversible. No approval
gate, but the explicit statement makes the change legible in the
transcript.

## Tier 4 — remote write

> **Action**: I'm about to `<verb>` `<resource>` in `<system>` via
> `<auth path>` — `<one-line summary>`.
> **Current state**: `<read-back-of-the-resource-before-the-change>`.
> **Target state**: `<what-it-will-be-after>`.
> **Reversible**: `<yes/no>` (`<how-to-rollback>`).
> **Blast radius**: `<which-other-people-or-systems-are-affected>`.
> Reply "go" to apply, or describe the change you'd like instead.

Use this for GitLab issues/MRs, Datadog alert changes, Cloudflare DNS,
Notion/Linear task updates, Railway deploys, `git push` to a shared
branch.

## Tier 5 — destructive / irreversible

> **Action**: I'm about to `<verb>` `<resource>` in `<system>` —
> `<one-line summary>`.
> **Current state**: `<read-back>`.
> **Target state**: `<what-it-will-be-after>`.
> **Reversible**: no. `<reason>`.
> **Blast radius**: `<which-people-systems-data-money-are-affected>`.
> **Confirm**: this is a Tier 5 action. Reply "yes, do it" to apply,
> or describe a safer alternative.

Use this for `rm -rf`, force-push, key rotation, billing changes, drop
table, DNS record deletion.

## How to deliver the statement

In the same message that contains the tool call, write the statement
above it as a quote block. Do not bury it in a paragraph — the user
needs to scan-read it. After the user replies, do the read-back
(verify the change landed as expected) and confirm in the same reply.

## Anti-pattern: skipping the statement

> "Updating DNS now."
>
> `cloudflare.update_dns_record(...)` → done.

This is what Tier 4 looks like without the statement. The user
can't tell what changed, can't tell what was rolled back to, can't
tell whether they want to stop it. **Always state first, then call.**

## Anti-pattern: batching Tier 4/5

> "Updating DNS for staging, prod, and dev in one call."

Even if all three are the same kind of change, three production
systems is three separate approvals. One confirmation per call.