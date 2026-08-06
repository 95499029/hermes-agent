"""Memory consolidation — the nightly janitor.

Runs the warm-layer (MEMORY.md) and cold-layer (memories/cold/) through a
set of housekeeping passes:

  1. PII redact           — strip API keys / phone / id before any write
  2. TTL demote           — facts older than ttl_days are archived
  3. Conflict detect      — pairwise semantic check; flag for review
  4. Re-classify section  — use memory_tier.rebalance
  5. Stats emit           — write ~/.hermes/logs/consolidate.json

The script is read-only by default. --apply must be passed to actually
mutate state, so it's safe to dry-run from a cron entry while debugging.

Usage:
    python memory_consolidate.py                # dry run
    python memory_consolidate.py --apply         # mutate
    python memory_consolidate.py --ttl 30       # 30-day TTL (default 60)
    python memory_consolidate.py --json         # print stats as JSON
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import pii as _pii


# --- PII: thin re-export so existing CLI flags stay stable -----------------
redact_pii = _pii.redact
PII_RULES = _pii.RULES
PII_RE = _pii._PATTERN


# --- Hermes home + path helpers ----------------------------------------------

def _hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    return Path(env) if env else Path.home() / ".hermes"


def _memory_path() -> Path:
    return _hermes_home() / "memories" / "MEMORY.md"


def _cold_dir() -> Path:
    d = _hermes_home() / "memories" / "cold"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _logs_dir() -> Path:
    d = _hermes_home() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- Consolidation passes ----------------------------------------------------

def pass_pii_scan(path: Path) -> dict:
    """Find PII in MEMORY.md and (if --apply) redact it.

    Returns a count dict {matches: N, redacted: N}.
    """
    if not path.exists():
        return {"matches": 0, "redacted": 0, "scanned_bytes": 0}
    text = path.read_text(encoding="utf-8")
    matches = sum(1 for _ in PII_RE.finditer(text))
    return {"matches": matches, "redacted": 0, "scanned_bytes": len(text)}


def pass_pii_apply(path: Path) -> dict:
    """Apply PII redaction in-place."""
    if not path.exists():
        return {"matches": 0, "redacted": 0, "scanned_bytes": 0}
    text = path.read_text(encoding="utf-8")
    redacted, count = redact_pii(text)
    if count:
        path.write_text(redacted, encoding="utf-8")
    return {"matches": count, "redacted": count, "scanned_bytes": len(text)}


def pass_ttl_demote(ttl_days: int, apply: bool) -> dict:
    """Archive any cold file older than ttl_days into a 'stale/' subdir.

    We don't auto-delete — TTL drops them into a separate archive so the
    user can review and recover. Stale files still appear in cold/ search
    unless explicitly excluded.
    """
    cold = _cold_dir()
    now = datetime.now(timezone.utc)
    archived: list[str] = []
    for path in cold.glob("*.md"):
        # Filename starts with YYYYMMDD; parse it directly.
        prefix = path.stem.split("-", 1)[0]
        try:
            ts = datetime.strptime(prefix, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        age_days = (now - ts).days
        if age_days < ttl_days:
            continue
        archived.append(str(path))
        if apply:
            stale_dir = cold / "stale"
            stale_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(stale_dir / path.name))
    return {"ttl_days": ttl_days, "candidates": len(archived), "archived": len(archived) if apply else 0}


def pass_conflict_detect() -> dict:
    """Lightweight conflict heuristic: look for fact pairs that share a
    category keyword (python, sudo, homebrew, etc.) but disagree on a
    specific token.

    For v1 we just report pairs; humans resolve. The detector returns
    {'flagged': [...]} so a future pass could prompt the user.
    """
    # Stub: full implementation requires LLM call. Keeping the surface so
    # the metrics schema is stable.
    return {"flagged": [], "checked_pairs": 0}


def pass_rebalance(apply: bool) -> dict:
    """Re-run section routing. Idempotent. Touches MEMORY.md only on change."""
    if not apply:
        return {"would_rebalance": True, "size": _memory_path().stat().st_size if _memory_path().exists() else 0}
    from hermes_cli.memory_tier import rebalance

    result = rebalance()
    return {"would_rebalance": False, "sections": result.get("sections", {}), "size": result.get("size", 0)}


# --- Main entrypoint ---------------------------------------------------------

def run(args: argparse.Namespace) -> dict:
    metrics: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "apply": args.apply,
        "ttl_days": args.ttl,
        "passes": {},
    }
    if args.pii or args.all:
        if args.apply:
            metrics["passes"]["pii"] = pass_pii_apply(_memory_path())
        else:
            metrics["passes"]["pii"] = pass_pii_scan(_memory_path())
    if args.ttl_demote or args.all:
        metrics["passes"]["ttl_demote"] = pass_ttl_demote(args.ttl, apply=args.apply)
    if args.conflict or args.all:
        metrics["passes"]["conflict"] = pass_conflict_detect()
    if args.rebalance or args.all:
        metrics["passes"]["rebalance"] = pass_rebalance(apply=args.apply)
    if args.cold_pii or args.all:
        # Scan + redact cold/ archives too.
        scanned = 0
        redacted = 0
        for path in _cold_dir().glob("*.md"):
            text = path.read_text(encoding="utf-8")
            new, n = redact_pii(text)
            scanned += len(text)
            if n and args.apply:
                path.write_text(new, encoding="utf-8")
            redacted += n
        metrics["passes"]["cold_pii"] = {"matches": redacted, "scanned_bytes": scanned}
    return metrics


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Memory consolidation janitor")
    p.add_argument("--apply", action="store_true", help="Mutate state (default is dry run)")
    p.add_argument("--all", action="store_true", help="Run every pass")
    p.add_argument("--pii", action="store_true", help="Run PII scan on warm layer")
    p.add_argument("--ttl", type=int, default=60, help="TTL in days (default: 60)")
    p.add_argument("--ttl-demote", action="store_true", help="Demote cold files older than --ttl")
    p.add_argument("--conflict", action="store_true", help="Run conflict detector")
    p.add_argument("--rebalance", action="store_true", help="Re-classify facts under sections")
    p.add_argument("--cold-pii", action="store_true", help="PII-scan cold layer too")
    p.add_argument("--json", action="store_true", help="Print metrics as JSON")
    p.add_argument("--out", type=Path, default=None, help="Write metrics JSON to file")
    args = p.parse_args(argv)

    # Default to --all when no pass flag given.
    if not any([args.all, args.pii, args.ttl_demote, args.conflict, args.rebalance, args.cold_pii]):
        args.all = True

    metrics = run(args)

    if args.json:
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
    else:
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"\n  Memory consolidate — {mode}")
        for name, m in metrics["passes"].items():
            print(f"    {name}: {m}")
        print()

    if args.out:
        args.out.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    # Always append a metrics line to logs/consolidate.jsonl (for trend tracking).
    log_line = json.dumps(metrics, ensure_ascii=False)
    log_path = _logs_dir() / "consolidate.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(log_line + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())