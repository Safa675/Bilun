"""Source-specific necessary facts, never inferred complete payment eligibility."""

from tests.unit._helpers.reviewed_clause_ids import reviewed_clause_id

from dataclasses import asdict, replace
from datetime import date, timedelta
import pytest
from src.bilun.domain.claims.clinical_evidence import IndicationEvidence
from src.bilun.domain.prose_rules._drug_indication.clinical_indications import evaluate_indications
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line

DAY = date(2026, 10, 2)


def line(drug="tenofovir", **values):
    return replace(
        _drug_line(
            drug_name=drug,
            report_present=True,
            report_duration_months=12,
            prescriber_specialty="hematoloji",
        ),
        drug_claim_date=DAY,
        indication_evidence=IndicationEvidence(
            **{"applies_on": DAY, "assessment_date": DAY, "phase": "initiation", **values}
        ),
    )


def hbv(**values):
    return line(
        **{
            "indication": "hbv_initiation_path_a",
            "age_group": "adult",
            "hbv_dna_iu_ml": 2000,
            "biopsy_scoring_system": "ishak_modified_hai",
            "biopsy_hai": 6,
            "biopsy_fibrosis_stage": 0,
            **values,
        }
    )


def noninvasive(**values):
    return hbv(
        **{
            "biopsy_hai": 0,
            "biopsy_fibrosis_stage": 0,
            "first_alt_uln_ratio": 1.1,
            "second_alt_uln_ratio": 1.1,
            "first_alt_date": date(2026, 7, 2),
            "second_alt_date": DAY,
            "fib4_score": 1.46,
            "apri_score": 0.4,
            **values,
        }
    )


def sc(**values):
    return line(
        "SCIG",
        **{
            "indication": "sc_ig_cll",
            "administration_route": "subcutaneous",
            "hypogammaglobulinemia": True,
            "recurrent_bacterial_infections": True,
            "prophylactic_antibiotics_failed": True,
            "report_author_specialty": "hematology",
            "prescribed_supply_months": 1,
            **values,
        },
    )


def bone(**values):
    return line(
        "denosumab",
        **{
            "indication": "glucocorticoid_bone_loss",
            "age_group": "adult",
            "osteoporosis_diagnosed": True,
            "high_fracture_risk": True,
            "long_term_glucocorticoid_treatment": True,
            "glucocorticoid_associated_bone_loss": True,
            "bisphosphonate_intolerant": True,
            **values,
        },
    )


def test_adult_hbv_dna_boundary_and_histology_source_compatibility_are_distinct():
    for case in (hbv(), hbv(biopsy_hai=0, biopsy_fibrosis_stage=2)):
        result = evaluate_indications(case)
        assert result["criterion_status"] == "unknown"
        assert (
            "indication_evidence.histology_scoring_source_compatibility" in result["missing_inputs"]
        )
    assert (
        evaluate_indications(hbv(hbv_dna_iu_ml=1999))["criterion_status"] == "restriction_not_met"
    )
    assert evaluate_indications(hbv(hbv_dna_iu_ml=None))["criterion_status"] == "unknown"


@pytest.mark.parametrize(
    "change",
    [
        {"fib4_score": 1.45, "apri_score": 0.5},
        {"first_alt_uln_ratio": 1},
        {"second_alt_uln_ratio": 1},
        {"first_alt_date": date(2026, 7, 3)},
    ],
)
def test_hbv_noninvasive_three_month_and_strict_threshold_negatives(change):
    assert evaluate_indications(noninvasive())["criterion_status"] == "criterion_clear"
    assert evaluate_indications(noninvasive(**change))["criterion_status"] == "unknown"


@pytest.mark.parametrize(
    "change",
    [
        {"first_alt_date": None},
        {"second_alt_date": DAY + timedelta(days=1)},
        {"first_alt_uln_ratio": None},
        {"fib4_score": None},
    ],
)
def test_hbv_noninvasive_missing_or_future_observations_remain_unknown(change):
    assert evaluate_indications(noninvasive(**change))["criterion_status"] == "unknown"


