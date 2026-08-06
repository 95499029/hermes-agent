"""Tests for hermes_cli/pii.py and hermes_cli/memory_consolidate.py.

Behaviour contracts:
- PII rules match the four categories (api key / id / phone / email).
- redact() returns the same length contract: count == matches.
- scan() and has_pii() agree with redact() for the same input.
- Consolidate dry-run never mutates the warm or cold files.
- Consolidate --apply moves expired cold files into stale/.
- Consolidate metrics always include timestamp + apply flag + ttl_days.
- Consolidate metrics JSON line is appended to logs/consolidate.jsonl.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


# --- fixtures ----------------------------------------------------------------

@pytest.fixture
def sandbox_home(tmp_path, monkeypatch):
    (tmp_path / "memories").mkdir(parents=True)
    (tmp_path / "memories" / "cold").mkdir(parents=True)
    (tmp_path / "logs").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def modules(sandbox_home):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from hermes_cli import pii, memory_consolidate

    return pii, memory_consolidate


# --- pii module --------------------------------------------------------------

class TestPii:
    def test_redacts_sk_api_key(self, modules):
        pii, _ = modules
        text = "token is sk-cp-abc123def456ghi789jkl012mno in env"
        out, n = pii.redact(text)
        assert n == 1
        assert "[REDACTED_API_KEY]" in out
        assert "sk-cp-abc" not in out

    def test_redacts_ghp_token(self, modules):
        pii, _ = modules
        text = "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        out, n = pii.redact(text)
        assert n == 1
        assert "ghp_" not in out

    def test_redacts_phone(self, modules):
        pii, _ = modules
        out, n = pii.redact("call 13812345678 today")
        assert n == 1 and "[REDACTED_PHONE]" in out

    def test_redacts_email(self, modules):
        pii, _ = modules
        out, n = pii.redact("ping me at ivan@example.com please")
        assert n == 1 and "[REDACTED_EMAIL]" in out

    def test_redacts_id_18_digit(self, modules):
        pii, _ = modules
        out, n = pii.redact("ID 11010519900307123X seen")
        assert n == 1 and "[REDACTED_ID]" in out

    def test_no_pii_returns_zero_count(self, modules):
        pii, _ = modules
        out, n = pii.redact("just a normal sentence about apples")
        assert n == 0 and out == "just a normal sentence about apples"

    def test_multiple_in_one_text(self, modules):
        pii, _ = modules
        text = "sk-aaaa1111bbbb2222cccc3333 ivan@test.com 13900000000"
        out, n = pii.redact(text)
        assert n == 3

    def test_scan_matches_redact_count(self, modules):
        pii, _ = modules
        text = "sk-aaaa1111bbbb2222cccc3333 and ivan@test.com"
        assert pii.scan(text) == pii.redact(text)[1]

    def test_has_pii_agrees_with_scan(self, modules):
        pii, _ = modules
        assert pii.has_pii("token sk-aaaa1111bbbb2222cccc3333") is True
        assert pii.has_pii("nothing here") is False

    def test_redact_preserves_surrounding_text(self, modules):
        pii, _ = modules
        text = "before sk-abcdefghijklmnopqrstuv after"
        out, _ = pii.redact(text)
        assert out.startswith("before ")
        assert out.endswith(" after")


# --- memory_consolidate ------------------------------------------------------

class TestConsolidatePiiScan:
    def test_dry_run_does_not_mutate(self, modules, sandbox_home):
        _, mc = modules
        # Plant PII in MEMORY.md and cold/.
        warm = sandbox_home / "memories" / "MEMORY.md"
        warm.write_text(
            "# Warm\n\n> meta\n\n## 工程协作偏好\n\n- sk-aaaa1111bbbb2222cccc3333 should never be here.\n",
            encoding="utf-8",
        )
        cold = sandbox_home / "memories" / "cold"
        (cold / "20260101T000000Z-secret.md").write_text(
            "# Archived 20260101T000000Z\n\ncontains sk-aaaa1111bbbb2222cccc3333\n",
            encoding="utf-8",
        )
        before = warm.read_bytes()
        cold_before = (cold / "20260101T000000Z-secret.md").read_bytes()
        # Dry-run --pii (default args do all)
        rc = mc.main(["--pii"])
        assert rc == 0
        # Files unchanged
        assert warm.read_bytes() == before
        assert (cold / "20260101T000000Z-secret.md").read_bytes() == cold_before

    def test_apply_redacts_warm(self, modules, sandbox_home):
        _, mc = modules
        warm = sandbox_home / "memories" / "MEMORY.md"
        warm.write_text(
            "# Warm\n\n> meta\n\n## 工程协作偏好\n\n- sk-aaaa1111bbbb2222cccc3333 should never be here.\n",
            encoding="utf-8",
        )
        mc.main(["--apply", "--pii"])
        text = warm.read_text()
        assert "sk-aaaa1111" not in text
        assert "[REDACTED_API_KEY]" in text

    def test_metrics_emitted_to_log(self, modules, sandbox_home):
        _, mc = modules
        log = sandbox_home / "logs" / "consolidate.jsonl"
        assert not log.exists()
        mc.main(["--json"])
        assert log.exists()
        line = log.read_text(encoding="utf-8").strip()
        rec = json.loads(line)
        assert "timestamp" in rec
        assert rec["apply"] is False
        assert "ttl_days" in rec


class TestConsolidateTtl:
    def test_dry_run_does_not_move(self, modules, sandbox_home):
        _, mc = modules
        cold = sandbox_home / "memories" / "cold"
        # 100-day-old file (yyyy=2026, mm=08, dd=06 minus 100 days ≈ 2026-04-28)
        old = cold / "20260428T000000Z-old-fact.md"
        old.write_text("# Archived\n\nancient fact\n", encoding="utf-8")
        rc = mc.main(["--ttl-demote", "--ttl", "30"])
        assert rc == 0
        assert old.exists()  # still in cold/
        assert not (cold / "stale").exists()

    def test_apply_moves_expired_files(self, modules, sandbox_home):
        _, mc = modules
        cold = sandbox_home / "memories" / "cold"
        old = cold / "20260428T000000Z-old-fact.md"
        old.write_text("# Archived\n\nancient fact\n", encoding="utf-8")
        rc = mc.main(["--apply", "--ttl-demote", "--ttl", "30"])
        assert rc == 0
        assert not old.exists()
        assert (cold / "stale" / "20260428T000000Z-old-fact.md").exists()

    def test_keeps_fresh_files(self, modules, sandbox_home):
        _, mc = modules
        cold = sandbox_home / "memories" / "cold"
        fresh = cold / "20260805T000000Z-fresh.md"
        fresh.write_text("# Archived\n\nrecent\n", encoding="utf-8")
        rc = mc.main(["--apply", "--ttl-demote", "--ttl", "30"])
        assert rc == 0
        assert fresh.exists()


class TestConsolidateRebalance:
    def test_dry_run_does_not_rebalance(self, modules, sandbox_home):
        _, mc = modules
        warm = sandbox_home / "memories" / "MEMORY.md"
        warm.write_text(
            "# Warm\n\n> meta\n\n## 工程协作偏好\n\n\n- non-empty\n",
            encoding="utf-8",
        )
        before = warm.read_bytes()
        mc.main(["--rebalance"])
        # Dry run should leave the file alone.
        assert warm.read_bytes() == before

    def test_apply_calls_rebalance(self, modules, sandbox_home):
        _, mc = modules
        warm = sandbox_home / "memories" / "MEMORY.md"
        # Plant a macOS-keyword fact under 工程协作偏好 — rebalance should
        # move it to macOS 环境.
        warm.write_text(
            "# Warm\n\n> meta\n\n## 工程协作偏好\n\n- macOS Python 3.9 太老\n",
            encoding="utf-8",
        )
        rc = mc.main(["--apply", "--rebalance"])
        assert rc == 0
        text = warm.read_text()
        provider_idx = text.index("## macOS 环境")
        fact_idx = text.index("Python 3.9")
        assert provider_idx < fact_idx


class TestConsolidateJson:
    def test_json_output_is_parseable(self, modules, sandbox_home, capsys):
        _, mc = modules
        rc = mc.main(["--all", "--json"])
        assert rc == 0
        captured = capsys.readouterr().out
        rec = json.loads(captured)
        assert rec["apply"] is False
        assert "passes" in rec
        assert "pii" in rec["passes"]
        assert "ttl_demote" in rec["passes"]
        assert "rebalance" in rec["passes"]


class TestConsolidateEndToEnd:
    def test_full_pipeline_apply(self, modules, sandbox_home):
        """promote → demote → consolidate (apply). All three pass without error."""
        _, mc = modules
        from hermes_cli import memory_tier, cold_search

        # Seed a memory file with a known fact.
        warm = sandbox_home / "memories" / "MEMORY.md"
        warm.write_text(
            "# Warm\n\n> meta\n\n## 工程协作偏好\n\n- end-to-end test fact goes here.\n",
            encoding="utf-8",
        )
        # Demote (this writes a cold archive + auto-rebuilds the FTS5 index).
        r = memory_tier.demote("end-to-end test fact")
        assert r["ok"] is True
        assert r["indexed"] is True

        # Confirm the index sees it.
        hits = cold_search.search("end-to-end")
        assert len(hits) >= 1

        # Consolidate dry run: must not raise, must emit metrics.
        rc = mc.main(["--all", "--json"])
        assert rc == 0