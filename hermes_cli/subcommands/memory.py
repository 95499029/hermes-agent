"""``hermes memory`` subcommand parser.

Extracted from ``hermes_cli/main.py:main()`` (god-file Phase 2 follow-up).
Handler injected to avoid importing ``main``.
"""

from __future__ import annotations

from typing import Callable


def build_memory_parser(subparsers, *, cmd_memory: Callable) -> None:
    """Attach the ``memory`` subcommand to ``subparsers``."""
    memory_parser = subparsers.add_parser(
        "memory",
        help="Configure external memory provider",
        description=(
            "Set up and manage external memory provider plugins.\n\n"
            "Available providers: honcho, openviking, mem0, hindsight,\n"
            "holographic, retaindb, byterover.\n\n"
            "Only one external provider can be active at a time.\n"
            "Built-in memory (MEMORY.md/USER.md) is always active."
        ),
    )
    memory_sub = memory_parser.add_subparsers(dest="memory_command")
    _setup_parser = memory_sub.add_parser(
        "setup", help="Interactive provider selection and configuration"
    )
    _setup_parser.add_argument(
        "provider",
        nargs="?",
        default=None,
        help="Provider to configure directly (e.g. honcho), skipping the picker",
    )
    memory_sub.add_parser("status", help="Show current memory provider config")
    memory_sub.add_parser("off", help="Disable external provider (built-in only)")
    _reset_parser = memory_sub.add_parser(
        "reset",
        help="Erase all built-in memory (MEMORY.md and USER.md)",
    )
    _reset_parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    _reset_parser.add_argument(
        "--target",
        choices=["all", "memory", "user"],
        default="all",
        help="Which store to reset: 'all' (default), 'memory', or 'user'",
    )

    # --- 通用层 tier operations (P1 task 3 of tiered memory plan) ---
    _promote = memory_sub.add_parser(
        "promote",
        help="Add a fact to MEMORY.md (no-op on near-duplicate)",
    )
    _promote.add_argument(
        "fact",
        help='Fact text, quoted. Use § to separate facts: hermes memory promote "fact one § fact two"',
    )
    _demote = memory_sub.add_parser(
        "demote",
        help="Remove a fact from MEMORY.md and archive it to 历史层",
    )
    _demote.add_argument(
        "needle",
        help="Substring to match (case-insensitive, first occurrence wins)",
    )
    memory_sub.add_parser(
        "stats",
        help="Show 通用层 stats (fact count, bytes, 历史层 size)",
    )
    memory_sub.add_parser(
        "rebalance",
        help="Re-organise existing facts under their correct ## section (idempotent)",
    )
    _search_parser = memory_sub.add_parser(
        "search",
        help="Full-text search over the 历史层 archive (local FTS5 index)",
    )
    _search_parser.add_argument(
        "query",
        help="BM25 search query — terms separated by spaces",
    )
    _search_parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=10,
        help="Max results to return (default: 10)",
    )
    _search_parser = memory_sub.add_parser(
        "index",
        help="Rebuild the 历史层 FTS5 index (auto-runs on each search call)",
    )

    memory_parser.set_defaults(func=cmd_memory)