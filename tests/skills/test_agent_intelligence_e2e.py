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
            ("examples_section",     "## Examples"),
            ("example_1_gitlab",     "GitLab issue #1234"),
            ("example_2_cloudflare", "Cloudflare DNS for staging"),
            ("references_section",   "## References"),
            ("ref_trust_tier",       "trust-tier-examples.md"),
            ("ref_source_ranking",   "source-ranking-heuristics.md"),
            ("related_source_dev",   "source-driven-development"),
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


class TestSkillFilesystem:
    """The skill ships with companion reference files in references/.
    They must be present and loadable."""

    def _skill_root(self):
        return REPO_ROOT / "skills" / "software-development" / SKILL_NAME

    def test_references_dir_exists(self):
        d = self._skill_root() / "references"
        assert d.exists(), "references/ directory missing"
        assert d.is_dir()

    def test_trust_tier_reference_exists_and_substantial(self):
        f = self._skill_root() / "references" / "trust-tier-examples.md"
        assert f.exists(), f"missing: {f}"
        text = f.read_text(encoding="utf-8")
        # All five tiers should have at least one example under each
        for tier in ("Read-only public", "Read-only authenticated",
                     "Write to local sandbox", "Write to remote",
                     "Destructive"):
            assert tier in text, f"trust tier {tier!r} not in reference"
        assert len(text) >= 2_000, f"reference too thin: {len(text)} chars"

    def test_source_ranking_reference_exists_and_substantial(self):
        f = self._skill_root() / "references" / "source-ranking-heuristics.md"
        assert f.exists(), f"missing: {f}"
        text = f.read_text(encoding="utf-8")
        for tier in ("Live primary source", "Crawler-grade secondary",
                     "Search-aggregated", "Training-data recall"):
            assert tier in text, f"source tier {tier!r} not in reference"
        assert len(text) >= 2_000, f"reference too thin: {len(text)} chars"

    def test_preflight_checklist_reference_exists(self):
        f = self._skill_root() / "references" / "preflight-checklist.md"
        assert f.exists(), f"missing: {f}"
        text = f.read_text(encoding="utf-8")
        # All three questions must be referenced in the checklist
        for q in ("Context", "Source", "Blast"):
            assert q in text, f"checklist missing question: {q!r}"

    def test_soul_md_references_agent_intelligence(self):
        """The user-level SOUL.md must mention agent-intelligence so the
        agent knows to load it on new sessions."""
        soul = Path(r"J:\Hermes\SOUL.md")
        if not soul.exists():
            pytest.skip("SOUL.md not at J:\\Hermes\\SOUL.md")
        text = soul.read_text(encoding="utf-8")
        assert "agent-intelligence" in text, (
            "SOUL.md does not mention agent-intelligence — skill will not "
            "be auto-loaded by the routing logic"
        )
        # Must mention all three questions by name to bind the reference
        for q in ("context", "source", "blast radius"):
            assert q in text, f"SOUL.md missing one of context/source/blast radius: {q!r}"


class TestSelfCheckSection:
    """The SKILL.md self-check section is the in-skill version of
    preflight-checklist.md — same questions, same purpose. Keep them
    in sync or one of them rots."""

    @pytest.fixture
    def body(self):
        _ensure_skill_present()
        data = json.loads(skill_view(SKILL_NAME, preprocess=False))
        return data.get("content") or ""

    def test_self_check_section_present(self, body):
        assert "## Self-check" in body, "self-check section missing"

    def test_self_check_mentions_three_questions(self, body):
        # Find the Self-check section and verify it covers all three
        i = body.find("## Self-check")
        assert i >= 0
        # Self-check is followed by Verification; everything between is
        # the section's body.
        j = body.find("## Verification", i)
        assert j >= 0, "Verification section must follow Self-check"
        section = body[i:j]
        for q in ("Context", "Source", "Blast"):
            assert q in section, f"Self-check missing topic: {q}"


