# Trust Tier Examples

Each of the five trust tiers from SKILL.md has the same shape: a
**classification**, a **default action**, and **examples** drawn from
real Hermes tool calls. Use this when you're unsure which tier a
candidate call belongs to — match by intent, not by tool name.

## Tier 1 — Read-only public

**Default action**: call immediately.

**What it means**: the call returns information that is already
public, has no authentication, and cannot mutate anything anywhere.

- `web_search` to a search engine
- `web_extract` of a public docs page (vendor docs, public GitHub
  README, public blog post)
- `read_file` on a local doc you don't need to lock
- `search_files` to discover file paths

**Red flag**: if the call requires a cookie, token, or session, it is
*not* Tier 1 — reclassify.

## Tier 2 — Read-only authenticated

**Default action**: call, but verify the data shape on first use.

**What it means**: the call hits an authenticated system but only
reads. It cannot change state on its own.

- MCP `get_*` / `list_*` / `search_*` endpoints (GitLab, Notion,
  Datadog, Linear, etc.)
- `git_log`, `git_diff`, `git_show` against a remote
- `terminal` running `cat`, `grep`, `find`, `head`, `tail`,
  `ls` against local files
- `web_extract` of an internal docs URL behind a VPN (read-only fetch)

**Red flag**: if the endpoint name includes `create`/`update`/`delete`/
`push`/`merge`/`deploy`/`run`, it is *not* Tier 2 — bump up.

## Tier 3 — Write to local sandbox

**Default action**: call, but show diff and sanity-check after.

**What it means**: the call modifies state, but the state is local to
the user's own machine and easily reversible.

- `write_file` / `patch` on files inside the working repo
- `terminal` running `pip install`, `npm install`, `cargo build`
- Running test suites that produce side effects (tmp files, in-memory
  DBs)
- Creating files in `/tmp` or under `.scratch/`

**Red flag**: if the command targets a system path outside the working
repo (`/etc/`, `C:\Windows\`, `~/.ssh/`, remote filesystem), bump to
Tier 4.

## Tier 4 — Write to remote

**Default action**: show the exact change first, get explicit approval,
then call.

**What it means**: the call mutates a system that other people or
production depends on. Errors here have external blast radius.

- GitLab / GitHub create/update merge request or comment
- Datadog update alert threshold or silence monitor
- Railway / Vercel / Cloudflare change DNS, env vars, deploy settings
- Notion / Linear / Asana create or update task
- `terminal` running `git push` to a shared branch
- `terminal` running `kubectl apply`, `terraform apply`,
  `aws s3 cp` (any cloud)

**Red flag**: if the change affects billing, access control, or
authentication, bump to Tier 5.

## Tier 5 — Destructive / irreversible

**Default action**: per-action human approval; never batch.

**What it means**: the call cannot be cleanly undone, or its blast
radius is large enough that a wrong decision is materially costly.

- `rm -rf` / `Remove-Item -Recurse -Force` outside `~/.hermes/.scratch/`
- `git push --force` / `git push origin :branch`
- Database `DROP TABLE`, `DELETE` without WHERE
- Cloudflare / Route53 delete DNS records
- Rotating API keys, OAuth tokens, SSH keys
- Stripe / PayPal refunds or subscription cancellations
- Anything that triggers billing: provisioning GPUs, sending SMS,
  large data egress

**Red flag**: if a "small" change cascades (delete a record → cascade
removes children → cascade triggers webhooks), it is Tier 5 even if
the first action looks small.

## The Default-Unknown Rule

If you genuinely cannot tell which tier a call belongs to, default
to **one tier higher** than your guess. The cost of asking for an
unnecessary confirmation is small; the cost of an unreviewed Tier 4
or Tier 5 mutation is not.

> "I don't know what this tool does in production" is always Tier 4,
> not Tier 1.