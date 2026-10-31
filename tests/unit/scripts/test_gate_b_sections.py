"""The Gate B sections: what each one exports and what its committed manifest accounts for.

`compile_rules.py --check` in CI proves that every committed manifest equals a fresh compile, and
tests/unit/domain/prose_rules/test_drug_indication_clauses.py holds each clause group's rules and manifest facts.

The session rewrites the drug manifests from their traces before any test runs (tests/conftest.py), so on those
the counts and defer reasons below read the repaired file; that check is what sees a committed one that drifted.
The manifests of the other sections are read as committed.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from scripts.sut.prose.gate_b_audit import audit_gap_parity
from scripts.sut.prose.gate_b_generic import export_candidates, write_artifacts
from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
from tests.unit._helpers.brittle_guards import assert_audit_report_consistent, assert_manifest_consistent
from tests.unit._helpers.reviewed_clause_ids import reviewed_clause_ids

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_RULES = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
# §4.2.13 has no manifest of its own: its traces are in the manifest it shares with §4.2.16.
_WITH_MANIFEST = [name for name in ALL_SECTIONS if name != "4213"]


def _manifest(name: str) -> dict:
    return json.loads((_REPO / ALL_SECTIONS[name].manifest_path).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ALL_SECTIONS)
def test_a_section_exports_its_own_clauses(name: str) -> None:
    section = ALL_SECTIONS[name]
    frame = export_candidates(_CLAUSES, section)
    assert frame.height > 0
    assert {"clause_id", "section_id", "text_tr", "encode_tier", "encode_priority"} <= set(frame.columns)
    assert frame["clause_id"].n_unique() == frame.height
    assert all(section.match.matches(section_id) for section_id in frame["section_id"].to_list())


@pytest.mark.parametrize("name", _WITH_MANIFEST)
def test_a_committed_manifest_accounts_for_the_export(name: str) -> None:
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[name])
    manifest = _manifest(name)
    assert_manifest_consistent(manifest, frame)
    traces = manifest["clause_traces"]
    assert set(frame["clause_id"].to_list()) <= {trace["clause_id"] for trace in traces}
    deferred = [trace for trace in traces if trace["manifest_status"] == "tier_c_deferred"]
    assert [trace["clause_id"] for trace in deferred if not trace.get("defer_reason")] == []
    assert [trace["clause_id"] for trace in deferred if trace.get("defer_themes") is None] == []


@pytest.mark.parametrize("name", [name for name in _WITH_MANIFEST if ALL_SECTIONS[name].has_audit])
def test_the_honest_gap_audit_finds_no_untraced_clause(name: str) -> None:
    section = ALL_SECTIONS[name]
    manifest = _manifest(name)
    report = audit_gap_parity(
        _CLAUSES,
        manifest,
        section_prefix=section.manifest_section_id,
        matcher=section.match.matches,
        frame=export_candidates(_CLAUSES, section),
    )
    assert_audit_report_consistent(report, manifest)


def test_section_4_2_1_stops_before_4_2_10() -> None:
    matches = ALL_SECTIONS["4201"].match.matches
    assert matches("4.2.1") and matches("4.2.1.A") and matches("4.2.1.C-1")
    assert not matches("4.2.10") and not matches("4.2.19")


def test_writing_a_section_puts_every_clause_in_force_in_one_bucket(tmp_path: Path) -> None:
    source = pl.read_parquet(_CLAUSES).filter((pl.col("section_id") == "4.2.14.C") & pl.col("is_in_force"))
    in_force = set(source["clause_id"].to_list())
    _, manifest = write_artifacts(
        clauses_path=_CLAUSES,
        section=ALL_SECTIONS["4214c"],
        effective_date="2026-07-25",
        rules_path=_RULES,
        manifest_path=tmp_path / "manifest.json",
        write_corpus=False,
    )
    assert manifest["section_clause_total"] == len(in_force)
    assert manifest.get("clause_trace_complete") is True
    buckets = ("encoded", "emr_blocked", "non_actionable", "tier_c_deferred", "tier_a_pending", "tier_b_pending")
    assert set().union(*(manifest.get(f"{bucket}_clause_ids") or [] for bucket in buckets)) == in_force
    assert sorted(trace["clause_id"] for trace in manifest["clause_traces"]) == sorted(in_force)


def test_the_reviewed_tiers_of_4_2_13_hold() -> None:
    frame = export_candidates(_CLAUSES, ALL_SECTIONS["4213"])

    def tiers(*clause_ids: str) -> set[tuple[str, str]]:
        rows = frame.filter(pl.col("clause_id").is_in(reviewed_clause_ids(*clause_ids)))
        assert rows.height == len(clause_ids)
        return set(rows.select("encode_tier", "encode_priority").iter_rows())

    assert tiers("C004593") == {("C", "defer_tier_c")}  # the treatment-start heading
    assert tiers("C004638", "C004647") == {("B", "p2_encode")}  # the oral-switch sources
