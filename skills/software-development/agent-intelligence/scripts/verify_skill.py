#!/usr/bin/env python3
"""Self-check for one of the bundled meta-skills.

Verifies a skill's structural integrity without requiring pytest or
the hermes runtime. Use this when you want a quick "is this skill
still intact?" answer without installing dev dependencies.

Supports both bundled meta-skills via --skill:

  - agent-intelligence   (default — context economics + tool trust tiers)
  - swarm-collaboration  (EvoMap/EvoX-derived multi-agent routing)

Usage:
    python scripts/verify_skill.py
    python scripts/verify_skill.py --skill agent-intelligence
    python scripts/verify_skill.py --skill swarm-collaboration
    python scripts/verify_skill.py --verbose

Exit code 0 = all checks passed. Non-zero = at least one failed.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Each profile is a complete spec for verifying one skill — frontmatter
# rules, body contract, file layout, tier order. Adding a new skill
# means adding a profile here; nothing else changes.
SKILL_PROFILES = {
    "agent-intelligence": {
        "required_files": [
            "SKILL.md",
            "references/trust-tier-examples.md",
            "references/source-ranking-heuristics.md",
            "references/preflight-checklist.md",
            "references/conversation-1-gitlab-issue.md",
            "scripts/verify_skill.py",
        ],
        "min_sizes": {
            "SKILL.md": 8_000,
            "references/trust-tier-examples.md": 2_000,
            "references/source-ranking-heuristics.md": 2_000,
            "references/preflight-checklist.md": 800,
            "references/conversation-1-gitlab-issue.md": 1_500,
            "scripts/verify_skill.py": 1_500,
        },
        "required_body": [
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
        ],
        "trust_tier_order": [
            "**Read-only public**",
            "**Read-only authenticated**",
            "**Write to local sandbox**",
            "**Write to remote**",
            "**Destructive**",
        ],
        "description": "Apply context economics and tool trust tiers on every task.",
    },
    "swarm-collaboration": {
        "required_files": [
            "SKILL.md",
            "references/conversation-1-coffee-shop-launch.md",
        ],
        "min_sizes": {
            "SKILL.md": 7_000,
            "references/conversation-1-coffee-shop-launch.md": 2_500,
        },
        "required_body": [
            "## Prerequisites",
            "## When to Use",
            "## The Six Principles",
            "## Pitfalls",
            "## Verification",
            "### 1. Direct result routing",
            "### 2. Pre-declare output shape",
            "### 3. No repeated context in the join",
            "### 4. Failures are inputs",
            "### 5. Persist successful patterns",
            "### 6. Independent lifecycle",
            "26.29%",
            "70.69%",
            "55.5%",
        ],
        "trust_tier_order": None,  # swarm has no trust-tier table
        "description": "Decompose tasks so sub-agents report directly to slots.",
    },
}

# Default skill (backwards-compat with the v0 single-skill version)
DEFAULT_SKILL = "agent-intelligence"

# Skill root is the parent of this script directory (scripts/ → <skill>/).
DEFAULT_SKILL_ROOT = Path(__file__).resolve().parent.parent


def check_files(root: Path, profile: dict, verbose: bool = False) -> list[str]:
    errors: list[str] = []
    for rel in profile["required_files"]:
        p = root / rel
        if not p.exists():
            errors.append(f"missing file: {rel}")
            continue
        if rel in profile["min_sizes"]:
            size = p.stat().st_size
            if size < profile["min_sizes"][rel]:
                errors.append(
                    f"{rel}: too small ({size} chars, min {profile['min_sizes'][rel]})"
                )
        if verbose:
            print(f"  ok: {rel} ({p.stat().st_size} bytes)")
    return errors


def check_skill_md_body(root: Path, profile: dict, verbose: bool = False) -> list[str]:
    errors: list[str] = []
    body_path = root / "SKILL.md"
    if not body_path.exists():
        return ["SKILL.md missing"]
    body = body_path.read_text(encoding="utf-8")

    for needle in profile["required_body"]:
        if needle not in body:
            errors.append(f"SKILL.md missing required phrase: {needle!r}")
        elif verbose:
            print(f"  ok: phrase {needle!r}")

    tier_order = profile.get("trust_tier_order")
    if tier_order:
        positions = [body.find(t) for t in tier_order]
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


def check_description(root: Path, profile: dict, verbose: bool = False) -> list[str]:
    """Description in YAML frontmatter must be <= 60 chars, end with
    a period, and contain no marketing words."""
    errors: list[str] = []
    body = (root / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    if not m:
        return ["SKILL.md: missing YAML frontmatter"]
    fm = m.group(1)

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
    # Description should match the profile's expected description
    if profile.get("description") and desc != profile["description"]:
        # Soft check — only flag if not the configured one
        if verbose:
            print(f"  note: description is '{desc}', profile expects "
                  f"'{profile['description']}'")
    if verbose:
        print(f"  ok: description {desc!r}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print each ok-check"
    )
    parser.add_argument(
        "--skill",
        default=DEFAULT_SKILL,
        choices=sorted(SKILL_PROFILES.keys()),
        help=f"which skill to verify (default: %(default)s)",
    )
    parser.add_argument(
        "--skill-root",
        default=None,
        help="override skill root (default: parent of this script)",
    )
    args = parser.parse_args(argv)

    profile = SKILL_PROFILES[args.skill]
    root = Path(args.skill_root).resolve() if args.skill_root else DEFAULT_SKILL_ROOT
    if not root.exists():
        print(f"error: skill root does not exist: {root}", file=sys.stderr)
        return 2

    print(f"Verifying skill: {args.skill} ({root})")

    if args.verbose:
        print("\n[files]")
    errors = check_files(root, profile, args.verbose)
    if args.verbose:
        print("\n[frontmatter]")
    errors.extend(check_description(root, profile, args.verbose))
    if args.verbose:
        print("\n[SKILL.md body]")
    errors.extend(check_skill_md_body(root, profile, args.verbose))

    if errors:
        print(f"\nFAILED: {len(errors)} issue(s)")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("\nOK: skill is intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())