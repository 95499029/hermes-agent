# Source Bias Checklist

The four-tier source ranking in SKILL.md ranks sources by trust, but
trust is not the only axis — **bias** matters too. This checklist
names the systematic biases that each tier is prone to, so you know
when a "trusted" source is still giving you the wrong answer.

## Tier 1 — Live primary source

Biases to watch for:

- **Recency bias**: the docs describe the latest stable version; if
  you're on an older release, the API may have changed. Always check
  the version selector.
- **Marketing bias**: vendor docs overstate ease-of-use and
  understate failure modes. Look for "limitations" sections, not
  just the getting-started page.
- **Tutorial bias**: docs optimised for first-time use often skip
  the harder production scenarios (auth refresh, rate limits,
  pagination edge cases). Read the reference page, not the tutorial.
- **De-emphasis bias**: features that are deprecated or have known
  issues are sometimes quietly moved. Cross-check with the changelog.

## Tier 2 — Crawler-grade secondary

Biases to watch for:

- **Last-write-wins**: blog posts and Stack answers that age poorly
  stay at the top of search results. The vote count is a poor
  freshness signal.
- **Author experience bias**: a tutorial written by an expert often
  assumes context you don't have. "Just do X" skips the years of
  experience that made X obvious to the author.
- **Cargo-cult bias**: solutions popular in one ecosystem get
  copy-pasted into adjacent ecosystems where they don't fit. "Use
  React for this Python problem" is a real failure mode.
- **Drift bias**: MDN, dev.to, and similar sites can lag the spec by
  6-18 months on bleeding-edge features. Prefer the spec for new
  APIs.

## Tier 3 — Search-aggregated

Biases to watch for:

- **SEO spam**: many search results are content farms optimised for
  the query, not the answer. The first result is rarely the best
  one for technical queries.
- **Aggregator bias**: sites that aggregate answers from multiple
  sources often strip the caveats and version specifics.
- **Localised bias**: a search for "Python sort" returns different
  results depending on the search engine's locale and your IP.
  Cross-check at least one alternative.
- **Recency-gaming bias**: some publishers learn what date-sensitive
  queries want and rewrite dates to game the freshness signal.
  Always read the actual page, not the search snippet.

## Tier 4 — Training-data recall

Biases to watch for:

- **Confident wrongness**: recall produces fluent, confident answers
  on topics where the model has no signal. The answer feels right
  because the form is right; the content can be months-to-years
  stale.
- **Mode-collapse bias**: when multiple competing APIs or libraries
  existed in training data, recall tends to pick the most popular
  one rather than the most appropriate. "Use Redis for this" when
  Postgres + LISTEN/NOTIFY would be simpler.
- **Version-agnostic bias**: training data lumps all versions of a
  library together. The model "knows" requests and httpx but may
  not know that httpx replaced requests for async usage in 2020.
- **Sycophancy bias**: when you push back on a recall-based answer,
  the model often agrees with you rather than defending the correct
  position. If you find yourself arguing with recall, fetch a real
  source.

## Cross-cutting biases

These apply no matter what source tier:

- **Confirmation bias**: a source that agrees with your hypothesis
  feels more trustworthy than one that disagrees. Force yourself to
  seek the contradicting source, not just the confirming one.
- **Authority bias**: a Microsoft blog post, a Google research paper,
  and a personal blog post are not the same kind of source. Strip
  the byline and see if the answer still holds.
- **First-source bias**: the first source you find for a topic tends
  to anchor all subsequent reasoning. If you find a contradicting
  source later, give it equal weight, not "well, this other thing
  said X first".
- **Tool-flattery bias**: vendor docs and reference manuals are
  written by the people who built the tool. They will not volunteer
  that the tool is wrong for your use case. Compare against at
  least one Tier 2 source that has no stake.

## How to apply this checklist

When your answer relies on a single source, run this checklist
against that source's tier. When your answer relies on multiple
sources, list each tier's biases and check whether the combined
answer is still net-positive (i.e., the biases don't all point the
same wrong direction).

If you can't check biases because you don't know which tier the
source is in — you've skipped Source question 2. Go back.