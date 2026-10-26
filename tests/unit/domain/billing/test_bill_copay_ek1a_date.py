"""A bill's report reads EK-1/A on that bill's own date, not on the patient's latest claim (#292, WP36).

WP26 gave the copay input a date: a patient's input reads EK-1/A on its latest claim's date, a one-bill input on
its own date. The cache build's bill reports (`compute_all_bill_billing_reports`) took the patient's result, so a
bill served before an EK-1/A change was read on the list of the patient's latest bill. The curated list changes on
2015-08-05 (N04, Q05, Q78 added) and on 2018-02-15 (G11.3 added). The patient's own report, its alert row and the
optimization summary stay as they were; the emergency ground stays per bill (WP23).
"""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import polars as pl
import pytest

from src.bilun.domain.billing.cohort_runner import bill_copay_exemption
from src.bilun.domain.claims.dataset import SUTClaimDataset
from src.bilun.domain.claims.models import ClaimHeader, PatientCopayProfile, ProcedureClaimLine
from src.bilun.domain.optimization.copay_exemption_context import (
    bill_copay_exemption_input,
    build_copay_exemption_input,
)
from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

pytestmark = pytest.mark.unit

_PID = "P-EK1A"
# The clinical feed lists the principal codes sorted: G11.3 before N04.
_DIAGNOSES = ["G11.3", "N04"]
# One bill on each side of each change: the day before and the first day.
_DAYS = {
    "C-150804": date(2015, 8, 4),
    "C-150805": date(2015, 8, 5),
    "C-180214": date(2018, 2, 14),
    "C-180215": date(2018, 2, 15),
}
_QUALIFYING = {
    "C-150804": [],
    "C-150805": ["N04"],
    "C-180214": ["N04"],
    "C-180215": ["G11.3", "N04"],
}
_DISEASE = {
    "N04": "Nefrotik Sendrom",
    "G11.3": "Defektif DNA tamiri ile birlikte olan serebellar ataksi",
}
_ORDERS = {
    "oldest-first": ("C-150804", "C-150805", "C-180214", "C-180215"),
    "latest-first": ("C-180215", "C-180214", "C-150805", "C-150804"),
    "interleaved": ("C-180214", "C-150804", "C-180215", "C-150805"),
}


