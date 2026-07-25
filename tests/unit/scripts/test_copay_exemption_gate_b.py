"""Tests for §1.8 copay Gate B export and manifest bootstrap."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from tests.unit._helpers.brittle_guards import (
    assert_audit_report_consistent,
    assert_manifest_consistent,
    soft_floor,
)

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_RULES = _REPO / "data/gazette/prose_rules/copay_general_1_8.json"
_CORPUS = _REPO / "data/gazette/prose_corpus/L1.8_copay_exemption_prose.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L1.8_copay_exemption_encoded_manifest.json"


def test_gate_b_export_section_1_8_rows() -> None:
    from scripts.sut.prose.copay_exemption_gate_b import export_copay_exemption_candidates

    frame = export_copay_exemption_candidates(_CLAUSES)
    soft_floor(frame.height, 60, label="copay export rows")
    assert set(frame["section_id"].str.slice(0, 3).unique().to_list()) == {"1.8"}


def test_gate_b_export_schema() -> None:
    from scripts.sut.prose.copay_exemption_gate_b import export_copay_exemption_candidates

    frame = export_copay_exemption_candidates(_CLAUSES)
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "category_hint",
        "encode_priority",
        "clause_coordinate",
    ):
        assert col in frame.columns
    assert set(frame["category_hint"].unique().to_list()) <= {"rate", "exemption"}
    assert frame.filter(pl.col("encode_priority") == "p1_encode").height >= 1


def test_json_rules_map_to_expected_clause_ids() -> None:
    from scripts.sut.prose.copay_exemption_gate_b import map_json_rules_to_clause_ids

    mapping = map_json_rules_to_clause_ids(_RULES, _CLAUSES)
    # Audit follow-up: added §1.8.1 base muayene schedule + family-physician 50%,
    # the §1.8.(4) refund, and 10 missed §1.8.5 exemption paragraphs.
    assert set(mapping) == {
        "1.8.(4).copay_refund_sydv",
        "1.8.1.(1).muayene_copay_schedule",
        "1.8.1.(6).farkli_kurum_artis",
        "1.8.1.family_physician_referral_50pct_reduction",
        "1.8.2.(1)",
        "1.8.2.(2)",
        "1.8.2.(3).enjektabl_kutu",
        "1.8.3.(1).protez_ortez",
        "1.8.3.(2)",
        "1.8.4.(1)",
        "1.8.5.(1).work_accident_occupational_disease",
        "1.8.5.(2).askeri_tatbikat",
        "1.8.5.(3).afet_savas_hali",
        "1.8.5.(4).kontrol_muayenesi",
        "1.8.5.(6).preventive_health_institution_funded",
        "1.8.5.(9).tibbi_sarf_malzeme",
        "1.8.5.(10).organ_nakli",
        "1.8.5.(11).istiklal_madalyasi_pensioner",
        "1.8.5.(12).vatani_hizmet_pensioner",
        "1.8.5.(13).nakdi_tazminat_pensioner",
        "1.8.5.(14).kanun_2828",
        "1.8.5.(15).harp_mallulu_terorle_mucadele",
        "1.8.5.(16).vazife_mallulu",
        "1.8.5.(17).iade_malzeme",
        "1.8.5.(18).polis_akademisi",
        "1.8.5.(19).harp_okulu",
        "1.8.5.(20).deprem_protez",
        "1.8.5.(21).wounded_3713_21",
        "1.8.5.(22)a.gss_5510_60_12",
        "1.8.5.(22)b.gss_5510_60_13_14",
    }
    # Phase 4.2: 1.8.2.(1) now carries 5 sub-bullet clause_ids (collection-channel
    # prose) in addition to the original C000314.
    assert mapping["1.8.2.(1)"] == ["C000314", "C000327", "C000328", "C000329", "C000330", "C000331"]
    assert mapping["1.8.5.(10).organ_nakli"] == ["C000364"]


def test_manifest_has_encoded_clause_ids_union() -> None:
    from scripts.sut.prose.copay_exemption_gate_b import build_encoded_manifest

    manifest = build_encoded_manifest(_RULES, _CLAUSES)
    encoded = manifest["encoded_clause_ids"]
    soft_floor(len(encoded), 30, label="copay encoded_clause_ids")
    assert "C000364" in encoded
    assert "C000361" in encoded
    assert "C000326" in encoded
    assert "C000362" in encoded
    assert "C000355" in manifest["compositor_clause_traces"]["copay_exemption_occupational"]
    patient_status = manifest["compositor_clause_traces"]["copay_exemption_patient_status"]
    assert "C000378" in patient_status
    assert "C000365" in patient_status
    assert "C000379" in patient_status
    assert "C000355" not in manifest["compositor_clause_traces"]["copay_exemption_visit_type"]
    soft_floor(int(manifest["rules_in_json"]), 21, label="test_copay_exemption_gate_b rules_in_json")


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.copay_exemption_gate_b import write_gate_b_artifacts

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    write_gate_b_artifacts(
        clauses_path=_CLAUSES,
        rules_path=_RULES,
        corpus_csv=corpus,
        manifest_path=manifest_path,
        write_corpus=True,
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    corpus_df = pl.read_csv(corpus)
    assert corpus_df.height >= 60
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(payload["encoded_clause_ids"]) >= 18
