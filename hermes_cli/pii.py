"""PII detection + redaction for memory operations.

Lightweight regex-based scrubber for the obvious categories:
- API keys (sk-..., ghp_..., etc.)
- Phone numbers (Chinese mobile)
- National IDs (18-digit Chinese resident ID)
- Email addresses

Used by:
- memory_consolidate.py (cold + warm scan / apply)
- Cold-layer indexer (so the FTS5 index doesn't carry secrets in plain text)
- Promote entry path (best-effort, non-blocking)

This is intentionally cheap and conservative — false positives are OK
(better to redact a phone-shaped number than leak a real one). Anything
more sophisticated (NER, encoders) is out of scope.
"""
from __future__ import annotations

import re

RULES: list[tuple[str, str]] = [
    (r"sk-[A-Za-z0-9_-]{20,}", "[REDACTED_API_KEY]"),
    (r"ghp_[A-Za-z0-9]{20,}", "[REDACTED_API_KEY]"),
    (r"\b\d{17}[\dXx]\b", "[REDACTED_ID]"),
    (r"\b1[3-9]\d{9}\b", "[REDACTED_PHONE]"),
    (r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", "[REDACTED_EMAIL]"),
]

# Compiled once; each rule is its own group so the substitution can pick
# the correct placeholder.
_PATTERN = re.compile("|".join(f"({p})" for p, _ in RULES))
_PLACEHOLDERS = [r[1] for r in RULES]


def redact(text: str) -> tuple[str, int]:
    """Return (redacted_text, replacement_count)."""
    count = 0

    def _sub(m: re.Match) -> str:
        nonlocal count
        count += 1
        for i, grp in enumerate(m.groups()):
            if grp is not None:
                return _PLACEHOLDERS[i]
        return m.group(0)

    return _PATTERN.sub(_sub, text), count


def scan(text: str) -> int:
    """Count PII matches without rewriting."""
    return sum(1 for _ in _PATTERN.finditer(text))


def has_pii(text: str) -> bool:
    return _PATTERN.search(text) is not None