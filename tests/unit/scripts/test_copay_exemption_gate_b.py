"""Tests for §1.8 copay Gate B export and manifest bootstrap."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_RULES = _REPO / "data/gazette/prose_rules/copay_general_1_8.json"
_CORPUS = _REPO / "data/gazette/prose_corpus/L1.8_copay_exemption_prose.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L1.8_copay_exemption_encoded_manifest.json"


def test_gate_b_export_section_1_8_rows() -> None:
    from scripts.sut.prose.copay_exemption_gate_b import export_copay_exemption_candidates

    frame = export_copay_exemption_candidates(_CLAUSES)
    assert frame.height >= 60
    assert frame.height <= 110
    assert set(frame["section_id"].str.slice(0, 3).unique().to_list()) == {"1.8"}


def test_gate_b_export_schema() -> None:
    from scripts.sut.prose.copay_exemption_gate_b import export_copay_exemption_candidates

    frame = export_copay_exemption_candidates(_CLAUSES)
    assert list(frame.columns) == [
        "clause_id",
        "section_id",
        "deontic_modality",
        "category_hint",
        "encode_priority",
    ]
    assert set(frame["category_hint"].unique().to_list()) <= {"rate", "exemption"}
    assert frame.filter(pl.col("encode_priority") == "p1_encode").height >= 8


def test_json_rules_map_to_expected_clause_ids() -> None:
    from scripts.sut.prose.copay_exemption_gate_b import map_json_rules_to_clause_ids

    mapping = map_json_rules_to_clause_ids(_RULES, _CLAUSES)
    assert set(mapping) == {
        "1.8.1.(6).farkli_kurum_artis",
        "1.8.2.(1)",
        "1.8.2.(2)",
        "1.8.2.(3).enjektabl_kutu",
        "1.8.3.(1).protez_ortez",
        "1.8.3.(2)",
        "1.8.4.(1)",
        "1.8.5.(2).askeri_tatbikat",
        "1.8.5.(3).afet_savas_hali",
        "1.8.5.(4).kontrol_muayenesi",
        "1.8.5.(9).tibbi_sarf_malzeme",
        "1.8.5.(10).organ_nakli",
        "1.8.5.(14).kanun_2828",
        "1.8.5.(17).iade_malzeme",
        "1.8.5.(18).polis_akademisi",
        "1.8.5.(19).harp_okulu",
        "1.8.5.(20).deprem_protez",
    }
    assert mapping["1.8.2.(1)"] == ["C000314"]
    assert mapping["1.8.5.(10).organ_nakli"] == ["C000364"]


def test_manifest_has_gate_b_sources_encoded_union() -> None:
    from scripts.sut.prose.copay_exemption_gate_b import build_encoded_manifest

    manifest = build_encoded_manifest(_RULES, _CLAUSES)
    encoded = manifest["gate_b_sources_encoded"]
    assert len(encoded) >= 30
    assert len(encoded) <= 33
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
    assert manifest["rules_in_json"] == 17


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.copay_exemption_gate_b import write_gate_b_artifacts

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    write_gate_b_artifacts(
        clauses_path=_CLAUSES,
        rules_path=_RULES,
        corpus_csv=corpus,
        manifest_path=manifest_path,
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    corpus_df = pl.read_csv(corpus)
    assert corpus_df.height >= 60
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(payload["gate_b_sources_encoded"]) >= 18
