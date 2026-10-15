"""Phase 2 provenance tests: source_type + clause_ref on prose findings.

Non-canonical section ids are a provenance problem, not fake SUT clauses:
findings must carry an honest ``source_type`` and a ``clause_ref`` with an
EMPTY ``clause_key`` (these locators have no row in the SUT corpus) while
their existing ``sut_section_id`` values stay unchanged for consumers.

Covered motors:
- ``common_billing_errors``       (Tablo 15 — el_kitabi, 16 detectors)
- ``diagnosis_coding_quality``    (El Kitabı — el_kitabi, 3 detectors)
- ``lab_capture_gap``             (rehber)
- ``traffic_accident_billing``    (algoritma_rehberi + 2918 Sayılı Kanun)
- ``transplant_package_scope``    (rehber, structured locator)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.prose_rules import common_billing_errors as cbe
from src.bilun.domain.prose_rules import diagnosis_coding_quality as dxq
from src.bilun.domain.prose_rules.lab_capture_gap import detect_lab_capture_gaps
from src.bilun.domain.prose_rules.traffic_accident_billing import (
    detect_traffic_accident_copay,
    detect_traffic_accident_wrong_pathway,
)
from src.bilun.domain.prose_rules.transplant_package_scope import (
    detect_transplant_package_scope_violations,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Construction helpers (mirror test_common_billing_errors*.py patterns).
# ---------------------------------------------------------------------------


def _claim(
    *,
    claim_id: str = "C1",
    claim_type: str = "yatis",
    admission: date | None = date(2026, 7, 10),
    discharge: date | None = date(2026, 7, 13),
    claim_end: date | None = None,
    primary_icd10: str = "K35.8",
    scenario_tag: str = "test",
    occupational_context: str = "none",
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="genel",
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission or date.today(),
        claim_end_date=claim_end or discharge or date.today(),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag=scenario_tag,
        occupational_context=occupational_context,
    )


def _proc(
    *,
    procedure_line_id: str = "PL1",
    claim_id: str = "C1",
    procedure_code: str = "401010",
    procedure_name: str = "test procedure",
    procedure_category: str = "muayene",
    procedure_date: date = date(2026, 7, 10),
    procedure_specialty_code: str = "1000",
    is_package_included: bool = False,
    lab_billing_status: str = "",
    copay_rate_applicable: bool = False,
    surcharge_applicable: bool = False,
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=procedure_date,
        procedure_code=procedure_code,
        procedure_name=procedure_name,
        procedure_category=procedure_category,
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("1000"),
        is_package_included=is_package_included,
        package_code="",
        surcharge_applicable=surcharge_applicable,
        copay_rate_applicable=copay_rate_applicable,
        denial_reason_expected="",
        rule_trace_expected="",
        procedure_specialty_code=procedure_specialty_code,
        lab_billing_status=lab_billing_status,
    )


def _drug(
    *,
    drug_claim_line_id: str = "D1",
    claim_id: str = "C1",
    barkod: str = "8690000000001",
    quantity: int = 1,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id=drug_claim_line_id,
        prescription_id="RX1",
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 7, 10),
        drug_name="Parasetamol",
        drug_code="PARA1",
        barkod=barkod,
        equivalence_group="",
        quantity=quantity,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("72"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _material(
    *,
    material_line_id: str = "ML1",
    claim_id: str = "C1",
    material_type: str = "consumable",
    requires_pre_auth: bool = False,
    barcode_sut_mismatch: bool = False,
    titubb_uts_barcode_documentation_missing: bool = False,
) -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id=material_line_id,
        claim_id=claim_id,
        procedure_line_id="",
        patient_id="P1",
        material_date=date(2026, 7, 10),
        material_code="500000",
        material_name="test material",
        material_type=material_type,
        specialty_category="general",
        quantity=1,
        unit_price_try=Decimal("500"),
        billed_amount_try=Decimal("500"),
        expected_payable_try=Decimal("500"),
        is_bundled=False,
        requires_pre_auth=requires_pre_auth,
        denial_reason_expected="",
        rule_trace_expected="",
        barcode_sut_mismatch=barcode_sut_mismatch,
        titubb_uts_barcode_documentation_missing=titubb_uts_barcode_documentation_missing,
    )


def _diagnosis(*, diagnosis_id: str = "DX1", claim_id: str = "C1", icd10: str) -> ClaimDiagnosis:
    return ClaimDiagnosis(
        diagnosis_id=diagnosis_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        icd10_code=icd10,
        is_primary=False,
        diagnosis_role="ek",
        diagnosis_date=date(2026, 1, 1),
        exemption_eligible=False,
    )


def _assert_non_sut_provenance(
    finding: dict,
    *,
    source_type: str,
    locator: str,
    sut_section_id: str,
    statutory_law: str = "",
) -> None:
    """The Phase 2 provenance contract for one finding dict."""
    assert finding["sut_section_id"] == sut_section_id
    assert finding["source_type"] == source_type
    clause_ref = finding["clause_ref"]
    assert clause_ref["source_type"] == source_type
    assert clause_ref["clause_key"] == ""  # honest: no SUT-corpus row
    assert clause_ref["clause_coordinate"] == locator
    assert clause_ref["statutory_law"] == statutory_law


# ===========================================================================
# Tablo 15 (common_billing_errors) — every one of the 16 detectors
# ===========================================================================


def _all_tablo15_findings() -> list[dict]:
    """One triggering finding from each of the 16 Tablo 15 detectors."""
    outpatient_a = _claim(claim_id="C1", claim_type="poliklinik", admission=None, discharge=None)
    outpatient_b = _claim(claim_id="C2", claim_type="poliklinik", admission=None, discharge=None)
    inpatient = _claim(claim_id="C3")
    findings: list[dict] = []
    findings += cbe.detect_duplicate_exam_10day(
        [outpatient_a, outpatient_b],
        [
            _proc(claim_id="C1", procedure_line_id="PL1", procedure_date=date(2026, 7, 1)),
            _proc(claim_id="C2", procedure_line_id="PL2", procedure_date=date(2026, 7, 6)),
        ],
    )
    findings += cbe.detect_missing_diagnosis([_claim(primary_icd10="")])
    findings += cbe.detect_duplicate_tests(
        [],
        [
            _proc(
                claim_id="C1",
                procedure_line_id="PL1",
                procedure_code="L112180",
                procedure_category="laboratuvar",
                procedure_date=date(2026, 7, 1),
            ),
            _proc(
                claim_id="C2",
                procedure_line_id="PL2",
                procedure_code="L112180",
                procedure_category="laboratuvar",
                procedure_date=date(2026, 7, 4),
            ),
        ],
    )
    findings += cbe.detect_missing_drug_barcode([], [_drug(barkod="")])
    findings += cbe.detect_vakabasi_wrong_method(
        [outpatient_a],
        [_proc(claim_id="C1", is_package_included=True)],
    )
    # #260: #4 no longer fires on a correct package line; §2.2 payment-method compliance owns it.
    assert cbe.detect_normal_poliklinik_wrong_method(
        [inpatient],
        [_proc(claim_id="C3", procedure_category="paket", is_package_included=False)],
    ) == []
    findings += cbe.detect_material_identity_errors(
        [], [_material(barcode_sut_mismatch=True)]
    )
    findings += cbe.detect_green_area_bundled_extras(
        [],
        [
            _proc(claim_id="C1", procedure_line_id="PL-GA", procedure_code="520021"),
            _proc(claim_id="C1", procedure_line_id="PL-X", procedure_code="401010"),
        ],
    )
    findings += cbe.detect_unreported_lab_result(
        [], [_proc(lab_billing_status="pending", procedure_category="laboratuvar")]
    )
    findings += cbe.detect_drug_quantity_error([], [_drug(quantity=0)])
    findings += cbe.detect_material_preauth_missing([], [_material(requires_pre_auth=True)])
    findings += cbe.detect_material_type_missing([], [_material(material_type="")])
    findings += cbe.detect_inpatient_on_outpatient(
        [outpatient_a],
        [_proc(claim_id="C1", procedure_category="ameliyat")],
    )
    findings += cbe.detect_donor_prep_as_exam(
        [_claim(claim_type="poliklinik", admission=None, discharge=None, occupational_context="donor_prep")],
        [_proc()],
    )
    return findings


def test_all_13_active_tablo15_detectors_carry_el_kitabi_provenance() -> None:
    findings = _all_tablo15_findings()
    assert len(findings) == 13  # #260: #4 emits nothing (was 14)
    rule_ids = {f["rule_id"] for f in findings}
    assert len(rule_ids) == 13  # one distinct rule id per active detector
    for finding in findings:
        _assert_non_sut_provenance(
            finding,
            source_type="el_kitabi",
            locator="El Kitabı Tablo 15",
            sut_section_id="tablo_15",
        )


def test_tablo15_clause_ref_is_shared_module_level_dict() -> None:
    # Resolved once at module load — not rebuilt per finding.
    finding = cbe.detect_missing_diagnosis([_claim(primary_icd10="")])[0]
    assert finding["clause_ref"] is cbe._CLAUSE_REF
    assert finding["source_type"] == cbe._SOURCE_TYPE == "el_kitabi"


# ===========================================================================
# Diagnosis-coding quality (El Kitabı)
# ===========================================================================


def test_diagnosis_quality_findings_carry_el_kitabi_provenance() -> None:
    findings = dxq.detect_never_principal_diagnosis([_claim(primary_icd10="R69")])
    findings += dxq.detect_diagnosis_procedure_mismatch(
        [_claim(primary_icd10="F20.0")],
        [_proc(procedure_code="601010", procedure_category="cerrahi")],
    )
    findings += dxq.detect_unnecessary_additional_diagnosis(
        [_claim(primary_icd10="K35.8")],
        [_diagnosis(diagnosis_id="DX-R", icd10="R10.4"), _diagnosis(diagnosis_id="DX-K", icd10="K35.8")],
    )
    assert len(findings) == 3
    for finding in findings:
        _assert_non_sut_provenance(
            finding,
            source_type="el_kitabi",
            locator="El Kitabı — Tanı Kodlama Kalitesi",
            sut_section_id="elkitabi_diagnosis_coding",
        )


# ===========================================================================
# Lab capture gap (rehber)
# ===========================================================================


def test_lab_capture_gap_finding_carry_rehber_provenance() -> None:
    lab_df = pl.DataFrame(
        [{"patient_id": "P1", "visit_id": "V1", "test_name": "l112180"}],
        schema={"patient_id": pl.Utf8, "visit_id": pl.Utf8, "test_name": pl.Utf8},
    )
    gaps = detect_lab_capture_gaps(lab_df, [], "V1", service_date="2024-01-01")
    assert len(gaps) == 1
    finding = gaps[0]
    # Compat id string unchanged.
    _assert_non_sut_provenance(
        finding,
        source_type="rehber",
        locator="Lab capture completeness review",
        sut_section_id="clinical lab capture completeness",
    )
    assert finding["rule_id"] == "lab_performed_not_submitted"


# ===========================================================================
# Traffic accident billing (algoritma_rehberi + 2918 Sayılı Kanun)
# ===========================================================================


def test_traffic_wrong_pathway_finding_carries_algoritma_provenance() -> None:
    # Traffic detected only via V-code diagnosis → wrong-pathway finding.
    claim = _claim(primary_icd10="V89.9")
    findings = detect_traffic_accident_wrong_pathway([claim])
    assert len(findings) == 1
    _assert_non_sut_provenance(
        findings[0],
        source_type="algoritma_rehberi",
        locator="Algoritma Rehberi §2-09",
        sut_section_id="algoritma_2_09",
        statutory_law="2918 Sayılı Kanun Madde 98",
    )


def test_traffic_copay_finding_carries_algoritma_provenance() -> None:
    claim = _claim(scenario_tag="trafik_kazasi", occupational_context="traffic_accident")
    line = _proc(copay_rate_applicable=True)
    findings = detect_traffic_accident_copay([claim], [line])
    assert len(findings) == 1
    _assert_non_sut_provenance(
        findings[0],
        source_type="algoritma_rehberi",
        locator="Algoritma Rehberi §2-09",
        sut_section_id="algoritma_2_09",
        statutory_law="2918 Sayılı Kanun Madde 98",
    )


# ===========================================================================
# Transplant package scope (rehber, structured locator)
# ===========================================================================


def test_transplant_finding_uses_structured_locator_and_rehber_provenance() -> None:
    claim = _claim(claim_id="CLM1")
    lines = [
        _proc(
            procedure_line_id="PL-PKG",
            claim_id="CLM1",
            procedure_code="609080",
            procedure_name="Karaciğer Transplantasyonu",
            procedure_category="paket",
        ),
        _proc(
            procedure_line_id="PL-SURG",
            claim_id="CLM1",
            procedure_code="510030",
            procedure_name="Karaciğer rezeksiyonu",
            procedure_category="islem",
        ),
    ]
    findings = detect_transplant_package_scope_violations(claim, lines)
    assert len(findings) == 1
    finding = findings[0]
    # No invent a SUT cite: structured locator + rehber provenance, empty key.
    _assert_non_sut_provenance(
        finding,
        source_type="rehber",
        locator="P609080 package scope",
        sut_section_id="p609080_package_scope",
    )
    # Existing behavior keys unchanged.
    assert finding["rule_id"] == "transplant_bundled_surgical_procedure"
    assert finding["savings_basis"] == "heuristic"