def test_hbv_noninvasive_alternative_clears_but_pediatric_histology_remains_source_review():
    assert (
        evaluate_indications(noninvasive(fib4_score=1.45, apri_score=0.51))["criterion_status"]
        == "criterion_clear"
    )
    for changes in (
        {"biopsy_hai": None, "biopsy_fibrosis_stage": 2},
        {"biopsy_hai": 4, "second_alt_uln_ratio": 2.01},
        {"biopsy_hai": 4, "second_alt_uln_ratio": 2},
    ):
        out = evaluate_indications(hbv(age_group="age_2_18", **changes))
        assert out["criterion_status"] == "unknown"
        assert "indication_evidence.histology_scoring_source_compatibility" in out["missing_inputs"]
    assert evaluate_indications(hbv(indication="other"))["criterion_status"] == "unknown"
    assert evaluate_indications(hbv(phase="continuation"))["criterion_status"] == "unknown"


def test_pediatric_hcv_requires_rna_and_genotype_and_shared_agent_uses_declared_path():
    facts = {
        "indication": "pediatric_chronic_hcv",
        "age_group": "child",
        "hcv_rna_positive": True,
        "hcv_genotype_result_present": True,
    }
    assert evaluate_indications(line("ribavirin", **facts))["criterion_status"] == "criterion_clear"
    for key in ("hcv_rna_positive", "hcv_genotype_result_present"):
        assert (
            evaluate_indications(line("ribavirin", **{**facts, key: False}))["criterion_status"]
            == "restriction_not_met"
        )
        assert (
            evaluate_indications(line("ribavirin", **{**facts, key: None}))["criterion_status"]
            == "unknown"
        )
    assert (
        evaluate_indications(line("ribavirin", **{**facts, "age_group": "adult"}))[
            "criterion_status"
        ]
        == "unknown"
    )
    assert (
        evaluate_indications(line("peginterferon", **facts))["criterion_status"]
        == "criterion_clear"
    )
    assert (
        evaluate_indications(replace(noninvasive(), drug_name="peginterferon"))["criterion_status"]
        == "criterion_clear"
    )


def test_sc_ig_cll_mm_and_transplant_are_distinct_source_alternatives():
    assert evaluate_indications(sc())["criterion_status"] == "criterion_clear"
    assert (
        evaluate_indications(
            sc(prophylactic_antibiotics_failed=False, prophylactic_antibiotics_contraindicated=True)
        )["criterion_status"]
        == "criterion_clear"
    )
    assert (
        evaluate_indications(
            sc(
                prophylactic_antibiotics_failed=False,
                prophylactic_antibiotics_contraindicated=False,
            )
        )["criterion_status"]
        == "restriction_not_met"
    )
    assert (
        evaluate_indications(sc(indication="sc_ig_mm", prophylactic_antibiotics_failed=None))[
            "criterion_status"
        ]
        == "criterion_clear"
    )
    assert (
        evaluate_indications(
            sc(
                indication="sc_ig_allogeneic_hsct",
                recurrent_bacterial_infections=None,
                prophylactic_antibiotics_failed=None,
                allogeneic_hsct_before_or_after=True,
            )
        )["criterion_status"]
        == "criterion_clear"
    )


def test_sc_ig_specialties_report_and_supply_caps_preserve_unknowns():
    for values in (
        {"hypogammaglobulinemia": False},
        {"report_author_specialty": "other"},
        {"prescribed_supply_months": 1.01},
    ):
        assert evaluate_indications(sc(**values))["criterion_status"] == "restriction_not_met"
    assert (
        evaluate_indications(replace(sc(), drug_report_duration_months=13))["criterion_status"]
        == "restriction_not_met"
    )
    for values in (
        {"hypogammaglobulinemia": None},
        {"report_author_specialty": None},
        {"prescribed_supply_months": 0},
        {"administration_route": "intravenous"},
    ):
        assert evaluate_indications(sc(**values))["criterion_status"] == "unknown"
    assert (
        evaluate_indications(replace(sc(), drug_report_duration_months=10**1000))[
            "criterion_status"
        ]
        == "unknown"
    )


