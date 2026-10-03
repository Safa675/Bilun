"""Full-corpus review guards compose with families without manufacturing eligibility."""

from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import pytest
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line, _diagnosis
from src.bilun.domain.claims.clinical_evidence import EnteralEvidence
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
from src.bilun.api.public_responses import project_public_response

ROOT = Path(__file__).resolve().parents[4]
DAY = date(2026, 10, 2)
MDS_REVIEW = "4.2.9.A-2.darbepoetin_mds_source_review"
ADULT = "4.2.8.A.adult_malnutrition_1200kcal_3mo_report"


def rules():
    return json.loads((ROOT / "data/gazette/prose_rules/drug_indication_prose.json").read_text())[
        "rules"
    ]


def mds_line(drug="darbepoetin", day=DAY, **values):
    return replace(
        _drug_line(
            drug_name=drug,
            report_present=True,
            report_duration_months=1,
            prescriber_specialty="hematoloji",
        ),
        drug_claim_date=day,
        **values,
    )


@pytest.mark.parametrize("drug", ["darbepoetin", "aranesp"])
@pytest.mark.parametrize(
    "day,missing",
    [
        (None, "drug_claim_date"),
        (date(2024, 5, 16), "verified_source_for_service_date"),
        (date(2024, 5, 17), None),
        (DAY, None),
        (date(2026, 10, 3), "verified_source_for_service_date"),
    ],
)
def test_mds_review_interval_never_clears_or_retroactively_denies(drug, day, missing):
    for corpus in (rules(), list(reversed(rules()))):
        out = evaluate_drug_indication_line_detailed(
            drug_line=mds_line(drug, day),
            claim=_claim(primary_icd10="D46.1"),
            diagnoses=[],
            rules=corpus,
        )
        assert out["violation"]["severity"] == "review"
        assert out["selected_rule_id"] == MDS_REVIEW
        assert out["clinical_eligibility_complete"] is False
        review = out["clinical_restrictions"][0]
        assert review["criterion_status"] == "unknown" and review["checks"] == []
        assert "prose:4.2.9.A-2#17efb08b" in review["source_refs"]
        assert "4.2.9.A.(3)#a9d0cf5b" in review["source_refs"]
        if missing:
            assert missing in out["missing_inputs"]


@pytest.mark.parametrize("duration", [None, 0, 1, 3, 12])
def test_broader_legacy_report_discriminator_cannot_bypass_review(duration):
    out = evaluate_drug_indication_line_detailed(
        drug_line=mds_line(drug_report_duration_months=duration),
        claim=_claim(primary_icd10="D46.1"),
        diagnoses=[],
        rules=rules(),
    )
    assert out["selected_rule_id"] == MDS_REVIEW and out["violation"]["severity"] == "review"


@pytest.mark.parametrize("drug", ["darbepoetin", "aranesp"])
def test_pure_ckd_routing_is_byte_equivalent_with_and_without_mds_quarantine(drug):
    line = mds_line(drug, prescriber_specialty="nefroloji")
    claim = _claim(primary_icd10="N18.5")
    corpus = rules()
    kwargs = {"drug_line": line, "claim": claim, "diagnoses": []}
    before = evaluate_drug_indication_line_detailed(
        **kwargs, rules=[r for r in corpus if r["rule_id"] != MDS_REVIEW]
    )
    after = evaluate_drug_indication_line_detailed(**kwargs, rules=corpus)
    # Candidate inventory may add the MDS review route; operational selection,
    # status and clinical result for a pure CKD indication must not change.
    for key in ("selected_rule_id", "evaluation_status", "applicability_status", "missing_inputs"):
        assert after[key] == before[key]
    assert (after.get("violation") or {}).get("violation_kind") == (
        before.get("violation") or {}
    ).get("violation_kind")
    assert after.get("clinical_restrictions") == before.get("clinical_restrictions")
    assert after["selected_rule_id"] != MDS_REVIEW


