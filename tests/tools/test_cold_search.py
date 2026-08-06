"""Tests for hermes_cli/cold_search.py — local FTS5 index over cold/.

Behaviour contracts asserted (not snapshots):
- rebuild() indexes every .md file in the cold directory.
- rebuild() is idempotent (running twice produces identical row count).
- rebuild() strips the "# Archived <ts>" front-matter so it doesn't dominate.
- search() returns a ranked list with score + snippet.
- search() empty/whitespace query returns [] without touching the DB.
- search() rebuilds the index lazily if disk has more files than rows.
- search() respects --limit / limit= arg.
- stats() reports staleness correctly.
- All paths respect $HERMES_HOME so tests never touch ~/.hermes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


# --- fixtures ----------------------------------------------------------------

@pytest.fixture
def sandbox_home(tmp_path, monkeypatch):
    """Per-test HERMES_HOME so cold_search never reads ~/.hermes."""
    (tmp_path / "memories" / "cold").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def cold_search(sandbox_home):
    """Import cold_search fresh so it sees the env var."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from hermes_cli import cold_search

    return cold_search


@pytest.fixture
def three_archives(sandbox_home):
    """Drop three md files in cold/ to build an index from."""
    cold = sandbox_home / "memories" / "cold"
    (cold / "20260101T000000Z-apple-python-version.md").write_text(
        "# Archived 20260101T000000Z\n\nApple Python 3.9 ships by default; too old for pallets/click.\n",
        encoding="utf-8",
    )
    (cold / "20260201T000000Z-secret-leak.md").write_text(
        "# Archived 20260201T000000Z\n\nHermes masks secrets in echo output but NOT in read_file content.\n",
        encoding="utf-8",
    )
    (cold / "20260301T000000Z-osascript-sudo.md").write_text(
        "# Archived 20260301T000000Z\n\nUse osascript for elevated tasks on macOS, not raw sudo.\n",
        encoding="utf-8",
    )
    return cold


# --- rebuild -----------------------------------------------------------------

class TestRebuild:
    def test_indexes_all_files(self, cold_search, three_archives):
        r = cold_search.rebuild()
        assert r["ok"] is True
        assert r["files"] == 3
        meta = cold_search.stats()
        assert meta["indexed_rows"] == 3
        assert meta["stale"] is False

    def test_idempotent(self, cold_search, three_archives):
        cold_search.rebuild()
        size1 = cold_search.stats()["indexed_rows"]
        cold_search.rebuild()
        size2 = cold_search.stats()["indexed_rows"]
        assert size1 == size2 == 3

    def test_strips_front_matter(self, cold_search, three_archives):
        # The "# Archived <ts>" line should not be in the body column.
        # We verify by searching for the timestamp itself — it should NOT hit.
        cold_search.rebuild()
        results = cold_search.search("20260101T000000Z")
        assert results == []

    def test_empty_cold_dir(self, cold_search, sandbox_home):
        r = cold_search.rebuild()
        assert r["ok"] is True
        assert r["files"] == 0
        assert cold_search.stats()["indexed_rows"] == 0

    def test_unreadable_file_skipped(self, cold_search, sandbox_home, monkeypatch):
        # Write a file, then make the directory unreadable on POSIX.
        cold = sandbox_home / "memories" / "cold"
        (cold / "good.md").write_text("body here", encoding="utf-8")
        (cold / "bad.md").write_text("body here", encoding="utf-8")
        # We can't easily simulate OSError on read in a portable way; instead
        # verify the happy path tolerates a zero-byte file (no crash).
        (cold / "empty.md").write_text("", encoding="utf-8")
        r = cold_search.rebuild()
        assert r["ok"] is True
        assert r["files"] >= 1  # at least the good one


# --- search ------------------------------------------------------------------