def test_denosumab_requires_population_conjunction_and_any_prior_reason():
    assert evaluate_indications(bone())["criterion_status"] == "criterion_clear"
    assert (
        evaluate_indications(
            bone(bisphosphonate_intolerant=None, bisphosphonate_renal_contraindication=True)
        )["criterion_status"]
        == "criterion_clear"
    )
    for field in (
        "osteoporosis_diagnosed",
        "high_fracture_risk",
        "long_term_glucocorticoid_treatment",
        "glucocorticoid_associated_bone_loss",
    ):
        assert (
            evaluate_indications(bone(**{field: False}))["criterion_status"]
            == "restriction_not_met"
        )
        assert evaluate_indications(bone(**{field: None}))["criterion_status"] == "unknown"
    assert evaluate_indications(bone(indication="other"))["criterion_status"] == "unknown"


@pytest.mark.parametrize(
    "factory,section", [(hbv, "4.2.13.1"), (sc, "4.2.12.B-2"), (bone, "4.2.17.A")]
)
@pytest.mark.parametrize("day", [None, date(2026, 10, 3)])
def test_missing_future_source_date_never_infers_eligibility(factory, section, day):
    out = evaluate_indications(replace(factory(), drug_claim_date=day))
    assert out["criterion_status"] == "not_evaluated"
    assert out["sut_section"] == section


@pytest.mark.parametrize("factory,start_status", [(hbv, "unknown"), (sc, "criterion_clear")])
def test_november_2024_verified_commencement_is_inclusive(factory, start_status):
    original = factory()
    start = date(2024, 11, 9)
    for day, expected in [(start - timedelta(days=1), "not_evaluated"), (start, start_status)]:
        changed = replace(
            original,
            drug_claim_date=day,
            indication_evidence=replace(
                original.indication_evidence, applies_on=day, assessment_date=day
            ),
        )
        assert evaluate_indications(changed)["criterion_status"] == expected


def test_actual_pydantic_json_v2_and_row_transport():
    from src.bilun.shared.models import ClaimValidationRequest
    from src.bilun.domain.claims.adapter import build_context_from_material_dict
    from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
    from src.bilun.domain.claim_validation_v2 import validate_claim_v2, typed_validation_payload

    facts = asdict(noninvasive().indication_evidence)
    for k, v in list(facts.items()):
        if isinstance(v, date):
            facts[k] = v.isoformat()
    raw = {
        "claim_id": "hep",
        "materials": [{"name": "tenofovir", "indication_evidence": facts}],
        "drug_context": {
            "primary_icd10": "B18.1",
            "board_report_present": True,
            "service_date": DAY.isoformat(),
        },
    }
    req = ClaimValidationRequest.model_validate(raw)
    parsed = req.model_dump(mode="json")
    ctx = build_context_from_material_dict(parsed)
    errors = []
    assert (
        parse_drug_line(asdict(ctx.drug_lines[0]), errors).indication_evidence
        == ctx.drug_lines[0].indication_evidence
    )
    assert not errors
    output = typed_validation_payload(
        validate_claim_v2(parsed, supplied_claim=req.model_dump(mode="json", exclude_unset=True))
    )
    advisory = next(x for x in output["advisories"] if x["rule"] == "drug_indication")
    assert advisory["clinical_eligibility_complete"] is False
    assert advisory["clinical_restrictions"][0]["criterion_status"] == "criterion_clear"


def test_cleared_partial_check_and_unknown_medicine_combination_do_not_approve_payment():
    out = evaluate_drug_indication_line_detailed(
        drug_line=noninvasive(), claim=replace(_claim(), primary_icd10="B18.1"), diagnoses=[]
    )
    assert out["clinical_restrictions"][0]["criterion_status"] == "criterion_clear"
    assert out["clinical_eligibility_complete"] is False
    assert out["evaluation_status"] == "missing_inputs"
    out = evaluate_indications(replace(hbv(), drug_name="tenofovir + denosumab"))
    assert out["criterion_status"] == "unknown" and not out["source_refs"]


@pytest.mark.parametrize("field,value", [("biopsy_hai", 999), ("biopsy_fibrosis_stage", 999)])
def test_impossible_histology_values_never_clear_a_necessary_threshold(field, value):
    out = evaluate_indications(hbv(**{"biopsy_hai": 0, "biopsy_fibrosis_stage": 0, field: value}))
    assert out["criterion_status"] == "unknown"