def test_mixed_mds_ckd_diagnoses_remain_explicitly_ambiguous():
    claim = _claim(primary_icd10="D46.1")
    other = _diagnosis(code="N18.5", claim_id=claim.claim_id)
    out = evaluate_drug_indication_line_detailed(
        drug_line=mds_line(), claim=claim, diagnoses=[other], rules=rules()
    )
    assert out["applicability_status"] == "ambiguous_route"
    assert out["selected_rule_id"] is None
    assert out["violation"]["severity"] == "review"
    assert "route_discriminator" in out["missing_inputs"]
    assert MDS_REVIEW in out["eligible_route_rule_ids"]


@pytest.mark.parametrize("pediatric", [None, True, False])
def test_adult_guard_and_family_survive_canonical_and_public_projection(pediatric):
    evidence = None if pediatric is None else EnteralEvidence(pediatric=pediatric)
    line = replace(
        _drug_line(
            drug_name="enteral beslenme ürünü", report_present=True, report_duration_months=3
        ),
        drug_claim_date=DAY,
        enteral_evidence=evidence,
    )
    claim = _claim(primary_icd10="E43")
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(claim,),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(line,),
        diagnoses=(),
    )
    batch = evaluate_drug_indication_findings("P1", ctx, rules=rules())
    payload = {
        "evaluations": [x.to_dict() for x in batch.evaluations],
        "findings": [x.to_dict() for x in batch.findings],
        "violations": list(batch.legacy_violations),
    }
    public = project_public_response({"drug_indication": payload}, "get_billing_report")[
        "drug_indication"
    ]
    for key in ("evaluations", "findings", "violations"):
        row = public[key][0]
        assert row["selected_rule_id"] == ADULT
        assert row["clinical_eligibility_complete"] is False
        outcomes = row["clinical_restrictions"]
        assert any(o["constraint_set"] == "source_context_clinical_review" for o in outcomes)
        if pediatric is not False:
            assert any(o["constraint_set"] == "enteral_pediatric_reports_2026" for o in outcomes)
        assert all(o["clinical_eligibility_complete"] is False for o in outcomes)


@pytest.mark.parametrize("pediatric", [None, True, False])
def test_actual_typed_request_to_v2_keeps_composed_guard_and_identity(pediatric):
    from src.bilun.shared.models import ClaimValidationRequest
    from src.bilun.domain.claim_validation_v2 import typed_validation_payload, validate_claim_v2

    item = {"name": "enteral beslenme ürünü"}
    if pediatric is not None:
        item["enteral_evidence"] = {"pediatric": pediatric}
    req = ClaimValidationRequest.model_validate(
        {
            "claim_id": "scope",
            "materials": [item],
            "drug_context": {
                "service_date": DAY,
                "primary_icd10": "E43",
                "board_report_present": True,
                "report_duration_months": 3,
            },
        }
    )
    result = typed_validation_payload(
        validate_claim_v2(
            req.model_dump(mode="json"),
            supplied_claim=req.model_dump(mode="json", exclude_unset=True),
        )
    )
    row = next(r for r in result["advisories"] if r["rule"] == "drug_indication")
    assert row["selected_rule_id"] == ADULT
    assert row["clinical_eligibility_complete"] is False and row["disposition"] == "review_only"
    assert any(
        o["constraint_set"] == "source_context_clinical_review"
        for o in row["clinical_restrictions"]
    )
    assert result["is_valid"] is None


def test_genuine_family_failure_takes_priority_but_preserves_source_guard_and_receipts(monkeypatch):
    from src.bilun.domain.prose_rules._drug_indication import clinical

    line = mds_line()
    guard = {
        "constraint_set": "source_context_clinical_review",
        "criterion_status": "unknown",
        "checks": [],
        "missing_inputs": ["remaining_sut_clinical_criteria"],
        "source_refs": ["prose:4.2.9.A-2#17efb08b"],
    }
    base = {
        "clinical_restrictions": [guard],
        "selected_rule_id": MDS_REVIEW,
        "violation": {
            "rule_id": MDS_REVIEW,
            "selected_rule_id": MDS_REVIEW,
            "sut_section": "4.2.9.A-2",
            "severity": "review",
            "clinical_restrictions": [guard],
        },
    }
    failure = {
        "constraint_set": "independent_family",
        "criterion_status": "restriction_not_met",
        "checks": [{"field": "documented", "status": "fail"}],
        "missing_inputs": [],
        "source_refs": ["independent"],
        "sut_section": "4.2.99",
        "runtime_coverage": {"status": "unavailable"},
    }
    monkeypatch.setattr(clinical, "evaluate_clinical_restrictions", lambda *args: [failure])
    out = clinical.apply_clinical_restrictions(base, line, [])
    assert (
        out["selected_rule_id"] == "independent_family"
        and out["violation"]["sut_section"] == "4.2.99"
    )
    assert out["clinical_restrictions"] == [guard, failure]
    assert out["clinical_restrictions"][1]["runtime_coverage"] == failure["runtime_coverage"]


