"""Tests for `hermes reflect` subcommand."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

HERMES_AGENT = Path("/Users/ivan/.hermes/hermes-agent")
sys.path.insert(0, str(HERMES_AGENT))

from hermes_cli.subcommands.reflect import (  # noqa: E402
    collect_today,
    _parse_iso_date,
    _today_iso,
    _safe_load_json,
    register_cli,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_today_iso_returns_yyyy_mm_dd():
    out = _today_iso()
    assert len(out) == 10
    assert out[4] == "-" and out[7] == "-"
    # parseable
    datetime.strptime(out, "%Y-%m-%d")


def test_parse_iso_date_accepts_iso_and_z_suffix():
    assert _parse_iso_date("2026-08-07") == "2026-08-07"
    assert _parse_iso_date("2026-08-07T12:00:00Z") == "2026-08-07"
    assert _parse_iso_date("2026-08-07T12:00:00+08:00") == "2026-08-07"
    assert _parse_iso_date("garbage") is None


def test_safe_load_json_returns_empty_on_missing_file(tmp_path):
    p = tmp_path / "nonexistent.json"
    assert _safe_load_json(p) == {}


def test_safe_load_json_returns_empty_on_corrupt(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("not json", encoding="utf-8")
    assert _safe_load_json(p) == {}


# ---------------------------------------------------------------------------
# collect_today
# ---------------------------------------------------------------------------

def test_collect_today_returns_required_keys(monkeypatch):
    """Even with no data, collect_today returns the documented schema."""
    from hermes_cli.subcommands import reflect as r

    monkeypatch.setattr(r, "_read_journey_today", lambda: [])
    monkeypatch.setattr(r, "_read_memory_today", lambda: {"added": [], "demoted": []})
    monkeypatch.setattr(r, "_read_curator_state", lambda: {"runs": 0, "last_run_at": None})
    monkeypatch.setattr(r, "_read_skills_used_today", lambda: [])

    out = collect_today()
    assert set(out.keys()) == {
        "date",
        "journey_count",
        "memories_added",
        "memories_demoted",
        "skills_used",
        "curator_state",
    }
    assert isinstance(out["journey_count"], int)
    assert isinstance(out["memories_added"], list)
    assert isinstance(out["memories_demoted"], list)
    assert isinstance(out["skills_used"], list)
    assert isinstance(out["curator_state"], dict)


def test_collect_today_counts_todays_journey(monkeypatch):
    from hermes_cli.subcommands import reflect as r

    fake_today = "2026-08-07"
    monkeypatch.setattr(r, "_today_iso", lambda: fake_today)
    # Mock raw journey loader to return 3 nodes; the real _read_journey_today
    # then filters by today's date. Override it with a filtered version so
    # the test isolates collect_today's behavior.
    raw = [
        {"id": "skill:a", "created_at": f"{fake_today}T01:00:00Z"},
        {"id": "skill:b", "created_at": f"{fake_today}T02:00:00Z"},
        {"id": "skill:c", "created_at": "2026-08-06T23:00:00Z"},
    ]
    def fake_journey_today():
        return [n for n in raw if r._parse_iso_date(n.get("created_at")) == fake_today]
    monkeypatch.setattr(r, "_read_journey_today", fake_journey_today)
    monkeypatch.setattr(r, "_read_memory_today", lambda: {"added": ["f1"], "demoted": []})
    monkeypatch.setattr(r, "_read_curator_state", lambda: {"runs": 3, "last_run_at": "2026-08-07T01:00:00Z"})
    monkeypatch.setattr(r, "_read_skills_used_today", lambda: ["skill:a"])

    out = collect_today()
    assert out["date"] == fake_today
    assert out["journey_count"] == 2  # 2 of 3 are today (a, b)
    assert out["memories_added"] == ["f1"]
    assert out["skills_used"] == ["skill:a"]
    assert out["curator_state"]["runs"] == 3


def test_read_journey_today_handles_missing_file(tmp_path, monkeypatch):
    """If ~/.hermes/journey.json doesn't exist, return empty list."""
    from hermes_cli.subcommands import reflect as r
    monkeypatch.setattr(r, "JOURNEY_PATH", tmp_path / "missing.json")
    assert r._read_journey_today() == []


def test_read_memory_today_diff_state(tmp_path, monkeypatch):
    """If no .last_consolidate marker, return empty diff."""
    from hermes_cli.subcommands import reflect as r
    monkeypatch.setattr(r, "HERMES_HOME", tmp_path)
    out = r._read_memory_today()
    assert out == {"added": [], "demoted": []}


def test_read_curator_state_handles_missing(tmp_path, monkeypatch):
    from hermes_cli.subcommands import reflect as r
    monkeypatch.setattr(r, "CURATOR_STATE", tmp_path / "missing.json")
    assert r._read_curator_state() == {}


def test_read_skills_used_today_no_op_when_no_skills_log(tmp_path, monkeypatch):
    from hermes_cli.subcommands import reflect as r
    monkeypatch.setattr(r, "SKILLS_USAGE_LOG", tmp_path / "missing.jsonl")
    assert r._read_skills_used_today() == []


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def test_register_cli_attaches_today_to_subparser():
    """register_cli receives the reflect subparser and adds 'today' verb."""
    import argparse
    from hermes_cli.subcommands.reflect import register_cli
    parent = argparse.ArgumentParser()
    register_cli(parent)
    parsed = parent.parse_args(["today"])
    assert parsed.reflect_cmd == "today"


def test_register_cli_rejects_no_verb():
    import argparse
    from hermes_cli.subcommands.reflect import register_cli
    parent = argparse.ArgumentParser()
    register_cli(parent)
    with pytest.raises(SystemExit):
        parent.parse_args([])
