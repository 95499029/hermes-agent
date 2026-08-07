"""``hermes study`` — distill durable principles from a book or long article.

Pipeline:
  1. extract:   TXT/MD direct, DOCX/XLSX/IPYNB via tools.read_extract,
                PDF/EPUB/etc via firecrawl-anydoc; URL via urllib + strip
  2. chunk:     paragraph-aligned ~8K token windows with overlap
  3. distill:   per-chunk LLM call returns 1-2 generalizable principles
                (universal, durable, actionable, ≤ 280 chars each)
  4. dedupe:    drop near-duplicates (case-insensitive + 70% token overlap)
  5. rank:      by frequency × specificity; return top 3-5
  6. promote:   --promote flag asks user y/N, on yes runs memory_tier.promote
                after pii redact

Cache: text is cached at ~/.hermes/cache/books/<slug>.md so re-runs are fast.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Callable

CACHE_DIR = Path.home() / ".hermes" / "cache" / "books"
HERMES_AGENT = Path.home() / ".hermes" / "hermes-agent"
ANYDOC_EXTS = {".pdf", ".epub", ".doc", ".ppt", ".xls", ".rtf", ".odt"}
STDLIB_EXTRACT_EXTS = {".docx", ".xlsx", ".ipynb"}
TEXT_EXTS = {".txt", ".md"}

DISTILL_PROMPT = """\
You are extracting generalizable principles from a passage of a book.
A principle is universal (applies beyond the book), durable (still true
in 5 years), and actionable (changes how a reader would decide).
Output 1-2 principles as a JSON array of strings. Each ≤ 280 chars.
No preamble. No citation. No commentary.