@pytest.mark.parametrize(
    "changes",
    [
        {"source_review_change_date": "2024-05-17T00:00:00"},
        {"source_review_change_date": "2026-10-03"},
        {"source_review_verified_through": None},
        {"source_review_quarantine": "true"},
        {"drug_names": []},
        {"icd10_ranges": []},
        {"source_clinical_scope_incomplete": False},
    ],
)
def test_authored_quarantine_requires_strict_dated_review_scope(changes):
    from scripts.sut.rule_sources import _validate_compile_invariants

    row = next(r for r in rules() if r["rule_id"] == MDS_REVIEW)
    with pytest.raises(ValueError):
        _validate_compile_invariants(
            {"rules": [{**row, **changes}]}, "drug_indication_prose", require_gate_b_sources=True
        )


def test_repeated_family_application_does_not_duplicate_inherited_review_outcomes(monkeypatch):
    from src.bilun.domain.prose_rules._drug_indication import clinical

    guard = {
        "constraint_set": "source_context_clinical_review",
        "criterion_status": "unknown",
        "checks": [],
        "missing_inputs": ["remaining_sut_clinical_criteria"],
        "source_refs": ["source"],
    }
    family = {
        "constraint_set": "other",
        "criterion_status": "unknown",
        "checks": [],
        "missing_inputs": ["assessment"],
        "source_refs": ["other"],
    }
    base = {
        "selected_rule_id": ADULT,
        "clinical_restrictions": [guard, family],
        "violation": {
            "rule_id": ADULT,
            "selected_rule_id": ADULT,
            "sut_section": "4.2.8.A",
            "severity": "review",
            "clinical_restrictions": [guard, family],
        },
    }
    monkeypatch.setattr(clinical, "evaluate_clinical_restrictions", lambda *args: [family])
    out = clinical.apply_clinical_restrictions(base, mds_line(), [])
    assert out["clinical_restrictions"] == [guard, family]
    assert out["selected_rule_id"] == ADULT and out["violation"]["sut_section"] == "4.2.8.A"


def test_actual_typed_mds_request_remains_unpriced_review_with_both_source_contexts():
    from src.bilun.shared.models import ClaimValidationRequest
    from src.bilun.domain.claim_validation_v2 import typed_validation_payload, validate_claim_v2

    request = ClaimValidationRequest.model_validate(
        {
            "claim_id": "mds",
            "materials": [{"name": "ARANESP"}],
            "drug_context": {
                "service_date": DAY,
                "primary_icd10": "D46.1",
                "board_report_present": True,
                "report_duration_months": 1,
                "prescriber_specialty": "hematoloji",
            },
        }
    )
    result = typed_validation_payload(
        validate_claim_v2(
            request.model_dump(mode="json"),
            supplied_claim=request.model_dump(mode="json", exclude_unset=True),
        )
    )
    row = next(item for item in result["advisories"] if item["rule"] == "drug_indication")
    assert row["selected_rule_id"] == MDS_REVIEW
    assert row["disposition"] == "review_only" and row["clinical_eligibility_complete"] is False
    refs = row["clinical_restrictions"][0]["source_refs"]
    assert "prose:4.2.9.A-2#17efb08b" in refs and "4.2.9.A.(3)#a9d0cf5b" in refs
    assert result["is_valid"] is None
    assert not any("amount" in key or "payable" in key for key in row)
