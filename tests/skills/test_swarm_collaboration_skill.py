"""Tests for skills/autonomous-ai-agents/swarm-collaboration/SKILL.md.

Verifies frontmatter compliance, required sections, and the six
principles encoded in the EvoX/EvoMap experiment distillation.
"""

import re
from pathlib import Path

import pytest
import yaml

SKILL_MD = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "autonomous-ai-agents"
    / "swarm-collaboration"
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
        assert _frontmatter()["name"] == "swarm-collaboration"

    def test_description_length_and_period(self):
        desc = _frontmatter()["description"]
        assert len(desc) <= 60, f"description too long: {len(desc)}"
        assert desc.endswith("."), f"must end with period: {desc!r}"

    def test_description_no_marketing_words(self):
        desc = _frontmatter()["description"].lower()
        for banned in ("powerful", "comprehensive", "seamless", "advanced"):
            assert banned not in desc, f"marketing word: {banned}"

    def test_platforms_covers_all_three(self):
        fm = _frontmatter()
        assert set(fm["platforms"]) == {"linux", "macos", "windows"}

    def test_license_present(self):
        assert _frontmatter().get("license") in {"MIT", "Apache-2.0"}

    def test_experimental_basis_in_frontmatter(self):
        """The skill is grounded in a published benchmark; the frontmatter
        notes must reference the source numbers so future readers know the
        claims are not invented."""
        notes = _frontmatter()["metadata"]["hermes"].get("notes", "")
        assert "26.29%" in notes, "benchmark baseline not cited"
        assert "70.69%" in notes or "70.87%" in notes, "swarm result not cited"
        assert "55.5%" in notes, "retention stat not cited"


class TestBody:
    def test_required_sections(self):
        body = _body()
        for section in ("## Prerequisites", "## When to Use",
                        "## The Six Principles", "## Pitfalls",
                        "## Verification"):
            assert section in body, f"missing: {section}"

    def test_six_principles_present_and_ordered(self):
        """All six principles must appear, in order. Removing or
        reordering would invalidate the skill's structural argument."""
        body = _body()
        principle_titles = [
            "### 1. Direct result routing",
            "### 2. Pre-declare output shape",
            "### 3. No repeated context in the join",
            "### 4. Failures are inputs",
            "### 5. Persist successful patterns",
            "### 6. Independent lifecycle",
        ]
        positions = [body.find(p) for p in principle_titles]
        for p in principle_titles:
            assert body.find(p) >= 0, f"missing principle: {p}"
        for a, b in zip(positions, positions[1:]):
            assert a < b, f"principle order violated: {positions}"

    def test_swarm_vs_subagent_contrast_present(self):
        """The skill's whole point is the difference between swarm
        (direct routing) and sub-agent (parent re-summarises). Both
        terms must appear with their defining contrast."""
        body = _body()
        # The benchmark numbers are the lever for the contrast
        assert "26.29%" in body, "single-agent baseline missing"
        assert "sub-agent" in body.lower()
        assert "swarm" in body.lower()
        # The retention stat is the "why" — must be in body
        assert "55.5%" in body, "55.5% retention stat missing"

    def test_principle_1_forbids_parent_resummarisation(self):
        body = _body()
        # Principle 1 explicitly forbids the parent rewriting
        # sub-agent output
        p1_start = body.find("### 1.")
        p1_end = body.find("### 2.")
        p1 = body[p1_start:p1_end]
        assert "never" in p1.lower() or "not" in p1.lower()
        # And it must name the action it forbids
        for forbidden in ("re-summarise", "rewrite", "re-interpret"):
            if forbidden in p1.lower():
                break
        else:
            pytest.fail(
                "Principle 1 must name the action it forbids "
                "(re-summarise / rewrite / re-interpret)"
            )

    def test_principle_4_requires_failure_visibility(self):
        body = _body()
        p4_start = body.find("### 4.")
        p4_end = body.find("### 5.")
        p4 = body[p4_start:p4_end]
        assert "silent" in p4.lower(), "must warn against silent failures"
        assert "slot" in p4.lower(), "must name a failure slot"

    def test_principle_5_requires_dated_one_line_memory(self):
        body = _body()
        p5_start = body.find("### 5.")
        p5_end = body.find("### 6.")
        p5 = body[p5_start:p5_end].lower()
        # Must mention dating
        assert "date" in p5
        # Must mention one-line format (either "one line" or "one-line")
        assert ("one line" in p5 or "one-line" in p5)
        # Must show a dated example (the 2026-09-02 prefix)
        assert "2026-" in p5


class TestFootprint:
    """Same zero-footprint rule as agent-intelligence."""

    def test_no_invocation_always(self):
        body = _body().lower()
        assert "invocation:" not in body, (
            "swarm-collaboration must not force-inject; the parent "
            "decides when to split a task into a swarm."
        )

    def test_no_command_invocation_directive(self):
        body = _body().lower()
        assert "always:" not in body or "always-on" not in body


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))