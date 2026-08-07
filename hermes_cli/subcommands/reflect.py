"""``hermes reflect`` — show what Hermes learned today.

The deterministic entry point for the daily-reflection cron job. Aggregates
signals from:
  - journey.json     (skills + memories created today)
  - memory_tier diff (facts promoted/demoted since last consolidate)
  - curator state    (last run, run count, idle gap)
  - skills usage log (which skills the agent actually invoked)

Output schema is stable so the cron job can post-process it.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERMES_HOME = Path.home() / ".hermes"
JOURNEY_PATH = HERMES_HOME / "journey.json"
CURATOR_STATE = HERMES_HOME / ".curator_state"
SKILLS_USAGE_LOG = HERMES_HOME / "logs" / "skill_usage.jsonl"
LAST_CONSOLIDATE_MARKER = HERMES_HOME / ".last_consolidate_at"


# ---------------------------------------------------------------------------
# Pure helpers (no I/O)
# ---------------------------------------------------------------------------

def _today_iso() -> str:
    """Return today's date in YYYY-MM-DD (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _parse_iso_date(s: str | None) -> str | None:
    """Extract YYYY-MM-DD from an ISO timestamp; return None on garbage."""
    if not s:
        return None
    try:
        # Handle both '...Z' and '...+00:00'
        s2 = s.replace("Z", "+00:00") if s.endswith("Z") else s
        return datetime.fromisoformat(s2).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _safe_load_json(path: Path) -> dict | list:
    """Read JSON file; return empty container on missing/corrupt."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
# I/O helpers (each isolated for testability)
# ---------------------------------------------------------------------------

def _read_journey_today() -> list[dict]:
    """Return journey nodes created today (UTC)."""
    data = _safe_load_json(JOURNEY_PATH)
    nodes = data.get("nodes", []) if isinstance(data, dict) else []
    today = _today_iso()
    out = []
    for n in nodes:
        created = n.get("created_at") or n.get("ts") or n.get("timestamp")
        if _parse_iso_date(created) == today:
            out.append(n)
    return out


def _read_memory_today() -> dict[str, list[str]]:
    """Diff MEMORY.md against the .last_consolidate_at marker.

    If no marker exists, returns empty diff (first run since consolidation
    was wired up; the cron job treats this as 'nothing to report').
    """
    if not LAST_CONSOLIDATE_MARKER.exists():
        return {"added": [], "demoted": []}
    return {"added": [], "demoted": []}  # TODO: diff once memory_consolidate writes a manifest


def _read_curator_state() -> dict:
    return _safe_load_json(CURATOR_STATE)


def _read_skills_used_today() -> list[str]:
    """Return names of skills the agent actually invoked today."""
    if not SKILLS_USAGE_LOG.exists():
        return []
    today = _today_iso()
    out: list[str] = []
    seen: set[str] = set()
    for line in SKILLS_USAGE_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = rec.get("ts") or rec.get("timestamp") or rec.get("at")
        if _parse_iso_date(ts) != today:
            continue
        name = rec.get("skill") or rec.get("name")
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

def collect_today() -> dict[str, Any]:
    """Aggregate today's learning signals into a stable dict.

    Schema (all keys always present; values may be empty):
        date              str  "YYYY-MM-DD"
        journey_count     int
        memories_added    list[str]
        memories_demoted  list[str]
        skills_used       list[str]
        curator_state     dict
    """
    return {
        "date": _today_iso(),
        "journey_count": len(_read_journey_today()),
        "memories_added": _read_memory_today().get("added", []),
        "memories_demoted": _read_memory_today().get("demoted", []),
        "skills_used": _read_skills_used_today(),
        "curator_state": _read_curator_state(),
    }


# ---------------------------------------------------------------------------
# CLI verb
# ---------------------------------------------------------------------------

def _format_human(data: dict) -> str:
    """Render the dict as a terminal-friendly summary."""
    lines = [
        f"Hermes reflections for {data['date']} (UTC)",
        "",
        f"  journey nodes created today: {data['journey_count']}",
        f"  memories added today:         {len(data['memories_added'])}",
        f"  memories demoted today:       {len(data['memories_demoted'])}",
        f"  skills used today:            {len(data['skills_used'])}",
    ]
    if data["skills_used"]:
        lines.append(f"    → {', '.join(data['skills_used'][:5])}")
    cs = data.get("curator_state") or {}
    if cs:
        runs = cs.get("runs", 0)
        last = cs.get("last_run_at") or "never"
        lines.append(f"  curator: runs={runs}, last_run={last}")
    if data["memories_added"]:
        lines.append("")
        lines.append("  New memories (consider promoting review):")
        for m in data["memories_added"][:5]:
            lines.append(f"    + {m[:100]}")
    return "\n".join(lines)


def _print_json(data: dict) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def run(args: argparse.Namespace) -> int:
    data = collect_today()
    if getattr(args, "json", False):
        _print_json(data)
    else:
        print(_format_human(data))
    return 0


def register_cli(parent: argparse.ArgumentParser) -> None:
    """Attach the ``reflect`` subcommand to the given parent parser."""
    sub = parent.add_subparsers(dest="reflect_cmd", required=True)
    today = sub.add_parser(
        "today",
        help="Show today's journey + memory stats + curator state",
    )
    today.add_argument(
        "--json", action="store_true",
        help="Print machine-readable JSON instead of human summary",
    )
    today.set_defaults(func=run)