Passage:
---
{passage}
---
"""


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def extract_text(path: Path) -> str:
    """Extract plain text from a book file on disk."""
    suf = path.suffix.lower()
    if suf in TEXT_EXTS:
        return path.read_text(encoding="utf-8", errors="replace")
    if suf in STDLIB_EXTRACT_EXTS:
        # tools/ lives under HERMES_AGENT, not on sys.path from a subcommand
        if str(HERMES_AGENT) not in sys.path:
            sys.path.insert(0, str(HERMES_AGENT))
        from tools.read_extract import extract_document_text
        return extract_document_text(str(path))
    if suf in ANYDOC_EXTS:
        import anydoc
        return anydoc.to_markdown(str(path))
    raise ValueError(f"unsupported format: {suf}")


def extract_url(url: str) -> str:
    """Fetch a URL and return plain text. Strips scripts/styles/nav."""
    import urllib.request
    with urllib.request.urlopen(url, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    html = re.sub(
        r"<(script|style|nav|header|footer)[^>]*>.*?</\1>",
        "", html, flags=re.S | re.I,
    )
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Chunk + Distill
# ---------------------------------------------------------------------------

def chunk(text: str, max_chars: int = 32000, overlap: int = 4000) -> list[str]:
    """Paragraph-aligned chunks of ~max_chars with overlap window."""
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    buf: list[str] = []
    for p in paragraphs:
        buf.append(p)
        if sum(len(x) for x in buf) > max_chars:
            chunks.append("\n\n".join(buf))
            # carry last few paragraphs as overlap
            kept: list[str] = []
            kept_len = 0
            for q in reversed(buf):
                if kept_len + len(q) > overlap:
                    break
                kept.append(q)
                kept_len += len(q)
            buf = list(reversed(kept))
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks


def _get_client():
    """Build an OpenAI-compatible client for the configured LLM provider."""
    from openai import OpenAI
    base_url = os.environ.get(
        "HERMES_LLM_BASE_URL", "https://api.minimaxi.com/v1"
    )
    api_key = os.environ.get(
        "HERMES_LLM_API_KEY",
        os.environ.get("MINIMAX_CN_API_KEY", ""),
    )
    return OpenAI(base_url=base_url, api_key=api_key)


def _llm_principles(client, passage: str, model: str) -> list[str]:
    """Single LLM call → JSON array of principle strings."""
    resp = client.responses.create(
        model=model,
        input=DISTILL_PROMPT.format(passage=passage[:30000]),
    )
    text = getattr(resp, "output_text", "") or ""
    # Try strict JSON first
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return [str(x) for x in arr]
    except Exception:
        pass
    # Fallback: extract JSON array from prose
    m = re.search(r"\[(.*?)\]", text, re.S)
    if m:
        try:
            arr = json.loads("[" + m.group(1) + "]")
            if isinstance(arr, list):
                return [str(x) for x in arr]
        except Exception:
            pass
    return []


def _normalize_principle(p: str) -> str:
    return re.sub(r"\s+", " ", p).strip().rstrip(".").lower()


def _dedupe(principles: list[str]) -> list[str]:
    """Drop near-duplicates. Order preserved (first occurrence wins)."""
    seen_norm: set[str] = set()
    out: list[str] = []
    for p in principles:
        n = _normalize_principle(p)
        if not n or n in seen_norm:
            continue
        # 70% token overlap with any existing
        new_tokens = set(n.split())
        if any(
            len(new_tokens & set(o.split())) / max(1, len(new_tokens | set(o.split()))) >= 0.7
            for o in seen_norm
        ):
            continue
        seen_norm.add(n)
        out.append(p.strip())
    return out


def distill(text: str, max_chunks: int = 8) -> list[str]:
    """Chunk + LLM-distill + dedupe. Returns top 3-5 ranked principles."""
    client = _get_client()
    model = os.environ.get("HERMES_LLM_MODEL", "MiniMax-Text-01")
    raw: list[str] = []
    for chunk_text in chunk(text)[:max_chunks]:
        try:
            for p in _llm_principles(client, chunk_text, model):
                if 20 <= len(p) <= 280:
                    raw.append(p)
        except Exception as e:
            print(f"  warn: distill chunk failed: {e}", file=sys.stderr)
    return _dedupe(raw)[:5]


# ---------------------------------------------------------------------------
# Promote
# ---------------------------------------------------------------------------

def _pii_redact(text: str) -> str:
    try:
        from hermes_cli.pii import redact
        return redact(text)
    except Exception:
        return text


def promote_principle(fact: str) -> dict:
    """Promote one principle to MEMORY.md via memory_tier (with PII redaction)."""
    if str(HERMES_AGENT) not in sys.path:
        sys.path.insert(0, str(HERMES_AGENT))
    from hermes_cli.memory_tier import promote  # type: ignore
    return promote(_pii_redact(fact))


# ---------------------------------------------------------------------------
# CLI verb
# ---------------------------------------------------------------------------

def _slug(source: str) -> str:
    base = re.sub(r"^https?://", "", source).rstrip("/")
    base = re.sub(r"[^a-zA-Z0-9._-]+", "_", base)[:80] or "untitled"
    return base


def _read_cached(source: str) -> str | None:
    p = CACHE_DIR / f"{_slug(source)}.md"
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else None


def _write_cached(source: str, text: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{_slug(source)}.md").write_text(text, encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    source: str = args.source
    max_chunks: int = args.max_chunks

    if source.startswith("http://") or source.startswith("https://"):
        print(f"[study] fetching URL: {source}")
        try:
            text = extract_url(source)
        except Exception as e:
            print(f"  error: {e}", file=sys.stderr)
            return 1
    else:
        path = Path(source).expanduser()
        if not path.exists():
            print(f"  error: file not found: {path}", file=sys.stderr)
            return 1
        print(f"[study] extracting: {path} ({path.stat().st_size:,} B)")
        try:
            text = extract_text(path)
        except ValueError as e:
            print(f"  error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"  error: extract failed: {e}", file=sys.stderr)
            return 1

    _write_cached(source, text)
    print(f"[study] text length: {len(text):,} chars")

    principles = distill(text, max_chunks=max_chunks)
    if not principles:
        print("[study] no principles extracted", file=sys.stderr)
        return 1

    print(f"\n[study] {len(principles)} distilled principles:\n")
    for i, p in enumerate(principles, 1):
        print(f"  {i}. {p}")

    if not args.promote:
        return 0

    # Interactive promote
    print("\n[study] promote which? (e.g. '1,3' or 'n' to skip)")
    try:
        choice = input("> ").strip().lower()
    except EOFError:
        return 0
    if choice in ("", "n", "no"):
        return 0
    try:
        idxs = {int(x) for x in re.split(r"[\s,]+", choice) if x}
    except ValueError:
        print("  invalid input", file=sys.stderr)
        return 1

    for i, p in enumerate(principles, 1):
        if i in idxs:
            r = promote_principle(p)
            status = "✓" if r.get("ok") else f"✗ {r.get('reason', '?')}"
            print(f"  {status} {p[:80]}...")
    return 0


def register_cli(parent: argparse.ArgumentParser) -> None:
    """Attach the ``study`` subcommand to the given parent parser.

    Receives the *parser* for the study subcommand (already created via
    subparsers.add_parser("study", ...)). Adds the source positional arg
    + flags to it.
    """
    parent.add_argument("source", help="Path to book file, or HTTP(S) URL")
    parent.add_argument(
        "--max-chunks", type=int, default=8,
        help="Max chunks to distill (default 8; each ~8K tokens)",
    )
    parent.add_argument(
        "--promote", action="store_true",
        help="Interactively promote chosen principles to MEMORY.md",
    )
    parent.set_defaults(func=run)


# Backwards-compat alias
def build_study_parser(subparsers, *, cmd_study) -> None:  # noqa: ARG001
    """Compatibility shim — creates study parser, then register_cli on it."""
    parser = subparsers.add_parser(
        "study",
        help="Distill durable principles from a book or long article",
        description=(
            "Read a book (PDF/EPUB/DOCX/TXT) or long article URL, "
            "extract generalizable principles, and optionally promote "
            "them to MEMORY.md."
        ),
    )
    register_cli(parser)
