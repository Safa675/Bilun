"""Track F — non-drug sections share the drug Gate B engine."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scripts.sut.prose.gate_b_generic import export_candidates, write_artifacts
from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[3]
_CLAUSES = _ROOT / "data/gazette/sut_clauses.parquet"


@pytest.mark.parametrize(
    "section_key,rule_json",
    [
        ("payment_22", "payment_method_2_2.json"),
        ("material_31_32", "material_bundling_prose.json"),
        ("copay_18", "copay_general_1_8.json"),
    ],
)
def test_nondrug_section_writes_canonical_manifest(
    section_key: str, rule_json: str, tmp_path: Path
) -> None:
    section = ALL_SECTIONS[section_key]
    assert section.rule_set_id != "drug_indication_prose"
    frame = export_candidates(_CLAUSES, section)
    assert frame.height > 0
    assert "clause_coordinate" in frame.columns

    manifest_path = tmp_path / "manifest.json"
    _, manifest = write_artifacts(
        clauses_path=_CLAUSES,
        section=section,
        effective_date=date.today().isoformat(),
        rules_path=_ROOT / "data/gazette/prose_rules" / rule_json,
        manifest_path=manifest_path,
        write_corpus=False,
    )
    assert manifest["manifest_version"] == "canonical-v1"
    assert manifest["rule_set_id"] == section.rule_set_id
    assert "encoded_clause_ids" in manifest
    assert "encoded_clause_coordinates" in manifest
    assert "clause_traces" in manifest
