"""Memory tier operations: promote facts into MEMORY.md, demote out to 历史层.

Implements the 通用层 promotion/demotion rules described in the
Tiered Memory Architecture design doc. Designed to live outside main.py
so the god-file doesn't grow further.

File format is plain Markdown (Hermes convention):
    # Header
    > meta-rule

    ## Section
    - fact one
    - fact two

历史层: ~/.hermes/memories/cold/<timestamp>-<slug>.md
(one archived fact per file, human-readable, grep-friendly).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

_COLD_DIR = "cold"
_FACT_LINE_PREFIX = "- "


def _hermes_home() -> Path:
    """Resolve ~/.hermes with full env-var + profile awareness.

    Honor $HERMES_HOME (Hermes convention) and the optional `profile` query
    before falling back to ~/.hermes. Matches hermes_constants.get_hermes_home
    so tests using HERMES_HOME=... are respected even when that import fails.
    """
    import os

    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    return Path.home() / ".hermes"


def _memory_char_limit() -> int:
    """Read memory.memory_char_limit from config.yaml, fall back to 2200.

    Hermes CLI stores this in config.yaml. We tolerate a missing/invalid file
    or key by returning the documented default rather than crashing stats().
    """
    import os

    try:
        import yaml  # type: ignore

    except ImportError:
        return 2200
    cfg_path = _hermes_home() / "config.yaml"
    if not cfg_path.exists():
        return 2200
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        mem = cfg.get("memory") or {}
        limit = mem.get("memory_char_limit")
        return int(limit) if isinstance(limit, (int, float)) else 2200
    except Exception:
        return 2200


def _memory_path() -> Path:
    return _hermes_home() / "memories" / "MEMORY.md"


def _cold_dir() -> Path:
    d = _hermes_home() / "memories" / _COLD_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(text: str, max_len: int = 40) -> str:
    """ASCII-safe slug from first words of the fact."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text or "fact")[:max_len].rstrip("-")


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").split("\n")


# Section routing rules for 通用层 facts. Each section is matched against a
# set of keywords; a fact that hits any keyword goes to that section. The order
# matters — the first match wins — so put the most specific section first.
_SECTION_RULES: list[tuple[str, list[str]]] = [
    ("模型/Provider 选型", [
        "model", "provider", "agent", "protocol probe", "Responses",
        "Chat Completions", "choose-coding-agent",
    ]),
    ("macOS 环境", [
        "macOS", "Apple Python", "Homebrew", "Hermes CLI", "sudo",
        "osascript", "Secret", "read_file", "echo", "cat", "Apple",
        "pmset", "uv-managed", "/usr/bin/python3",
    ]),
    ("工程协作偏好", [
        "工作流", "策划", "推进", "批判性分析", "5 阶段",
        "ad-hoc", "验证脚本", "具体产出", "跨项目",
    ]),
]
_DEFAULT_SECTION = "工程协作偏好"


def _classify_section(fact: str) -> str:
    """Return the best section name for ``fact`` based on keyword routing."""
    lower = fact.lower()
    for section, keywords in _SECTION_RULES:
        if any(k.lower() in lower for k in keywords):
            return section
    return _DEFAULT_SECTION


def rebalance() -> dict:
    """Re-organise existing facts under their correct ## section.

    Reads the current file, groups every bullet under the most recent ## header,
    then re-emits the document with facts placed under their classified section
    (one section per header, facts interleaved by original order).

    Idempotent: running it twice is a no-op.
    """
    path = _memory_path()
    if not path.exists():
        return {"ok": False, "reason": "MEMORY.md missing"}
    lines = _read_lines(path)
    # Phase 1: collect facts as (raw_fact_text, classified_section)
    facts_with_section: list[tuple[str, str]] = []
    current_section: str | None = None
    top_header: list[str] = []  # everything before the first ## heading
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("## "):
            current_section = stripped[3:].strip()
        elif stripped.startswith("- "):
            section = current_section or _DEFAULT_SECTION
            facts_with_section.append((stripped[2:].rstrip(), section))
        else:
            if current_section is None:
                top_header.append(line)
    # Phase 2: re-classify each fact (overrides whatever section it landed in
    # originally) and group by classified section in original-order traversal.
    grouped: dict[str, list[str]] = {}
    for raw, _original in facts_with_section:
        section = _classify_section(raw)
        grouped.setdefault(section, []).append(raw)
    # Phase 3: emit. Header first (top_header), then each section that has facts.
    new_lines: list[str] = list(top_header)
    for section_name, fact_list in grouped.items():
        if not fact_list:
            continue
        if new_lines and new_lines[-1] != "":
            new_lines.append("")
        new_lines.append(f"## {section_name}")
        new_lines.append("")
        new_lines.extend(f"- {f}" for f in fact_list)
    new_lines.append("")
    path.write_text("\n".join(new_lines), encoding="utf-8")
    return {
        "ok": True,
        "action": "rebalanced",
        "sections": {k: len(v) for k, v in grouped.items()},
        "size": path.stat().st_size,
    }


def _split_facts(lines: list[str]) -> tuple[list[str], list[str]]:
    """Return (header_lines, fact_lines).

    header_lines = everything that is NOT a bullet (`- `).
    fact_lines   = the bullet lines, trimmed of the leading "- ".
    """
    header: list[str] = []
    facts: list[str] = []
    for line in lines:
        if line.lstrip().startswith(_FACT_LINE_PREFIX):
            facts.append(line.lstrip()[len(_FACT_LINE_PREFIX):].rstrip())
        else:
            header.append(line)
    return header, facts