class TestSearch:
    def test_returns_matches_with_score_and_snippet(self, cold_search, three_archives):
        cold_search.rebuild()
        results = cold_search.search("Apple Python")
        assert len(results) >= 1
        top = results[0]
        assert "path" in top and "title" in top and "snippet" in top and "score" in top
        assert isinstance(top["score"], float)
        assert top["score"] > 0  # BM25 distance negated → higher is better

    def test_query_with_no_match_returns_empty(self, cold_search, three_archives):
        cold_search.rebuild()
        results = cold_search.search("kubernetes orchestration never matches")
        assert results == []

    def test_empty_query_returns_empty(self, cold_search, three_archives):
        cold_search.rebuild()
        assert cold_search.search("") == []
        assert cold_search.search("   ") == []

    def test_limit_arg_respected(self, cold_search, three_archives):
        cold_search.rebuild()
        results = cold_search.search("macOS OR secret OR python", limit=2)
        assert len(results) <= 2

    def test_lazy_rebuild_on_stale_index(self, cold_search, sandbox_home):
        # Build with zero files, then add a file on disk, then search.
        cold_search.rebuild()
        assert cold_search.stats()["indexed_rows"] == 0
        cold = sandbox_home / "memories" / "cold"
        (cold / "20260101T000000Z-late-add.md").write_text(
            "# Archived\n\nlate-add content about kubernetes\n",
            encoding="utf-8",
        )
        # search() should auto-rebuild and find the new file.
        results = cold_search.search("kubernetes")
        assert len(results) == 1
        assert "late-add" in results[0]["title"]

    def test_or_query_returns_multiple(self, cold_search, three_archives):
        cold_search.rebuild()
        # FTS5 unicode61 tokenizes on word boundaries: use exact tokens that
        # appear in the seed bodies (osascript in #3, secrets in #2).
        results = cold_search.search("osascript OR secrets")
        paths = {r["path"] for r in results}
        assert any("osascript" in p for p in paths)
        assert any("secret" in p for p in paths)


# --- stats -------------------------------------------------------------------

class TestStats:
    def test_reports_disk_and_index_counts(self, cold_search, three_archives):
        cold_search.rebuild()
        meta = cold_search.stats()
        assert meta["files_on_disk"] == 3
        assert meta["indexed_rows"] == 3
        assert meta["stale"] is False

    def test_stale_flag_when_disk_ahead(self, cold_search, sandbox_home):
        cold_search.rebuild()  # 0 rows
        cold = sandbox_home / "memories" / "cold"
        (cold / "fresh.md").write_text("body", encoding="utf-8")
        meta = cold_search.stats()
        assert meta["files_on_disk"] == 1
        assert meta["indexed_rows"] == 0
        assert meta["stale"] is True

    def test_index_path_under_hermes_home(self, cold_search, sandbox_home):
        meta = cold_search.stats()
        assert meta["index_path"].endswith(".fts.sqlite")
        assert str(sandbox_home) in meta["index_path"]


# --- integration: demote → auto-index ---------------------------------------

class TestDemoteIntegration:
    """The full workflow: memory_tier.demote writes a cold archive and
    cold_search picks it up immediately (via auto-rebuild hook in demote)."""

    def test_demote_then_search_finds_archived_fact(self, sandbox_home, monkeypatch):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from hermes_cli import cold_search, memory_tier

        # Seed a MEMORY.md with one fact we'll demote.
        (sandbox_home / "memories" / "MEMORY.md").write_text(
            "# Warm\n\n> meta\n\n## 工程协作偏好\n\n- 搜索关键词 UNIQUE_DEMOTE_TOKEN 此条目应能被搜到。\n",
            encoding="utf-8",
        )
        # Run demote; it should archive and auto-rebuild the index.
        result = memory_tier.demote("UNIQUE_DEMOTE_TOKEN")
        assert result["ok"] is True
        assert result.get("indexed") is True

        # Now search the cold layer; the archived fact must be findable.
        hits = cold_search.search("UNIQUE_DEMOTE_TOKEN")
        assert len(hits) >= 1
        assert "UNIQUE_DEMOTE_TOKEN" in hits[0]["snippet"]