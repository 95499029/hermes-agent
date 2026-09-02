# Example Conversation — GitLab Issue Status

Full multi-turn transcript showing how the three questions shape the
agent's tool choice. Use this as a reference pattern, not a script —
the specific tools and calls will change as your MCP catalog changes,
but the structure (Q1 → Q2 → Q3 → single call → cited answer) does not.

---

**User**: What's the status of GitLab issue #1234 in the `payments`
repo?

**Agent (without the framing)**:

> I'll search for it.

```
web_search(query="gitlab payments issue 1234")
```

> Let me click the first result.

```
browser_navigate(url="https://gitlab.example.com/payments/-/issues/1234")
```

> Hmm, looks like a login wall. Let me try via the API.

```
web_search(query="gitlab payments api get_issue 1234")
```

> That gave me some docs, not the issue. Let me try one more thing.

```
browser_navigate(url="https://gitlab.example.com/users/sign_in")
```

> Need a cookie/session to proceed.

Final answer: I couldn't reach the issue without logging in. You can
check it at `https://gitlab.example.com/payments/-/issues/1234`.

Burned: 4 tool calls, ~3,200 tokens, no answer.

---

**Agent (with the framing)**:

> Q1 — Context: I need the JSON for one issue — title, state,
> assignee, last update. Single canonical source.

> Q2 — Source: This is the user's own GitLab; I have the `gitlab`
> MCP installed (OAuth-backed). Its `get_issue` endpoint is Tier 2
> (authenticated read) and returns structured data. No need for
> `web_search` or `browser_navigate`.

> Q3 — Blast: read-only. Tier 2 — call directly.

```
gitlab.get_issue(project="payments", id="1234")
```

Returns:

```json
{
  "id": "1234",
  "title": "Refund webhook silently drops on 502",
  "state": "open",
  "assignee": "alice",
  "updated_at": "2026-09-01T14:32:00Z",
  "labels": ["bug", "p1"],
  "url": "https://gitlab.example.com/payments/-/issues/1234"
}
```

Final answer:

> `payments` issue **#1234** — *"Refund webhook silently drops on
> 502"* — is **open**, assigned to @alice, last updated
> 2026-09-01 14:32 UTC. Labels: `bug`, `p1`.
> Source: GitLab MCP, fetched 2026-09-02.
> URL: https://gitlab.example.com/payments/-/issues/1234

Burned: 1 tool call, ~450 tokens, complete answer.

---

## What the framing changed

| Step | Without | With |
|---|---|---|
| Tools used | web_search × 2, browser_navigate × 2 | gitlab.get_issue × 1 |
| Tokens (approx) | ~3,200 | ~450 |
| Answer delivered | No (login wall) | Yes (with citation) |
| Mid-session cache breakage | Yes (browser_navigate reset context once) | No |
| Trust tier followed | None | Tier 2 — read-only authenticated |

The framing costs ~50 words of internal scratch. The savings are 7× on
tokens and 0 vs 1 on answer quality.