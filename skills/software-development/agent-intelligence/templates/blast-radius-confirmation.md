# Blast Radius Confirmation

For **Tier 4** (remote write) and **Tier 5** (destructive) calls,
the user needs to confirm the blast radius. Use this checklist before
asking for approval.

## Pre-confirmation checklist (Hermes fills this in)

```
[ ] Action verb + resource + system:
    <verb> <resource> in <system> via <auth path>
[ ] Current state (read back before change):
    <state>
[ ] Target state:
    <state>
[ ] Reversible?
    yes  → how: <rollback steps>
    no   → why: <reason>
[ ] Blast radius:
    other people affected: <count or scope>
    other systems affected: <names>
    data affected: <rows / records / files>
    money affected: <amount or "none">
[ ] Trust tier: 4 or 5
[ ] Approval pattern: <one confirmation per call>
```

## Example: Tier 4 — GitLab MR

```
[ ] Action verb + resource + system:
    create MR in gitlab/payments targeting main, by merging feature/dns-fix
[ ] Current state:
    branch feature/dns-fix has 3 commits, all CI green, latest push 2026-09-01 16:42 UTC
[ ] Target state:
    MR #124 open with reviewers @alice and @bob assigned, label "ready-for-review"
[ ] Reversible?
    yes  → how: close MR; git push origin :feature/dns-fix to delete the branch
[ ] Blast radius:
    other people affected: 2 reviewers notified
    other systems affected: none
    data affected: none (no DB writes)
    money affected: none
[ ] Trust tier: 4
[ ] Approval pattern: one confirmation, one call
```

User reply: "go".

## Example: Tier 5 — drop table

```
[ ] Action verb + resource + system:
    DROP TABLE staging.webhook_events_2024 in postgres-staging via psql
[ ] Current state:
    table exists, ~ 47 million rows, last backup 2026-08-31 03:00 UTC
[ ] Target state:
    table removed, related views fail with "relation does not exist" until re-created
[ ] Reversible?
    yes  → how: pg_restore from 2026-08-31 backup; ~ 2 hours downtime
    no   → data from 2026-09-01 onwards is lost with the drop
[ ] Blast radius:
    other people affected: 3 engineers depending on staging dashboards
    other systems affected: any downstream view selecting from this table
    data affected: ~ 1.4 million rows (Sep 1-2)
    money affected: none
[ ] Trust tier: 5
[ ] Approval pattern: per-action human approval
```

User reply: "yes, do it".

## Anti-pattern: vague blast radius

> Blast radius: probably small.

Always be specific. Counts, names, scope. The user decides based on
your numbers, not your intuition.

## Anti-pattern: hiding reversibility

> Reversible: yes.

How? In how many steps? How long does it take? If rollback needs a
four-person manual process, that's effectively **not reversible**.
Say so.