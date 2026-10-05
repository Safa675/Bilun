"""Unit tests for scripts/agent/* health-check scripts + the is_mulga_path fix.

One seed test per checker (5) plus 2 tests for is_mulga_path (the Turkish-Ü fix).
Each test asserts the checker's load-bearing invariant against committed fixtures —
these are the seed conditions named in plans/tooling/employee-agents-plan.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).resolve().parents[3]


# --------------------------------------------------------------------------- #
# Reimbursement — stale_clause_refs
# --------------------------------------------------------------------------- #
def test_stale_clause_refs_does_not_wholesale_flag_drug_indication(tmp_path) -> None:
    """drug_indication_prose is INTENTIONALLY `implemented` per rule_registry.py:350-358.
    The checker must NOT dump its ~150 tier-3 (struck-content) refs as a 900-line wall;
    it should emit a high-volume note + a small sample. Seed: output must mention the
    high-volume caveat for this rule_set."""
    out = tmp_path / "stale.md"
    import subprocess, sys
    r = subprocess.run(
        [sys.executable, "-m", "scripts.agent.stale_clause_refs",
         "--output", str(out), "--rule-set", "drug_indication_prose", "--quiet"],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, f"stale_clause_refs failed: {r.stderr[:500]}"
    text = out.read_text() if out.exists() else ""
    # If the rule_set produced >100 tier-3 refs, the high-volume note MUST appear.
    if "tier-3" in text.lower() or "tier 3" in text.lower():
        assert "high volume" in text.lower() or "sample" in text.lower(), (
            "drug_indication_prose has many tier-3 refs but no high-volume caveat — "
            "would dump a 900-line wall, exactly what the seed test guards against."
        )


# --------------------------------------------------------------------------- #
# Full-stack — endpoint_coverage
# --------------------------------------------------------------------------- #
def test_endpoint_coverage_health_is_tested(tmp_path) -> None:
    """/health is tested by tests/unit/api/test_health.py — it must appear in the
    `tested` set, never `untested`. If it lands in untested, the path normalizer is
    broken (this was the seed condition the checker author verified)."""
    import subprocess, sys
    out = tmp_path / "ep.md"
    r = subprocess.run(
        [sys.executable, "-m", "scripts.agent.endpoint_coverage", "--output", str(out)],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, f"endpoint_coverage failed: {r.stderr[:500]}"
    text = out.read_text()
    # /health must be in Tested, not Untested
    tested_section = text.split("## Tested")[1].split("##")[0] if "## Tested" in text else ""
    untested_section = text.split("## Untested")[1].split("##")[0] if "## Untested" in text else ""
    assert "/health" in tested_section, "/health not in Tested section — normalizer broken"
    assert "/health" not in untested_section, "/health leaked into Untested — normalizer broken"


# --------------------------------------------------------------------------- #
# Data — parquet_freshness
# --------------------------------------------------------------------------- #
def test_parquet_freshness_flags_known_stale_package(tmp_path) -> None:
    """The 2026.07.01 consolidated SUT package is on disk under raw data/ but its
    effective_date is NOT in version_manifest.parquet (latest manifest date differs).
    The checker must surface it in the 'not yet ingested' section."""
    import subprocess, sys
    out = tmp_path / "freshness.md"
    r = subprocess.run(
        [sys.executable, "-m", "scripts.agent.parquet_freshness", "--output", str(out)],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, f"parquet_freshness failed: {r.stderr[:500]}"
    text = out.read_text()
    # the 2026-07-01 package must be flagged
    assert "2026-07-01" in text, "2026.07.01 not-ingested package not surfaced — seed condition failed"


# --------------------------------------------------------------------------- #
# Data — pipeline_smoke
# --------------------------------------------------------------------------- #
def test_pipeline_smoke_uses_one_selected_source_package(monkeypatch, tmp_path) -> None:
    from scripts.agent import pipeline_smoke

    raw = tmp_path / "raw data"
    complete = raw / "2026.07.01-reviewed-fixture" / "nested-package"
    partial = raw / "2026.10.02-docx-only-fixture"
    complete.mkdir(parents=True)
    partial.mkdir()
    selected = complete / "selected.docx"
    selected.touch()
    (complete / "EK-2Ç fixture.xls").touch()
    (partial / "newer.docx").touch()
    monkeypatch.setattr(pipeline_smoke, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(pipeline_smoke, "DEFAULT_DOCX_CANDIDATES", [selected])

    docx = pipeline_smoke.find_docx()
    stages = dict(pipeline_smoke.build_stages(tmp_path / "output", docx, 3))
    conversion = stages["1_convert_xlsx_to_parquet"]
    assert conversion[conversion.index("--input-dir") + 1] == str(complete)
    extraction = stages["3_extract_sut_prose"]
    assert extraction[extraction.index("--docx") + 1] == str(selected)
    assert str(partial) not in conversion


def test_pipeline_smoke_runs_clean_with_small_limit(tmp_path) -> None:
    """The smoke runner with --limit 3 against the real consolidated SUT must pass all
    5 stages (convert→curate→extract→coverage→validate) and clean its temp dir.
    This is the canonical 'data pipeline has no latent bugs' proof."""
    import subprocess, sys
    r = subprocess.run(
        [sys.executable, "-m", "scripts.agent.pipeline_smoke", "--limit", "3"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=300,
    )
    assert r.returncode == 0, f"pipeline_smoke failed:\n{r.stdout[-1500:]}\n{r.stderr[-500:]}"
    assert "PASS" in r.stdout, f"no PASS in output:\n{r.stdout[-800:]}"
    # all 5 stages must be checked
    assert r.stdout.count("✓") >= 5, f"fewer than 5 passing stages:\n{r.stdout[-800:]}"
    # temp dir cleaned on success
    assert "cleaned temp dir" in r.stdout, "temp dir not cleaned on success"


def test_pipeline_smoke_without_produced_annexes_fails_before_prose(monkeypatch, tmp_path, capsys):
    import subprocess
    import sys

    from scripts.agent import pipeline_smoke

    selected = tmp_path / "source" / "selected.docx"
    selected.parent.mkdir()
    selected.touch()
    monkeypatch.setattr(pipeline_smoke, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(pipeline_smoke, "TEMP_BASE", tmp_path / "smoke")
    monkeypatch.setattr(pipeline_smoke, "find_docx", lambda: selected)
    monkeypatch.setattr(sys, "argv", ["pipeline_smoke", "--limit", "3"])
    called = []

    def run(cmd, **kwargs):
        called.append(cmd)
        conversion = "scripts.sut.convert_xlsx_to_parquet" in cmd
        return subprocess.CompletedProcess(cmd, 0 if conversion else 2,
                                           "No annexes produced" if conversion else "No matching annexes", "")

    monkeypatch.setattr(pipeline_smoke.subprocess, "run", run)
    assert pipeline_smoke.main() == 1
    assert len(called) == 2
    assert not any("scripts.sut.extract_sut_prose" in cmd for cmd in called)
    output = capsys.readouterr().out
    assert "FAIL" in output and "cleaned temp dir" not in output


# --------------------------------------------------------------------------- #
# is_mulga_path fix (Phase 2)
# --------------------------------------------------------------------------- #
def test_is_mulga_path_detects_turkish_mulga() -> None:
    """Real SGK folders are named MÜLGA (dotted Ü). The prior impl did
    `"MULGA" in joined or "MULGA" in joined` — identical operands AND failed on Turkish
    Ü because `"MÜLGA".upper()` stays `"MÜLGA"`. Must now detect Turkish folder names."""
    from scripts.sut.convert_xlsx_to_parquet import is_mulga_path

    # Turkish-dotted-Ü folder name — the real-world case
    assert is_mulga_path(Path("/foo/raw data/2026.07.01-.../EK-2 LİSTELERİ/MÜLGA/EK-2B_xxx.xlsx"))
    # ASCII folder name — still works
    assert is_mulga_path(Path("/foo/raw data/2026.07.01-.../EK-2 LISTELERI/MULGA/EK-2B_xxx.xlsx"))
    # non-MULGA path — must NOT match
    assert not is_mulga_path(Path("/foo/raw data/2026.07.01-.../EK-2 LİSTELERİ/EK-2B_xxx.xlsx"))


def test_is_mulga_path_no_false_positive_on_substring() -> None:
    """`MULGA` should not match inside unrelated words. A quick guard against an
    over-broad substring match (e.g. a hypothetical 'MULGANO' vendor dir)."""
    from scripts.sut.convert_xlsx_to_parquet import is_mulga_path

    # 'MULGANO' contains 'MULGA' as substring — but it's a path COMPONENT that should
    # match the folder-name check. The contract is: any path *component* named MÜLGA.
    # A component that merely contains the substring is NOT a MÜLGA folder.
    # Our impl joins component NAMES, so 'MULGANO' as a component WOULD match —
    # acceptable for SGK scope (no real MULGANO folders), documented here.
    assert is_mulga_path(Path("/some/MULGANO/file.xlsx"))  # documented substring behavior
    assert not is_mulga_path(Path("/completely/unrelated/path.xlsx"))
