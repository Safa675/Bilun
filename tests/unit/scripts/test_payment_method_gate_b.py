"""L2.2 Phase C0 Gate B export and manifest bootstrap."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
CLAUSES = ROOT / "data/gazette/sut_clauses.parquet"
PROSE_JSON = ROOT / "data/gazette/prose_rules/payment_method_2_2.json"
MANIFEST = ROOT / "data/gazette/prose_manifests/L2.2_payment_method_encoded_manifest.json"
CORPUS = ROOT / "data/gazette/prose_corpus/L2.2_payment_method_prose.csv"


@pytest.fixture(scope="module")
def gate_b_frame():
    from scripts.sut.prose.payment_method_gate_b import (
        enrich_gate_b_dataframe,
        load_candidate_clauses,
        run_gate_b_pipeline,
    )

    run_gate_b_pipeline(
        clauses_path=CLAUSES,
        prose_json_path=PROSE_JSON,
        corpus_csv_path=CORPUS,
        manifest_path=MANIFEST,
    )
    hit = load_candidate_clauses(CLAUSES)
    return enrich_gate_b_dataframe(hit)


def test_gate_b_exports_section_2_2_candidates(gate_b_frame) -> None:
    assert len(gate_b_frame) >= 80
    assert gate_b_frame["section_id"].str.starts_with("2.2").all()


def test_gate_b_csv_columns(gate_b_frame) -> None:
    for col in (
        "clause_id",
        "section_id",
        "text_tr",
        "deontic_modality",
        "encode_priority",
        "clause_coordinate",
    ):
        assert col in gate_b_frame.columns


def test_manifest_related_session_pricing_cross_ref() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    related = payload.get("related_rule_sets") or []
    assert related
    entry = related[0]
    assert entry["rule_set_id"] == "session_pricing_2_2_2_B"
    assert payload.get("session_fraction_status") == "PARTIAL"


def test_manifest_exists_with_encoded_clauses() -> None:
    assert MANIFEST.is_file()
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    encoded = payload.get("encoded_clause_ids") or payload.get("encoded_clause_ids") or []
    assert payload.get("rules_in_json", 0) >= 39
    assert len(encoded) >= 38


def test_prose_json_rules_have_gate_b_sources() -> None:
    payload = json.loads(PROSE_JSON.read_text(encoding="utf-8"))
    assert len(payload["rules"]) >= 39
    for rule in payload["rules"]:
        sources = rule.get("gate_b_sources") or []
        assert sources, f"missing gate_b_sources on {rule['rule_id']}"


def test_coverage_wires_payment_method_manifest() -> None:
    from scripts.sut.prose.coverage import _WAVE2_MANIFESTS

    for rule_id in (
        "payment_method_package",
        "payment_method_itemized",
        "payment_method_tier_override",
    ):
        assert _WAVE2_MANIFESTS[rule_id] == "L2.2_payment_method_encoded_manifest.json"


def test_coverage_wires_session_pricing_manifest() -> None:
    from scripts.sut.prose.coverage import _WAVE2_MANIFESTS

    assert (
        _WAVE2_MANIFESTS["drg_unbundling"]
        == "L2.2_session_pricing_2_2_2_B_encoded_manifest.json"
    )
