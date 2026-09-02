"""Tests for skills/software-development/agent-intelligence/SKILL.md.

Verifies frontmatter compliance, required sections, and the key behavioral
contracts the skill encodes (context economics + tool trust tiers).
"""

import re
from pathlib import Path

import pytest
import yaml

SKILL_MD = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "software-development"
    / "agent-intelligence"
    / "SKILL.md"
)


def _read():
    return SKILL_MD.read_text(encoding="utf-8")


def _frontmatter():
    text = _read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md missing YAML frontmatter"
    return yaml.safe_load(m.group(1))


def _body():
    return re.sub(r"^---\n.*?\n---\n", "", _read(), count=1, flags=re.DOTALL)


class TestFrontmatter:
    def test_name_matches_directory(self):
        assert _frontmatter()["name"] == "agent-intelligence"

    def test_description_length_and_period(self):
        desc = _frontmatter()["description"]
        assert len(desc) <= 60, f"description too long: {len(desc)}"
        assert desc.endswith("."), f"description must end with period: {desc!r}"

    def test_description_no_marketing_words(self):
        desc = _frontmatter()["description"].lower()
        for banned in ("powerful", "comprehensive", "seamless", "advanced"):
            assert banned not in desc, f"marketing word in description: {banned}"

    def test_platforms_covers_all_three(self):
        fm = _frontmatter()
        assert set(fm["platforms"]) == {"linux", "macos", "windows"}

    def test_license_present(self):
        assert _frontmatter().get("license") in {"MIT", "Apache-2.0"}


class TestBody:
    def test_required_sections(self):
        body = _body()
        for section in (
            "## Prerequisites",
            "## When to Use",
            "## Pitfalls",
            "## Verification",
        ):
            assert section in body, f"missing required section: {section}"

    def test_three_questions_present(self):
        body = _body()
        for q in (
            "What context do I actually need right now?",
            "What's the most reliable source for this information?",
            "What's the blast radius if this tool call is wrong?",
        ):
            assert q in body, f"missing framing question: {q}"

    def test_trust_tier_table_present(self):
        body = _body()
        # All five tiers and at least one example per tier
        for marker in (
            "**Read-only public**",
            "**Read-only authenticated**",
            "**Write to local sandbox**",
            "**Write to remote**",
            "**Destructive**",
        ):
            assert marker in body, f"trust tier missing: {marker}"

    def test_prompt_caching_constraint_present(self):
        body = _body().lower()
        # Must explicitly forbid mid-session cache-breaking
        assert "prompt cache" in body or "prompt caching" in body
        assert "mid-session" in body or "mid-conversation" in body

    def test_source_ranking_present(self):
        body = _body()
        for tier in (
            "Live primary source",
            "Crawler-grade secondary",
            "Search-aggregated",
            "Memory / training-data recall",
        ):
            assert tier in body, f"source tier missing: {tier}"

    def test_patterns_section_has_four_patterns(self):
        body = _body()
        # All four canonical patterns must be present and named
        for pat in ("Pattern A", "Pattern B", "Pattern C", "Pattern D"):
            assert pat in body, f"pattern missing: {pat}"

    def test_pitfalls_dont_include_obsolete_tooling(self):
        body = _body().lower()
        # The skill must not recommend tools that contradict its own advice
        # (e.g. telling user to dump the whole toolset)
        for banned in (
            "always enable all tools",
            "load the full catalog",
            "skip the trust tier",
        ):
            assert banned not in body, f"pitfall contradicts skill: {banned}"


class TestFootprint:
    """The whole point of this skill is zero schema footprint."""

    def test_no_command_invocation_directive(self):
        # Skills should not inject tool calls into the agent prompt;
        # they are guidance, not commands.
        body = _body().lower()
        # No `invocation:` block (which would force model invocation
        # of this skill every turn — exactly the cache-cost the skill
        # itself warns against).
        assert "invocation:" not in body, (
            "skill sets invocation: → every-turn cache pressure; "
            "skill should be opt-in via Skill tool or context."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))