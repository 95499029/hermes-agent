#!/usr/bin/env python3
"""Self-check for the agent-intelligence skill.

Verifies the skill's structural integrity without requiring pytest or
the hermes runtime. Use this when you want a quick "is this skill still
intact?"" answer without installing dev dependencies.

Usage:
    python scripts/verify_skill.py
    python scripts/verify_skill.py --verbose

Exit code 0 = all checks passed. Non-zero = at least one failed.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKILL_NAME = "agent-intelligence"
SKILL_ROOT = Path(__file__).resolve().parent.parent

# Files that must exist
REQUIRED_FILES = [
    "SKILL.md",
    "references/trust-tier-examples.md",
    "references/source-ranking-heuristics.md",
    "references/preflight-checklist.md",
    "references/conversation-1-gitlab-issue.md",
    "scripts/verify_skill.py",
]

# Strings that must appear in SKILL.md body
REQUIRED_BODY = [
    "## Prerequisites",
    "## When to Use",
    "## Pitfalls",
    "## Verification",
    "## Examples",
    "## References",
    "## Self-check",
    "What context do I actually need right now?",
    "most reliable source",
    "blast radius",
    "**Read-only public**",
    "**Read-only authenticated**",
    "**Write to local sandbox**",
    "**Write to remote**",
    "**Destructive**",
    "Live primary source",
    "Memory / training-data recall",
    "mid-session",
    "Pattern A",
    "Pattern B",
    "Pattern C",
    "Pattern D",
]

# Per-file minimum size (chars) — guards against accidental truncation
MIN_SIZE = {
    "SKILL.md": 8_000,
    "references/trust-tier-examples.md": 2_000,
    "references/source-ranking-heuristics.md": 2_000,
    "references/preflight-checklist.md": 800,
    "references/conversation-1-gitlab-issue.md": 1_500,
    "scripts/verify_skill.py": 1_500,
}

# Trust tiers must appear in risk-ascending order
TRUST_TIER_ORDER = [
    "**Read-only public**",
    "**Read-only authenticated**",
    "**Write to local sandbox**",
    "**Write to remote**",
    "**Destructive**",
]


def check_files(root: Path, verbose: bool = False) -> list[str]:
    errors: list[str] = []
    for rel in REQUIRED_FILES:
        p = root / rel
        if not p.exists():
            errors.append(f"missing file: {rel}")
            continue
        if rel in MIN_SIZE:
            size = p.stat().st_size
            if size < MIN_SIZE[rel]:
                errors.append(
                    f"{rel}: too small ({size} chars, min {MIN_SIZE[rel]})"
                )
        if verbose:
            print(f"  ok: {rel} ({p.stat().st_size} bytes)")
    return errors


def check_skill_md_body(root: Path, verbose: bool = False) -> list[str]:
    errors: list[str] = []
    body_path = root / "SKILL.md"
    if not body_path.exists():
        return ["SKILL.md missing"]
    body = body_path.read_text(encoding="utf-8")

    for needle in REQUIRED_BODY:
        if needle not in body:
            errors.append(f"SKILL.md missing required phrase: {needle!r}")
        elif verbose:
            print(f"  ok: phrase {needle!r}")

    # Trust tier order
    positions = [body.find(t) for t in TRUST_TIER_ORDER]
    if any(p < 0 for p in positions):
        errors.append("SKILL.md: one or more trust tiers missing")
    else:
        for a, b in zip(positions, positions[1:]):
            if a >= b:
                errors.append(
                    f"SKILL.md: trust tier order violated "
                    f"(position {a} >= {b})"
                )

    return errors


def check_description(root: Path, verbose: bool = False) -> list[str]:
    """Description in YAML frontmatter must be <= 60 chars, end with
    a period, and contain no marketing words."""
    errors: list[str] = []
    body = (root / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    if not m:
        return ["SKILL.md: missing YAML frontmatter"]
    fm = m.group(1)

    # Description line
    dm = re.search(r"^description:\s*(.+?)\s*$", fm, re.MULTILINE)
    if not dm:
        return ["SKILL.md: missing description in frontmatter"]
    desc = dm.group(1).strip().strip('"').strip("'")
    if len(desc) > 60:
        errors.append(f"SKILL.md: description too long ({len(desc)} chars)")
    if not desc.endswith("."):
        errors.append("SKILL.md: description must end with a period")
    for banned in ("powerful", "comprehensive", "seamless", "advanced"):
        if banned in desc.lower():
            errors.append(f"SKILL.md: description has marketing word: {banned}")
    if verbose:
        print(f"  ok: description {desc!r}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print each ok-check"
    )
    parser.add_argument(
        "--skill-root",
        default=None,
        help="override skill root (default: parent of this script)",
    )
    args = parser.parse_args(argv)

    root = Path(args.skill_root).resolve() if args.skill_root else SKILL_ROOT
    if not root.exists():
        print(f"error: skill root does not exist: {root}", file=sys.stderr)
        return 2

    print(f"Verifying skill: {SKILL_NAME} ({root})")

    if args.verbose:
        print("\n[files]")
    errors = check_files(root, args.verbose)
    if args.verbose:
        print("\n[frontmatter]")
    errors.extend(check_description(root, args.verbose))
    if args.verbose:
        print("\n[SKILL.md body]")
    errors.extend(check_skill_md_body(root, args.verbose))

    if errors:
        print(f"\nFAILED: {len(errors)} issue(s)")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("\nOK: skill is intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())