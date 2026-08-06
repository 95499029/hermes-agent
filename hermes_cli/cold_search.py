"""Cold-layer (历史层) full-text search over ~/.hermes/memories/cold/.

Naming note: the directory on disk is still called `cold/` for backward
compatibility with any existing tools that hardcode the path. In user-facing
strings (CLI output, docs) we call this the "历史层" (history/archive tier)
per the local Tiered Memory architecture. New code should use the term
"历史层" in user-facing strings; the file/column/directory names stay.

A tiny local FTS5 index lives at ~/.hermes/memories/cold/.fts.sqlite.
We build it from the *.md archive files written by memory_tier.demote()
and refresh it lazily on every search call (cheap because N is small — the
typical history tier has tens of files, not thousands).

Why not pull in a vector plugin? The design doc calls for hybrid search
(BM25 + vector) but the 通用层 memory in this codebase is small and
high-signal; BM25 over the 历史层 gives 90% of the value with zero
external dependency. We can add a vector layer (e.g. sqlite-vss or the
``holographic`` plugin) later without changing this module's contract.

Public API:
    search(query, limit=10) -> list[dict]
    rebuild()              -> {"ok": True, "files": N}
"""
from __future__ import annotations

import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()


def _hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    return Path(env) if env else Path.home() / ".hermes"


def _cold_dir() -> Path:
    d = _hermes_home() / "memories" / "cold"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path() -> Path:
    return _cold_dir() / ".fts.sqlite"


def _connect() -> sqlite3.Connection:
    """Open the cold FTS5 DB, creating schema if missing."""
    p = _index_path()
    conn = sqlite3.connect(p, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    with _LOCK:
        conn.executescript(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS cold_fts USING fts5(
                path UNINDEXED,
                title UNINDEXED,
                body,
                tokenize = 'unicode61 remove_diacritics 2'
            );
            """
        )
        conn.commit()
    return conn


def _strip_frontmatter(body: str) -> str:
    """Drop the `# Archived <ts>` first line so it doesn't dominate queries."""
    lines = body.split("\n", 1)
    if len(lines) > 1 and lines[0].lstrip().startswith("# Archived"):
        return lines[1]
    return body


def rebuild() -> dict:
    """Re-index every .md in cold/. Idempotent — drops & rebuilds.

    Returns a small status dict. Safe to call repeatedly; the work is bounded
    by the file count in cold/ which is typically tens.
    """
    cold = _cold_dir()
    files = sorted(p for p in cold.glob("*.md"))
    conn = _connect()
    try:
        with _LOCK:
            conn.execute("DELETE FROM cold_fts")
            indexed = 0
            for path in files:
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                # Strip the front matter so it doesn't dominate queries.
                title = path.stem  # filename without .md (timestamp-slug form)
                body = _strip_frontmatter(text)
                # PII redact before indexing so secrets don't leak into the
                # full-text search index or BM25 snippets.
                from hermes_cli import pii as _pii
                body = _pii.redact(body)[0]
                conn.execute(
                    "INSERT INTO cold_fts(path, title, body) VALUES (?, ?, ?)",
                    (path.name, title, body),
                )
                indexed += 1
            conn.commit()
    finally:
        conn.close()
    return {"ok": True, "files": indexed, "index_size": _index_path().stat().st_size}


def search(query: str, limit: int = 10) -> list[dict]:
    """BM25-ranked full-text search over 历史层 archives.

    Returns a list of dicts with: path, title, snippet, score. Empty result
    list if the query is empty or no matches.

    Side effect: ensures the index is up-to-date before searching. We rebuild
    on first call when the index is stale (file count on disk > index rows).

    Note on FTS5 query syntax: hyphens, asterisks and parentheses are
    operators in FTS5's MATCH expression. We wrap the user query in double
    quotes (phrase syntax) only when the raw query contains operator
    characters, otherwise we pass it through so multi-word AND/OR-style
    queries still work as the user wrote them.
    """
    if not query or not query.strip():
        return []
    raw = query.strip()
    # Only wrap in quotes if the query contains operator characters that
    # would be parsed as FTS5 syntax (NOT keywords like OR/AND — those are
    # intentional user input).
    needs_phrase = bool(re.search(r"[-*()]", raw))
    safe = f'"{raw.replace(chr(34), chr(34)*2)}"' if needs_phrase else raw
    cold = _cold_dir()
    on_disk = sum(1 for _ in cold.glob("*.md"))
    conn = _connect()
    try:
        # Cheap staleness check: if disk has more files than the index, rebuild.
        row = conn.execute("SELECT COUNT(*) FROM cold_fts").fetchone()
        if on_disk > row[0]:
            rebuild()
            conn = _connect()  # reopen against fresh state
        # BM25 ranking: -bm25() returns negative scores; smaller = better match.
        # We strip the leading "-" and pass it through as a positive "score".
        rows = conn.execute(
            "SELECT path, title, snippet(cold_fts, 2, '«', '»', '…', 16) AS snippet, "
            "       -bm25(cold_fts) AS score "
            "FROM cold_fts "
            "WHERE cold_fts MATCH ? "
            "ORDER BY score DESC LIMIT ?",
            (safe, limit),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "path": r["path"],
            "title": r["title"],
            "snippet": r["snippet"],
            "score": round(r["score"], 4),
        }
        for r in rows
    ]


def stats() -> dict:
    """Quick health-check stats for the 历史层."""
    cold = _cold_dir()
    on_disk = sum(1 for _ in cold.glob("*.md"))
    index_exists = _index_path().exists()
    indexed_rows = 0
    if index_exists:
        try:
            conn = _connect()
            indexed_rows = conn.execute("SELECT COUNT(*) FROM cold_fts").fetchone()[0]
            conn.close()
        except sqlite3.Error:
            pass
    return {
        "files_on_disk": on_disk,
        "indexed_rows": indexed_rows,
        "stale": on_disk != indexed_rows,
        "index_path": str(_index_path()),
    }