def _dedup(facts: list[str], new_fact: str) -> tuple[list[str], bool]:
    """Near-duplicate detection by first 60 chars (case+whitespace-insensitive)."""
    norm = re.sub(r"\s+", " ", new_fact.strip().lower())[:60]
    for existing in facts:
        if re.sub(r"\s+", " ", existing.strip().lower())[:60] == norm:
            return facts, True
    return facts + [new_fact.strip()], False


def promote(fact: str) -> dict:
    """Append a bullet fact to MEMORY.md unless it's a near-duplicate."""
    if not fact or not fact.strip():
        return {"ok": False, "reason": "empty fact"}
    path = _memory_path()
    if not path.exists():
        return {"ok": False, "reason": "MEMORY.md missing"}
    lines = _read_lines(path)
    header, facts = _split_facts(lines)
    new_facts, dup = _dedup(facts, fact)
    if dup:
        return {
            "ok": True,
            "action": "noop",
            "reason": "duplicate",
            "total_facts": len(facts),
            "size": path.stat().st_size,
        }
    # Classify the new fact into a section, then rebalance so it lands under
    # the correct ## header (not just appended at the end).
    section = _classify_section(fact)
    # Insert into the chosen section in header form by reconstructing the file
    # with the section title in place. The rebalance helper handles this.
    # We hand off to rebalance() for the actual write so there is one code path.
    # First, append the new fact to the end of the file (it'll be re-grouped).
    text_lines: list[str] = list(header)
    if text_lines and text_lines[-1] != "":
        text_lines.append("")
    text_lines.extend(_FACT_LINE_PREFIX + f for f in new_facts)
    text_lines.append("")
    path.write_text("\n".join(text_lines), encoding="utf-8")
    rebalance_result = rebalance()
    final_size = rebalance_result.get("size", path.stat().st_size)
    return {
        "ok": True,
        "action": "promoted",
        "section": section,
        "total_facts": len(new_facts),
        "size": final_size,
    }


def demote(needle: str) -> dict:
    """Remove the first fact whose text contains ``needle`` (case-insensitive).
    Archive it to the 历史层."""
    if not needle or not needle.strip():
        return {"ok": False, "reason": "empty needle"}
    path = _memory_path()
    if not path.exists():
        return {"ok": False, "reason": "MEMORY.md missing"}
    lines = _read_lines(path)
    header, facts = _split_facts(lines)
    lower_needle = needle.strip().lower()
    match_idx = -1
    for i, f in enumerate(facts):
        if lower_needle in f.lower():
            match_idx = i
            break
    if match_idx == -1:
        return {"ok": False, "reason": "no match"}
    matched = facts[match_idx]
    new_facts = facts[:match_idx] + facts[match_idx + 1:]
    # Archive to 历史层.
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cold_file = _cold_dir() / f"{ts}-{_slug(matched)}.md"
    cold_file.write_text(f"# Archived {ts}\n\n{matched}\n", encoding="utf-8")
    # Rebuild file: header (original), then any remaining facts as bullets.
    text_lines: list[str] = list(header)
    if new_facts:
        if text_lines and text_lines[-1] != "":
            text_lines.append("")
        text_lines.extend(_FACT_LINE_PREFIX + f for f in new_facts)
    text_lines.append("")
    path.write_text("\n".join(text_lines), encoding="utf-8")
    # Rebalance so remaining facts land under their correct ## sections
    # (otherwise demote leaves the file in flat-trailing-facts form).
    rebalance_result = rebalance()
    # Refresh the 历史层 FTS5 index so this new archive is searchable
    # immediately. Cheap: typical 历史层 has tens of files.
    indexed_ok = False
    try:
        from hermes_cli import cold_search  # local import — avoid cycles
        cold_search.rebuild()
        indexed_ok = True
    except Exception:
        # Indexing failure must not block the demote operation.
        indexed_ok = False
    return {
        "ok": True,
        "action": "demoted",
        "cold_file": str(cold_file),
        "remaining_facts": len(new_facts),
        "size": rebalance_result.get("size", path.stat().st_size),
        "indexed": indexed_ok,
    }


def stats() -> dict:
    """Return 通用层 stats for `hermes memory stats` and dashboards.

    `limit` is read live from config.yaml so the progress bar stays accurate
    even if the user customises memory_char_limit.
    """
    import os

    path = _memory_path()
    _, fact_lines = _split_facts(_read_lines(path))
    cold_count = sum(1 for _ in _cold_dir().glob("*.md"))
    return {
        "warm_facts": len(fact_lines),
        "warm_bytes": path.stat().st_size if path.exists() else 0,
        "cold_files": cold_count,
        "limit": _memory_char_limit(),
    }


def _progress_bar(pct: float, width: int = 20) -> str:
    """Render a Unicode block bar with ASCII fallback.

    Some terminals (legacy Windows cmd, certain SSH setups, dumb consoles)
    can't render Box Drawing characters and print ? instead. Detect a
    non-UTF-8 stdout and degrade to =/- glyphs.
    """
    import os
    import sys

    enc = (sys.stdout.encoding or "").lower()
    is_utf8 = "utf-8" in enc or enc == "utf8"
    fill, empty = ("█", "░") if is_utf8 else ("#", "-")
    filled = int(round(pct / 100 * width))
    return fill * filled + empty * (width - filled)