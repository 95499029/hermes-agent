# Source Ranking Heuristics

The source ranking in SKILL.md gives you four tiers in order of
trustworthiness: **live primary > crawler-grade > search-aggregated >
training-data recall**. This document gives concrete heuristics for
recognising each tier in the wild and for switching tiers mid-task
when your first choice fails.

## Tier 1 — Live primary source

**Recognition**: a domain you associate with the producer of the
information, and a URL whose path names the specific resource.

- `docs.python.org/3.13/library/asyncio-task.html` (Python project
  docs)
- `github.com/<owner>/<repo>/blob/<sha>/<path>` (the actual source
  file in the repo at a pinned commit)
- `pypi.org/project/<pkg>/#history` (release history)
- `registry.npmjs.org/<pkg>` (raw package metadata)
- `<vendor>.com/api/v1/...` if it's the vendor's own canonical API
- The project README on its own GitHub repo

**Heuristic**: if the URL is on a domain controlled by the producer
**and** the path names a specific resource, it's Tier 1.

**Failure mode**: the page is JS-rendered and `web_extract` returns
nothing. Try:
1. A JSON endpoint on the same domain (look for `<link rel="alternate"
   type="application/json">` or `__NEXT_DATA__` / `__INITIAL_STATE__`
   patterns)
2. The same resource on a static mirror (e.g. `raw.githubusercontent.com`
   for GitHub files)
3. The package's tarball `*.json` schema file (npm, PyPI, crates.io)

## Tier 2 — Crawler-grade secondary

**Recognition**: a URL you got from a search result, but on a domain
you've decided is stable enough to trust as a source for *this*
question.

- An MDN page for a web API
- A Stack Overflow answer with high votes and recent activity, when
  the question matches your situation closely
- A blog post by a maintainer of the project
- A reputable mirror (`developer.mozilla.org`, `learnxinyminutes.com`,
  official language tour sites)

**Heuristic**: it's not Tier 1 because it's not the producer, but it
is Tier 2 because it cites Tier 1 or has a reputation for accuracy.

**Failure mode**: the source is outdated. Cross-check against Tier 1
if you can — Tier 2 should mostly agree with Tier 1 when Tier 1 is
available.

## Tier 3 — Search-aggregated

**Recognition**: a URL returned by `web_search` without you clicking
through to verify it. You're trusting the search engine's ranking.

**Heuristic**: any URL you haven't independently verified fits here.
This is *discovery*, not *answer* — `web_search` finds candidates; you
then promote one to Tier 1 or Tier 2 by reading it.

**Failure mode**: the search result is itself wrong, or summarises
something outdated. Always follow up with a Tier 1 / Tier 2 read
before committing to the answer.

## Tier 4 — Training-data recall

**Recognition**: no URL — the answer is coming from the model's
parametric memory.

**Heuristic**: if you cannot or will not produce a citation URL,
you're here. This is fine for general knowledge (basic algorithms,
common language features, well-established idioms) and dangerous for
anything that has changed in the last 12-24 months (library API
signatures, pricing, policies, security advisories, model versions).

**Failure mode**: the model doesn't know it doesn't know. A confident
wrong answer looks the same as a confident right answer — that's why
you must always try Tier 1 / Tier 2 first.

## When to switch tiers

- **Tier 1 failed → Tier 2**: you can't reach the producer's docs
  but a reputable secondary source has the same information. Cite
  Tier 2 with the date you fetched it.
- **Tier 1 contradicted Tier 4**: defer to Tier 1. Training data is
  stale; the producer is correct.
- **Tier 2 contradicted Tier 1**: re-read Tier 1. If Tier 1 really
  says what Tier 2 says it says, you misread Tier 1.
- **All tiers failed**: say so explicitly. Don't fake a citation.
  "I could not find a live source for this; the following is from
  training-data recall and may be stale" is a perfectly good answer.

## The freshness hint

Whenever you cite Tier 1 or Tier 2, attach the date you fetched it
(`as of 2026-09-02`). Future-you reading the transcript will know
when to re-verify.