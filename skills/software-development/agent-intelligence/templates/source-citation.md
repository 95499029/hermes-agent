# Source Citation Template

For every non-trivial factual claim in a Hermes response, attach a
citation. Use this format:

```
<claim in one sentence>. (Source: <URL>, fetched <YYYY-MM-DD>)
```

## When you need a citation

- API signatures, library version-specific behaviour
- Pricing, billing, quota, tier limits
- Security advisories, CVE references
- Service status, outage history
- Configuration syntax for any external system
- Anything that has likely changed since training

## When you don't need a citation

- Basic language syntax (loops, exceptions, syntax)
- Algorithm descriptions from textbooks
- General programming idioms
- Things the user told you in the same conversation

## How to format

**Single source:**

> Python 3.13's `asyncio.TaskGroup` raises `ExceptionGroup` on child
> cancellation. (Source: https://docs.python.org/3.13/library/asyncio-task.html,
> fetched 2026-09-02)

**Multiple sources agree:**

> Stripe Checkout sessions expire after 24 hours of inactivity.
> (Sources: https://docs.stripe.com/api/checkout/sessions, fetched
> 2026-09-02; https://stripe.com/docs/payments/checkout/sessions,
> fetched 2026-09-02)

**Recalled (cite it as such):**

> I think this used to throw `RecursionError`, but I cannot find a
> current source confirming the behaviour in the latest Python —
> flagging as from training-data recall. Verify against
> https://docs.python.org before relying on it.

## What "fetched" means

The date you ran `web_extract` or `web_search` against the URL, not
the date the URL was published. This is the date the citation becomes
suspect: any later date means re-verify.

## Anti-pattern: dropped citation

> Use `asyncio.TaskGroup(cancel=True)` to cancel all sub-tasks.

What version of Python? What's the actual API? When was this fetched?
**Cite or qualify as recall.** A claim without a citation is a claim
without evidence.

## Anti-pattern: false citation

> According to https://docs.python.org/3.13/asyncio-task.html (fetched
> today)...

But you didn't actually fetch that URL — you wrote the citation to
look authoritative. **Don't do this.** If you didn't fetch, say so:

> Based on training-data recall (no live fetch performed):
> `asyncio.TaskGroup` provides structured concurrency for child
> tasks. Verify at https://docs.python.org/3.13/library/asyncio-task.html
> before relying on this.