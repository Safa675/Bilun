"""Context repair cannot turn report metadata into clinical/payment clearance."""

from tests.unit._helpers.reviewed_clause_ids import reviewed_clause_id

from dataclasses import replace
import json
from pathlib import Path
import pytest
from scripts.sut.rule_sources import load_drug_section_rules
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from src.bilun.domain.prose_rules._drug_indication.routing import (
    _drug_rule_candidates,
    _select_semantically_equivalent_route,
)
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line

ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize(
    "section,drug,diagnosis,duration,specialty",
    [
        ("4.2.14.C", "pemetreksed", "C45.0", None, "tıbbi onkoloji"),
        ("4.2.14.C", "raltitreksed", "C45.0", None, "tıbbi onkoloji"),
        ("4.2.14.C", "raltitreksed", "C18.1", None, "tıbbi onkoloji"),
        ("4.2.9.A-2", "epoetin", "D46.1", None, "hematoloji"),
        ("4.2.8.A", "enteral beslenme ürünü", "E43", 3, "iç hastalıkları"),
        ("4.2.75", "vosoritide", "Q77.4", 12, "çocuk endokrinolojisi"),
    ],
)
def test_complete_existing_report_metadata_still_requires_unimplemented_clinical_scope(
    section, drug, diagnosis, duration, specialty
):
    rules = load_drug_section_rules(section)
    out = evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(
            drug_name=drug,
            report_present=True,
            report_duration_months=duration,
            prescriber_specialty=specialty,
        ),
        claim=replace(_claim(), primary_icd10=diagnosis),
        diagnoses=[],
        rules=rules,
    )
    assert out["violation"] is not None
    assert out["violation"]["severity"] == "review"
    assert "remaining_sut_clinical_criteria" in out["violation"]["missing_inputs"]
    assert out["violation"]["clinical_eligibility_complete"] is False
    assert out["violation"]["clinical_restrictions"][0]["criterion_status"] == "unknown"
    assert out["clinical_restrictions"] == out["violation"]["clinical_restrictions"]
    assert out["clinical_eligibility_complete"] is False


def test_review_scope_is_operational_route_semantics_not_order_dependent_metadata():
    plain = {"rule_id": "a", "report_required": True}
    guarded = {**plain, "rule_id": "b", "source_clinical_scope_incomplete": True}
    assert _select_semantically_equivalent_route([plain, guarded]) is None
    assert _select_semantically_equivalent_route([guarded, plain]) is None


def test_changed_mds_substances_only_select_explicit_review_quarantine():
    mds = load_drug_section_rules("4.2.9.A-2")
    for name in ("darbepoetin", "aranesp"):
        hits = _drug_rule_candidates(name, mds)[0]
        assert [row["rule_id"] for row in hits] == ["4.2.9.A-2.darbepoetin_mds_source_review"]
        assert hits[0]["source_review_quarantine"] is True
        assert "pay" not in hits[0]
    vos = load_drug_section_rules("4.2.75")
    assert _drug_rule_candidates("vosoritide", vos)[0]
    assert not _drug_rule_candidates("somatropin", vos)[0]


def test_nonpredicate_context_fragments_are_retired_from_the_executable_corpus():
    rules = load_drug_section_rules("4.2.16")
    assert not any(".amount_paid_coverage_" in r["rule_id"] for r in rules)
    capture = json.loads(
        (ROOT / "data/gazette/clinical_sources/source_context_repairs_2026_10.json").read_text()
    )
    rows = capture["retired_nonpredicate_rule_rows"]
    assert len(rows) == 2 and rows[0]["source_context_refs"] != rows[1]["source_context_refs"]
    for r in rows:
        assert r["gate_b_sources"] == []
        assert not _drug_rule_candidates("protein diet product", [r])[0]
        assert not any(k in r for k in ["amount", "unit_price", "pay", "clinical_constraint_set"])


def test_mesothelioma_and_colorectal_report_composition_are_not_transferred():
    rows = {r["rule_id"]: r for r in load_drug_section_rules("4.2.14.C")}
    for drug in ("pemetrexed", "raltitrexed"):
        r = rows[f"4.2.14.C.{drug}_mesothelioma_board"]
        assert r["icd10_ranges"] == ["C45"]
        assert not r.get("report_specialties")
    colorectal = rows["4.2.14.C.raltitrexed_colorectal_board"]
    assert colorectal["icd10_ranges"] == ["C18-C20"]
    assert colorectal["report_specialties"] == ["tıbbi onkoloji"]


def test_all_seven_context_records_resolve_unique_original_items_without_encoding_predicates():
    import polars as pl
    from scripts.sut.prose.clause_identity import (
        assert_gate_b_sources_resolvable,
        resolve_gate_b_ref_to_clause_ids,
        encoded_clause_ids_from_rules,
    )

    frame = pl.read_parquet(ROOT / "data/gazette/sut_clauses.parquet")
    data = json.loads(
        (ROOT / "data/gazette/clinical_sources/source_context_repairs_2026_10.json").read_text()
    )
    assert len(data["entries"]) == 7
    for row in data["entries"]:
        refs = row["source_context_refs"]
        assert resolve_gate_b_ref_to_clause_ids(refs[0], frame) == [reviewed_clause_id(row["baseline_inventory_id"])]
        as_rule = {"rule_id": row["baseline_inventory_id"], "source_context_refs": refs}
        assert_gate_b_sources_resolvable([as_rule], frame)
        assert encoded_clause_ids_from_rules([as_rule], frame) == set()


@pytest.mark.parametrize(
    "section,drug,diagnosis,duration",
    [
        ("4.2.14.C", "pemetreksed", "C34.9", None),
        ("4.2.8.A", "enteral beslenme ürünü", "E43", 6),
    ],
)
def test_context_guard_does_not_transfer_to_independent_routes(section, drug, diagnosis, duration):
    out = evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(
            drug_name=drug,
            report_present=True,
            report_duration_months=duration,
            prescriber_specialty="tıbbi onkoloji",
        ),
        claim=replace(_claim(), primary_icd10=diagnosis),
        diagnoses=[],
        rules=load_drug_section_rules(section),
    )
    nested = (out.get("violation") or {}).get("clinical_restrictions", [])
    assert not any(r["constraint_set"] == "source_context_clinical_review" for r in nested)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_clinical_scope_incomplete", "true"),
        ("source_context_refs", "key"),
        ("source_context_refs", []),
        ("source_context_refs", [None]),
    ],
)
def test_malformed_source_scope_metadata_is_rejected_at_compile_boundary(field, value):
    from scripts.sut.rule_sources import _validate_compile_invariants

    with pytest.raises(ValueError):
        _validate_compile_invariants(
            {
                "rules": [
                    {"rule_id": "malformed", "gate_b_sources": ["4.2.75.a#e84a7b6d"], field: value}
                ]
            },
            "drug_indication_prose",
            require_gate_b_sources=True,
        )


@pytest.mark.parametrize("report_present", [True, False, None])
def test_source_review_guard_never_equates_generic_board_flag_with_mds_specialist_report(
    report_present,
):
    out = evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(
            drug_name="epoetin", report_present=report_present, prescriber_specialty="hematoloji"
        ),
        claim=replace(_claim(), primary_icd10="D46.1"),
        diagnoses=[],
        rules=load_drug_section_rules("4.2.9.A-2"),
    )
    assert out["violation"]["severity"] == "review"
    assert out["violation"]["clinical_restrictions"][0]["checks"] == []
    assert out["violation"]["clinical_restrictions"][0]["criterion_status"] == "unknown"