class TestCompanionFiles:
    """The skill ships a worked example and a self-verification script.
    Both must exist and be functional."""

    def _skill_root(self):
        return REPO_ROOT / "skills" / "software-development" / SKILL_NAME

    def test_conversation_example_exists(self):
        f = self._skill_root() / "references" / "conversation-1-gitlab-issue.md"
        assert f.exists(), f"missing: {f}"
        text = f.read_text(encoding="utf-8")
        assert len(text) >= 1_500, f"example too thin: {len(text)} chars"
        # Must contain the GitLab example by content (not just filename)
        assert "GitLab issue" in text
        # Must contrast with/without framing (this is the lesson)
        assert "without" in text.lower() and "with the framing" in text.lower()

    def test_verify_script_exists_and_runs_clean(self):
        f = self._skill_root() / "scripts" / "verify_skill.py"
        assert f.exists(), f"missing: {f}"
        # Run it; must exit 0 against the current skill root
        import subprocess
        r = subprocess.run(
            [sys.executable, str(f)],
            capture_output=True, text=True,
            cwd=str(self._skill_root()),
        )
        assert r.returncode == 0, (
            f"verify_skill.py failed (exit {r.returncode}): {r.stdout}\n{r.stderr}"
        )
        assert "OK" in r.stdout

    def test_verify_script_detects_missing_required_phrase(self):
        """Sanity: the verify script must actually catch a regression,
        not just always exit 0."""
        import subprocess
        import tempfile

        f = self._skill_root() / "scripts" / "verify_skill.py"
        # Make a tmp copy of the skill with a corrupted SKILL.md
        with tempfile.TemporaryDirectory() as tmp:
            tmp_skill = Path(tmp) / "agent-intelligence"
            shutil = __import__("shutil")
            shutil.copytree(self._skill_root(), tmp_skill)
            bad = tmp_skill / "SKILL.md"
            bad.write_text(
                bad.read_text(encoding="utf-8").replace(
                    "blast radius", "BLAST REMOVED"
                ),
                encoding="utf-8",
            )
            r = subprocess.run(
                [sys.executable, str(f), "--skill-root", str(tmp_skill)],
                capture_output=True, text=True,
            )
            assert r.returncode != 0, (
                "verify_skill.py did not catch the missing 'blast radius' phrase"
            )
            assert "blast radius" in r.stdout, (
                "verify_skill.py output should name the missing phrase"
            )

    def test_verify_script_supports_swarm_collaboration_profile(self):
        """verify_skill.py must support both bundled meta-skills via
        --skill. A regression that drops swarm-collaboration from
        the SKILL_PROFILES dict breaks the second-skill story."""
        import subprocess
        f = self._skill_root() / "scripts" / "verify_skill.py"
        # Help text must list both skills
        r = subprocess.run(
            [sys.executable, str(f), "--help"],
            capture_output=True, text=True,
        )
        assert "agent-intelligence" in r.stdout
        assert "swarm-collaboration" in r.stdout
        # Mutation: corrupt swarm-collaboration, verify catches it
        import tempfile
        swarm_root = (REPO_ROOT / "skills" / "autonomous-ai-agents"
                      / "swarm-collaboration")
        if not swarm_root.exists():
            pytest.skip("swarm-collaboration not in repo yet")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_skill = Path(tmp) / "swarm-collaboration"
            shutil = __import__("shutil")
            shutil.copytree(swarm_root, tmp_skill)
            bad = (tmp_skill / "SKILL.md").read_text(encoding="utf-8")
            bad = bad.replace("### 1. Direct result routing",
                               "### 1. REMOVED")
            (tmp_skill / "SKILL.md").write_text(bad, encoding="utf-8")
            r2 = subprocess.run(
                [sys.executable, str(f),
                 "--skill", "swarm-collaboration",
                 "--skill-root", str(tmp_skill)],
                capture_output=True, text=True,
            )
            assert r2.returncode != 0, (
                "verify_skill.py did not catch the missing "
                "'Direct result routing' principle"
            )
            assert "Direct result routing" in r2.stdout


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))