def _claim(claim_id: str, day: date, *, claim_type: str = "poliklinik") -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id=_PID,
        episode_id=f"E-{claim_id}",
        claim_type=claim_type,
        facility_tier="2",
        provider_type="kamu",
        department="acil" if claim_type == "acil" else "dahiliye",
        admission_date=None,
        discharge_date=None,
        claim_start_date=day,
        claim_end_date=day,
        primary_icd10="N04",
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _exam(claim: ClaimHeader) -> ProcedureClaimLine:
    """An examination billed 100 TRY, 70 TRY payable: a 30 TRY share."""
    return ProcedureClaimLine(
        procedure_line_id=f"PL-{claim.claim_id}",
        claim_id=claim.claim_id,
        patient_id=_PID,
        episode_id=claim.episode_id,
        procedure_date=claim.claim_start_date,
        procedure_code="520030",
        procedure_name="Muayene",
        procedure_category="muayene",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("70"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _profile(report: bool | None) -> PatientCopayProfile:
    return PatientCopayProfile(patient_id=_PID, birth_year=1960, has_chronic_health_report=report)


def _dataset(claims: tuple[ClaimHeader, ...], report: bool | None) -> SUTClaimDataset:
    exams = tuple(_exam(claim) for claim in claims)
    empty: dict[str, Any] = {field.name: {} for field in fields(SUTClaimDataset)}
    return SUTClaimDataset(
        **{
            **empty,
            "medula_rejection_ingest_available": False,
            "claims": {claim.claim_id: claim for claim in claims},
            "claims_by_patient": {_PID: claims},
            "procedure_lines": {line.procedure_line_id: line for line in exams},
            "procedure_lines_by_claim": {line.claim_id: (line,) for line in exams},
            "procedure_lines_by_patient": {_PID: exams},
            "copay_profiles_by_patient": {_PID: _profile(report)},
        }
    )


def _cache_build(monkeypatch: pytest.MonkeyPatch, dataset: SUTClaimDataset) -> dict[str, Any]:
    """The app's cache build (`_assemble_sut_and_billing_context`) over `dataset`, the patient's diagnoses in the
    clinical feed."""
    from src.bilun.cache import context

    monkeypatch.setattr(context, "load_sut_claim_dataset", lambda **_: dataset)
    source = SimpleNamespace(
        claims_dir=None, mode="synthetic_demo", metadata=SimpleNamespace(as_dict=dict)
    )
    return context._assemble_sut_and_billing_context(
        ana_df=pl.DataFrame({"patient_id": [_PID, _PID], "TANIKODU": _DIAGNOSES}),
        lab_df=pl.DataFrame(),
        rec_df=pl.DataFrame(),
        patient_ids=[_PID],
        billing_workers=None,
        sut_data_source=source,
    )


def _ek1a_codes(sources: list[dict[str, Any]]) -> list[str]:
    for source in sources:
        if source.get("category") == "ek1a_chronic":
            return [row["icd10"] for row in source["evidence"]["qualifying_diagnoses"]]
    return []


def _message_codes(copay) -> list[str]:
    return [
        str(row.get("message_code") or row.get("sut_section")) for row in copay.rate_corrections
    ]


# --- the cache build: each bill on its own date ------------------------------------------------------------------


@pytest.mark.parametrize("order", list(_ORDERS), ids=list(_ORDERS))
@pytest.mark.parametrize("report", [True, None], ids=["report-on-file", "report-unknown"])
def test_each_bill_report_reads_ek1a_on_its_own_date(
    monkeypatch: pytest.MonkeyPatch, order: str, report: bool | None
) -> None:
    claims = tuple(_claim(cid, _DAYS[cid]) for cid in _ORDERS[order])
    built = _cache_build(monkeypatch, _dataset(claims, report))
    bills = built["bill_billing_reports"]
    assert sorted(bills) == sorted(f"{_PID}::{cid}" for cid in _DAYS)

    matched = "exempt" if report else "partial_exempt"
    for cid, codes in _QUALIFYING.items():
        copay = bills[f"{_PID}::{cid}"].copay
        assert _ek1a_codes(copay.exemption_sources) == codes, cid
        assert copay.copay_primary_outcome == (matched if codes else "none"), cid
        assert copay.is_exempt is bool(report and codes), cid
        assert copay.exemption_disease == _DISEASE.get(codes[0] if codes else "", ""), cid
        # the share of the bill's examination is waived only where EK-1/A matches and the report is on file
        assert copay.visit_copay_savings_try == pytest.approx(30.0 if report and codes else 0.0), (
            cid
        )
        assert ("ek1a_report_unknown" in _message_codes(copay)) is (
            report is None and bool(codes)
        ), cid

    # The patient as a whole is read on its latest bill, as before: both diagnoses, every share waived.
    patient = built["billing_reports"][_PID].copay
    assert _ek1a_codes(patient.exemption_sources) == ["G11.3", "N04"]
    assert patient.copay_primary_outcome == matched
    assert patient.exemption_disease == _DISEASE["G11.3"]
    assert patient.visit_copay_savings_try == pytest.approx(120.0 if report else 0.0)
    (alert,) = built["patient_alerts_cache"]["patients"]
    assert _ek1a_codes(alert["copay_exemption"]["exemption_sources"]) == ["G11.3", "N04"]
    assert alert["copay_exemption"]["outcome_kind"] == matched
    # The summary's bill counts were already per bill (WP26): the bill reports now agree with them.
    summary = built["optimization_summary"]["copay_exemptions"]
    assert (summary["n_exempt_patients"], summary["n_total_bills"]) == (1 if report else 0, 4)
    assert summary["n_exempt_bills"] == (3 if report else 0)


def test_the_emergency_ground_stays_on_the_er_bill(monkeypatch: pytest.MonkeyPatch) -> None:
    """An ER visit on 2015-08-04 (before N04 and G11.3 enter EK-1/A) and a visit on 2018-02-15, report on file.

    The patient is exempt on EK-1/A as of 2018-02-15. The ER bill is exempt on the emergency ground (SUT
    1.8.5.(5), its own bill: WP23), with no EK-1/A ground of its date; the visit is exempt on EK-1/A only.
    """
    er, visit = (
        _claim("C-ER", date(2015, 8, 4), claim_type="acil"),
        _claim("C-VISIT", date(2018, 2, 15)),
    )
    built = _cache_build(monkeypatch, _dataset((er, visit), True))

    er_copay = built["bill_billing_reports"][f"{_PID}::C-ER"].copay
    assert (er_copay.is_exempt, er_copay.primary_exemption_category) == (True, "acil_servis")
    assert [source["category"] for source in er_copay.exemption_sources] == ["acil_servis"]
    assert er_copay.exemption_disease == ""
    assert {row["exemption_ground"] for row in er_copay.rate_corrections} == {
        "composite_acil_servis"
    }

    visit_copay = built["bill_billing_reports"][f"{_PID}::C-VISIT"].copay
    assert (visit_copay.is_exempt, visit_copay.primary_exemption_category) == (True, "ek1a_chronic")
    assert [source["category"] for source in visit_copay.exemption_sources] == ["ek1a_chronic"]
    assert _ek1a_codes(visit_copay.exemption_sources) == ["G11.3", "N04"]

    patient = built["billing_reports"][_PID].copay
    assert (patient.is_exempt, patient.primary_exemption_category) == (True, "ek1a_chronic")
    assert [source["category"] for source in patient.exemption_sources] == [
        "ek1a_chronic",
        "acil_servis",
    ]


def test_the_cache_build_hands_the_copay_inputs_to_the_bill_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claims = tuple(_claim(cid, _DAYS[cid]) for cid in _ORDERS["oldest-first"])
    dataset = _dataset(claims, True)
    from src.bilun.cache import context

    seen: dict[str, Any] = {}

    def bill_runner(cache: dict[str, Any], **_: Any) -> dict[str, Any]:
        seen.update(cache)
        return {}

    real = context.assemble_billing_context
    monkeypatch.setattr(
        context,
        "assemble_billing_context",
        lambda **kwargs: real(**{**kwargs, "compute_all_bill_billing_reports_fn": bill_runner}),
    )
    _cache_build(monkeypatch, dataset)
    (patient_input,) = seen["copay_inputs_by_pid"].values()
    assert patient_input.diagnoses == _DIAGNOSES
    assert patient_input.service_date == date(2018, 2, 15)
    assert patient_input.has_chronic_health_report is True


# --- the bill's input and its fallbacks --------------------------------------------------------------------------


def _patient_input(*claims: ClaimHeader) -> CopayExemptionInput:
    return build_copay_exemption_input(
        diagnoses=_DIAGNOSES, patient_profile=_profile(True), patient_claims=claims
    )


def test_a_bills_input_changes_the_date_only() -> None:
    claims = tuple(_claim(cid, day) for cid, day in _DAYS.items())
    patient = _patient_input(*claims)
    assert patient.service_date == date(2018, 2, 15)
    for claim in claims:
        bill = bill_copay_exemption_input(patient, claim)
        assert bill == replace(patient, service_date=claim.claim_start_date)
    assert patient.service_date == date(2018, 2, 15)  # the patient's input is not changed


def test_a_stays_bill_is_read_on_its_admission_date() -> None:
    stay = replace(
        _claim("C-STAY", date(2018, 2, 15), claim_type="yatan"),
        admission_date=date(2018, 2, 14),
        discharge_date=date(2018, 2, 16),
        claim_end_date=date(2018, 2, 16),
    )
    patient = _patient_input(stay, _claim("C-LATER", date(2019, 1, 2)))
    exemption = bill_copay_exemption(_PID, stay, {}, {_PID: patient})
    assert _ek1a_codes(exemption["exemption_sources"]) == ["N04"]


def test_a_bill_without_a_date_keeps_the_patients_date() -> None:
    """date.min is the loader's "date unknown": the bill is read on the patient's latest bill (2015-08-05: N04
    only), not on today (N04 and G11.3)."""
    undated = replace(_claim("C-UNDATED", date.min), claim_end_date=date.min)
    patient = _patient_input(_claim("C-150805", date(2015, 8, 5)), undated)
    assert patient.service_date == date(2015, 8, 5)
    assert bill_copay_exemption_input(patient, undated) is patient
    exemption = bill_copay_exemption(_PID, undated, {}, {_PID: patient})
    assert _ek1a_codes(exemption["exemption_sources"]) == ["N04"]


def test_without_an_input_the_bill_reuses_the_patients_result() -> None:
    """A cache built without copay inputs (an older caller) keeps today's behaviour: the alert's result."""
    claim = _claim("C-150804", date(2015, 8, 4))
    cached = {"exempt": True, "exemption_sources": [{"category": "ek1a_chronic"}]}
    alerts = {_PID: {"copay_exemption": cached}}
    assert bill_copay_exemption(_PID, claim, alerts, {}) is cached
    assert bill_copay_exemption(_PID, claim, alerts, {"P-OTHER": _patient_input(claim)}) is cached
    assert bill_copay_exemption(_PID, claim, {}, {}) == {
        "exempt": False,
        "n_qualifying": 0,
        "qualifying_diagnoses": [],
    }


def test_a_bill_of_the_patients_latest_version_gets_the_patients_result() -> None:
    claims = tuple(_claim(cid, _DAYS[cid]) for cid in _ORDERS["interleaved"])
    patient = _patient_input(*claims)
    latest = next(claim for claim in claims if claim.claim_id == "C-180215")
    assert bill_copay_exemption(_PID, latest, {}, {_PID: patient}) == evaluate_copay_exemption(
        patient
    )


# --- the committed demo cohort ------------------------------------------------------------------------------------


def test_on_the_demo_no_bill_straddles_an_ek1a_change() -> None:
    """Every demo bill is dated after 2018-02-15, the list's last change: each bill's exemption is its patient's, so
    no committed report moves (the app path's inputs, as `assemble_sut_context` builds them)."""
    from scripts.synthetic.cohort.coverage_metrics import DEFAULT_CLAIMS_DIR
    from scripts.synthetic.cohort.engine_proof import load_showcase_dataset
    from src.bilun.cache.data_loader import load_anadata
    from src.bilun.cache.loaders import load_normalized_raw_data
    from src.bilun.cache.patient_slice import _build_diagnoses_by_pid
    from src.bilun.domain.loaders.validity import service_date_of
    from src.bilun.domain.optimization.copay_exemption_context import build_copay_inputs_by_patient

    dataset = load_showcase_dataset(DEFAULT_CLAIMS_DIR)
    clean = DEFAULT_CLAIMS_DIR.parent / "clean"
    ana_df, _, _ = load_normalized_raw_data(
        load_anadata_fn=lambda include_text=True: load_anadata(
            path=clean / "anadata_clean.parquet", include_text=include_text
        ),
        load_labdata_fn=pl.DataFrame,
        load_recete_fn=pl.DataFrame,
    )
    pids = sorted(dataset.claims_by_patient)
    inputs = build_copay_inputs_by_patient(
        pids,
        _build_diagnoses_by_pid(ana_df),
        claims_by_patient=dataset.claims_by_patient,
        copay_profiles_by_patient=dataset.copay_profiles_by_patient,
        procedure_lines_by_patient=dataset.procedure_lines_by_patient,
    )
    bills = 0
    for pid in pids:
        patient = evaluate_copay_exemption(inputs[pid])
        for claim in dataset.claims_by_patient[pid]:
            assert service_date_of(None, claim) >= date(2018, 2, 15), claim.claim_id
            assert bill_copay_exemption(pid, claim, {}, inputs) == patient, claim.claim_id
            bills += 1
    assert bills == sum(len(claims) for claims in dataset.claims_by_patient.values()) > 40
    # the demo's EK-1/A matches are read on the bill's date too: patient 5 (I10) is one of them
    assert any(
        _ek1a_codes(evaluate_copay_exemption(inputs[pid])["exemption_sources"]) for pid in pids
    )
