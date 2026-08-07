"""Tests for `hermes study` subcommand."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

HERMES_AGENT = Path("/Users/ivan/.hermes/hermes-agent")
sys.path.insert(0, str(HERMES_AGENT))

from hermes_cli.subcommands.study import (  # noqa: E402
    extract_text,
    extract_url,
    chunk,
    _dedupe,
    _normalize_principle,
    build_study_parser,
    CACHE_DIR,
)


# ---------------------------------------------------------------------------
# extract_text
# ---------------------------------------------------------------------------

def test_extract_text_handles_txt_path(tmp_path):
    p = tmp_path / "book.txt"
    p.write_text("Hello world.\n\nChapter two begins here.", encoding="utf-8")
    result = extract_text(p)
    assert "Hello world" in result
    assert "Chapter two" in result


def test_extract_text_handles_md_path(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("# Title\n\nSome **bold** text.", encoding="utf-8")
    result = extract_text(p)
    assert "Title" in result
    assert "bold" in result


def test_extract_text_unsupported_format_raises(tmp_path):
    p = tmp_path / "weird.xyz"
    p.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported format"):
        extract_text(p)


# ---------------------------------------------------------------------------
# extract_url
# ---------------------------------------------------------------------------

def test_extract_url_strips_scripts_and_tags(monkeypatch):
    html = (
        "<html><head><style>body{color:red}</style></head>"
        "<body><h1>Title</h1><p>Real content here.</p>"
        "<script>alert('hide me')</script></body></html>"
    )
    fake_resp = MagicMock()
    fake_resp.read.return_value = html.encode("utf-8")
    fake_resp.__enter__ = lambda self: self
    fake_resp.__exit__ = lambda self, *a: False
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda url, timeout=30: fake_resp
    )
    result = extract_url("http://example.com/page")
    assert "Title" in result
    assert "Real content" in result
    assert "alert" not in result
    assert "color:red" not in result


# ---------------------------------------------------------------------------
# chunk
# ---------------------------------------------------------------------------

def test_chunk_short_text_returns_one_chunk():
    text = "paragraph one.\n\nparagraph two."
    out = chunk(text, max_chars=1000, overlap=100)
    assert len(out) == 1
    assert "paragraph one" in out[0]


def test_chunk_splits_long_text_at_paragraph_boundary():
    paras = [f"paragraph {i} " + "x" * 100 for i in range(50)]
    text = "\n\n".join(paras)
    out = chunk(text, max_chars=2000, overlap=200)
    assert len(out) >= 2
    # Each chunk is a substring of original
    for c in out:
        assert c in text


# ---------------------------------------------------------------------------
# dedupe
# ---------------------------------------------------------------------------

def test_dedupe_drops_exact_duplicates():
    out = _dedupe([
        "Always test first.",
        "always test first",
        "Other principle.",
    ])
    assert len(out) == 2


def test_dedupe_drops_near_duplicates_via_token_overlap():
    out = _dedupe([
        "Always test code first before writing more.",
        "Always test code first before writing more code.",
        "Prefer composition over inheritance.",
    ])
    # first two collapse into one (70%+ token overlap)
    assert len(out) == 2


def test_normalize_principle_strips_punctuation_and_case():
    assert _normalize_principle("Hello World.") == "hello world"
    assert _normalize_principle("  Multiple   spaces  ") == "multiple spaces"


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def test_build_study_parser_attaches_to_subparsers():
    import argparse
    top = argparse.ArgumentParser()
    sub = top.add_subparsers()
    # build_study_parser creates the parser + calls register_cli
    from hermes_cli.subcommands.study import build_study_parser
    build_study_parser(sub, cmd_study=MagicMock())
    parsed = top.parse_args(["study", "book.pdf"])
    assert parsed.source == "book.pdf"
    assert parsed.max_chunks == 8
    assert parsed.promote is False


def test_build_study_parser_promote_flag():
    import argparse
    top = argparse.ArgumentParser()
    sub = top.add_subparsers()
    from hermes_cli.subcommands.study import build_study_parser
    build_study_parser(sub, cmd_study=MagicMock())
    parsed = top.parse_args(["study", "--promote", "book.epub"])
    assert parsed.promote is True
    assert parsed.source == "book.epub"


def test_register_cli_attaches_args_to_existing_parser():
    """register_cli receives the study subparser (already created) and adds args."""
    import argparse
    from hermes_cli.subcommands.study import register_cli
    parent = argparse.ArgumentParser()
    register_cli(parent)
    parsed = parent.parse_args(["some-book.pdf"])
    assert parsed.source == "some-book.pdf"
    assert parsed.max_chunks == 8
    assert parsed.promote is False


# ---------------------------------------------------------------------------
# distill (mocked LLM)
# ---------------------------------------------------------------------------

def test_distill_returns_deduped_principles(monkeypatch):
    from hermes_cli.subcommands import study as study_mod

    class FakeResp:
        output_text = json.dumps([
            "Always write tests first.",
            "Prefer composition over inheritance.",
        ])

    class FakeClient:
        def responses_create(self, model, input):
            return FakeResp()
        class responses:
            create = lambda self, model, input: FakeResp()

    fake = FakeClient()
    monkeypatch.setattr(study_mod, "_get_client", lambda: fake)

    out = study_mod.distill("paragraph one " * 100, max_chunks=1)
    # mocked client returns same pair for every chunk call; dedupe collapses them
    assert isinstance(out, list)
    assert all(isinstance(p, str) for p in out)
    assert all(20 <= len(p) <= 280 for p in out)