def test_histology_scale_is_explicit_and_unknown_or_invalid_branch_cannot_block_other_route():
    assert evaluate_indications(hbv(biopsy_scoring_system=None))["criterion_status"] == "unknown"
    assert (
        evaluate_indications(noninvasive(biopsy_scoring_system=None))["criterion_status"]
        == "criterion_clear"
    )
    assert (
        evaluate_indications(
            hbv(biopsy_scoring_system="metavir", biopsy_hai=None, biopsy_fibrosis_stage=2)
        )["criterion_status"]
        == "unknown"
    )
    assert (
        evaluate_indications(
            hbv(biopsy_scoring_system="metavir", biopsy_hai=999, biopsy_fibrosis_stage=5)
        )["criterion_status"]
        == "unknown"
    )


def test_unknown_population_or_instrument_does_not_create_false_denial():
    assert (
        evaluate_indications(bone(age_group=None, osteoporosis_diagnosed=False))["criterion_status"]
        == "unknown"
    )
    assert evaluate_indications(hbv(biopsy_scoring_system="other"))["criterion_status"] == "unknown"


def test_flat_and_derived_failures_retain_bounded_public_explanation():
    for changed, field in [
        (replace(sc(), drug_report_duration_months=13), "drug_report_duration_months"),
        (replace(sc(), prescriber_specialty="nöroloji"), "prescriber_specialty"),
    ]:
        out = evaluate_indications(changed)
        assert out["criterion_status"] == "restriction_not_met"
        assert {"field": field, "status": "fail"} in out["checks"]
        assert all(set(check) == {"field", "status"} for check in out["checks"])


def test_source_keys_and_exact_hashes_match_captured_official_paragraphs():
    import json
    from pathlib import Path
    from scripts.sut.prose.clause_identity import content_hash

    root = Path(__file__).resolve().parents[4]
    capture = json.loads(
        (root / "data/gazette/clinical_sources/remaining_indications_2026_10.json").read_text()
    )
    rows = capture["clauses"]
    keys = {row["clause_key"] for row in rows}
    assert all(content_hash(row["in_force_text"]) == row["content_hash"] for row in rows)
    for case in (
        hbv(),
        sc(),
        bone(),
        line("ribavirin", indication="pediatric_chronic_hcv", age_group="child"),
    ):
        assert set(evaluate_indications(case)["source_refs"]) <= keys


@pytest.mark.parametrize(
    "factory,changes,section",
    [
        (hbv, {"hbv_dna_iu_ml": 1999}, "4.2.13.1"),
        (sc, {"hypogammaglobulinemia": False}, "4.2.12.B-2"),
        (bone, {"osteoporosis_diagnosed": False}, "4.2.17.A"),
    ],
)
def test_actual_request_to_v2_keeps_source_specific_negative_evidence(factory, changes, section):
    from src.bilun.shared.models import ClaimValidationRequest
    from src.bilun.domain.claim_validation_v2 import validate_claim_v2, typed_validation_payload

    case = factory(**changes)
    raw = {
        "claim_id": "necessary-negative",
        "materials": [
            {"name": case.drug_name, "indication_evidence": asdict(case.indication_evidence)}
        ],
        "drug_context": {
            "primary_icd10": "B18.1",
            "prescriber_specialty": "hematoloji",
            "board_report_present": True,
            "report_duration_months": 12,
            "service_date": DAY,
        },
    }
    req = ClaimValidationRequest.model_validate(raw)
    output = typed_validation_payload(
        validate_claim_v2(
            req.model_dump(mode="json"),
            supplied_claim=req.model_dump(mode="json", exclude_unset=True),
        )
    )
    advisory = next(x for x in output["advisories"] if x["rule"] == "drug_indication")
    actual = advisory["clinical_restrictions"][0]
    assert actual["criterion_status"] == "restriction_not_met"
    assert actual["source_refs"]
    assert any(c["status"] == "fail" for c in actual["checks"])
    assert advisory["clinical_eligibility_complete"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("biopsy_hai", 999),
        ("biopsy_fibrosis_stage", 999),
        ("hbv_dna_iu_ml", True),
        ("second_alt_uln_ratio", "2.1"),
    ],
)
def test_actual_api_parser_never_coerces_invalid_histology_or_numeric_facts(field, value):
    from src.bilun.shared.models import ClaimValidationRequest
    from src.bilun.domain.claims.adapter import build_context_from_material_dict

    facts = asdict(hbv().indication_evidence)
    facts[field] = value
    request = ClaimValidationRequest.model_validate(
        {
            "claim_id": "domain",
            "materials": [{"name": "tenofovir", "indication_evidence": facts}],
            "drug_context": {"service_date": DAY},
        }
    )
    assert getattr(request.materials[0].indication_evidence, field) is None
    line = build_context_from_material_dict(request.model_dump(mode="json")).drug_lines[0]
    assert getattr(line.indication_evidence, field) is None


