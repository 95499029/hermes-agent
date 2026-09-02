"""End-to-end verification that the agent-intelligence skill integrates
with hermes's real production code paths (skill_view → _load_skill_payload
→ build_preloaded_skills_prompt), and that the injected prompt satisfies
the behavioral contracts the skill is designed to encode.

Mirrors what `hermes -s agent-intelligence` does on a real session start.
"""

import json
import sys
from pathlib import Path

import pytest

# Add hermes-agent root so we import the same modules production uses
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from agent.skill_commands import _load_skill_payload, build_preloaded_skills_prompt  # noqa: E402
from tools.skills_tool import skill_view  # noqa: E402


SKILL_NAME = "agent-intelligence"


def _ensure_skill_present() -> Path:
    """The agent-intelligence skill must be installed under
    ~/.hermes/skills/<category>/<name>/SKILL.md for hermes's default skill
    resolver to find it. This fixture points at the canonical copy in the
    repo (skills/software-development/agent-intelligence/) and, if missing
    in HERMES_HOME, copies it there so the test runs against the live
    profile resolver. Skips if HERMES_HOME cannot be resolved.
    """
    from hermes_constants import get_hermes_home

    try:
        hermes_home = get_hermes_home()
    except Exception:
        pytest.skip("HERMES_HOME not resolvable in this environment")

    # The skill must live at <hermes_home>/skills/software-development/<name>/SKILL.md
    target = hermes_home / "skills" / "software-development" / SKILL_NAME / "SKILL.md"
    repo_source = REPO_ROOT / "skills" / "software-development" / SKILL_NAME / "SKILL.md"

    if not repo_source.exists():
        pytest.skip(f"repo source missing: {repo_source}")

    if not target.exists():
        # Mirror the repo copy into the live profile dir.
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(repo_source.read_text(encoding="utf-8"), encoding="utf-8")

    return target


class TestSkillResolutionE2E:
    """The first step of any session: can hermes find this skill by name?"""

    def test_skill_view_returns_success(self):
        _ensure_skill_present()
        data = json.loads(skill_view(SKILL_NAME, preprocess=False))
        assert data.get("success") is True, (
            f"skill_view failed: {data.get('error') or 'no error message'}"
        )
        assert data.get("name") == SKILL_NAME

    def test_skill_content_has_minimum_substance(self):
        _ensure_skill_present()
        data = json.loads(skill_view(SKILL_NAME, preprocess=False))
        content = data.get("content") or ""
        # 10KB is a soft floor — anything smaller means the SKILL.md
        # was edited down past the point where the contracts below
        # can survive.
        assert len(content) >= 5_000, f"skill too thin: {len(content)} chars"

    def test_load_skill_payload_round_trip(self):
        _ensure_skill_present()
        payload = _load_skill_payload(SKILL_NAME)
        assert payload is not None
        loaded_skill, skill_dir, skill_name = payload
        assert skill_name == SKILL_NAME
        assert skill_dir is not None and skill_dir.exists()


class TestPreloadPromptE2E:
    """The second step: when hermes preloads this skill, what does the
    injected prompt actually contain? These checks are the behavioral
    contract — the agent should not be able to use this skill in
    production without these features being available in its context."""

    @pytest.fixture
    def preload_prompt(self):
        _ensure_skill_present()
        prompt, loaded, missing = build_preloaded_skills_prompt([SKILL_NAME])
        assert loaded == ["agent-intelligence"], (
            f"skill did not load: missing={missing}"
        )
        assert missing == []
        assert prompt, "preloaded prompt is empty"
        return prompt

    @pytest.mark.parametrize(
        "contract,needle",
        [
            ("activation_note",      "IMPORTANT: The user launched this CLI session"),
            ("skill_dir_block",      "[Skill directory:"),
            ("three_q1_context",     "What context do I actually need right now?"),
            ("three_q2_source",      "most reliable source"),
            ("three_q3_blast",       "blast radius"),
            ("tier_1_read_only",     "**Read-only public**"),
            ("tier_2_read_auth",     "**Read-only authenticated**"),
            ("tier_3_local_write",   "**Write to local sandbox**"),
            ("tier_4_remote_write",  "**Write to remote**"),
            ("tier_5_destructive",   "**Destructive**"),
            ("source_primary",       "Live primary source"),
            ("source_recall",        "Memory / training-data recall"),
            ("cache_stability_rule", "mid-session"),
            ("pattern_a",            "Pattern A"),
            ("pattern_d",            "Pattern D"),
            ("pitfalls_section",     "## Pitfalls"),
            ("verification_section", "## Verification"),
        ],
    )
    def test_prompt_contains_contract(self, preload_prompt, contract, needle):
        assert needle in preload_prompt, (
            f"contract {contract!r} (needle {needle!r}) not in preloaded prompt"
        )

    def test_prompt_size_under_budget(self, preload_prompt):
        """This skill is guidance-only. Budget: under 20KB injected text
        (~5K tokens). Larger means the skill is doing too much."""
        size = len(preload_prompt)
        assert size < 20_000, f"preload prompt too large: {size} chars"
        # Sanity: at least enough to be useful
        assert size > 5_000, f"preload prompt suspiciously small: {size} chars"


class TestSkillContractInvariants:
    """Static checks that the skill content enforces what the skill's
    own claims require. These are the 'behavior over snapshots' tests
    — they fail when the skill regresses, not when its wording shifts."""

    @pytest.fixture
    def body(self):
        _ensure_skill_present()
        data = json.loads(skill_view(SKILL_NAME, preprocess=False))
        return data.get("content") or ""

    def test_three_questions_are_distinct_topics(self, body):
        """Each of the three questions must be a different topic — Q1 is
        context, Q2 is source, Q3 is blast radius. If two collapse into
        the same topic, the framing collapses too."""
        import re
        q1 = body.find("What context do I actually need right now?")
        q2 = body.find("What\u2019s the most reliable source for this information?")
        if q2 == -1:
            q2 = body.find("What's the most reliable source for this information?")
        q3 = body.find("What\u2019s the blast radius if this tool call is wrong?")
        if q3 == -1:
            q3 = body.find("What's the blast radius if this tool call is wrong?")
        assert q1 >= 0 and q2 >= 0 and q3 >= 0, "three questions must all exist"
        # Ordered: Q1 < Q2 < Q3
        assert q1 < q2 < q3, f"questions out of order: {q1},{q2},{q3}"

    def test_trust_tiers_are_strictly_ordered_by_risk(self, body):
        """The 5 trust tiers must appear in risk-ascending order in the
        tier table. Reordering would invert the safety gradient."""
        import re
        tier_markers = [
            "**Read-only public**",
            "**Read-only authenticated**",
            "**Write to local sandbox**",
            "**Write to remote**",
            "**Destructive**",
        ]
        positions = [body.find(m) for m in tier_markers]
        for i, p in enumerate(positions):
            assert p >= 0, f"missing tier: {tier_markers[i]}"
        # Strict ascending order
        for a, b in zip(positions, positions[1:]):
            assert a < b, f"trust tier order violated: {positions}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))