@pytest.mark.parametrize("alt", [0, 1, None])
def test_disputed_apri_positive_alt_path_never_becomes_automatic_clearance_or_denial(alt):
    out = evaluate_indications(
        noninvasive(
            first_alt_uln_ratio=alt, second_alt_uln_ratio=alt, fib4_score=0, apri_score=0.51
        )
    )
    assert out["criterion_status"] == "unknown"
    assert "indication_evidence.hbv_noninvasive_boolean_grouping" in out["missing_inputs"]


def test_derived_interval_failure_is_observed_without_denying_unresolved_histology_route():
    out = evaluate_indications(noninvasive(first_alt_date=date(2026, 7, 3)))
    assert out["criterion_status"] == "unknown"
    assert {"field": "indication_evidence.alt_retest_interval", "status": "fail"} in out["checks"]


@pytest.mark.parametrize("name", ["peginterferon + ribavirin", "pegile interferon + tenofovir"])
def test_shared_agent_does_not_hide_a_second_active_medicine(name):
    out = evaluate_indications(replace(noninvasive(), drug_name=name))
    assert out["criterion_status"] == "unknown"
    assert out["source_refs"] == []


def test_hbv_numbered_source_items_are_stable_key_overrides_and_resolve_in_compiler():
    import polars as pl
    from pathlib import Path
    from scripts.sut.prose.clause_type_overrides import (
        apply_clause_type_overrides,
        load_clause_type_overrides,
    )
    from scripts.sut.prose.clause_identity import resolve_gate_b_ref_to_clause_ids

    root = Path(__file__).resolve().parents[4]
    frame = pl.read_parquet(root / "data/gazette/sut_clauses.parquet")
    keys = {"4.2.13.1#2076b8bd": (reviewed_clause_id("C004595"), 1), "4.2.13.1#50f88a7d": (reviewed_clause_id("C004596"), 2)}
    specs = {key: load_clause_type_overrides()[key] for key in keys}
    for prefix in ("", "shifted-"):
        changed = frame.with_columns((pl.lit(prefix) + pl.col("clause_id")).alias("clause_id"))
        patched = apply_clause_type_overrides(changed, specs)
        for key, (cid, number) in keys.items():
            assert resolve_gate_b_ref_to_clause_ids(key, patched, encode_eligible_only=True) == [
                prefix + cid
            ]
            row = patched.filter(pl.col("clause_id") == prefix + cid).row(0, named=True)
            assert row["clause_number"] == number
            assert row["clause_type"] == "numbered_item"


@pytest.mark.parametrize("indication", [None, "other", "hbv_initiation_path_a"])
def test_unselected_sc_branch_exposes_no_branch_b_clinical_checks(indication):
    out = evaluate_indications(sc(indication=indication, hypogammaglobulinemia=False))
    assert out["criterion_status"] == "unknown"
    assert out["checks"] == []
    assert out["missing_inputs"] == ["indication_evidence.indication"]


def test_bisphosphonate_failure_retains_parent_as_well_as_population_source():
    out = evaluate_indications(
        bone(
            bisphosphonate_intolerant=False,
            bisphosphonate_inadequate_response=False,
            bisphosphonate_renal_contraindication=False,
        )
    )
    assert out["criterion_status"] == "restriction_not_met"
    assert out["source_refs"] == ["4.2.17.A.(2)#ec5a2641", "4.2.17.A.b#21d7b36c"]
    assert {"field": "indication_evidence.bisphosphonate_intolerant", "status": "fail"} in out[
        "checks"
    ]
