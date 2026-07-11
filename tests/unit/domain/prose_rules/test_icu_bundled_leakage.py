"""Unit tests for ICU bundled-service leakage detector (SUT §2.4.4.H).

The El Kitabı + SUT §2.4.4.H bundle ventilation, oxygen therapy,
nebulization, deep tracheal suction, and patient monitoring into the 510090
ICU day-rate (hizmet başı). This detector flags any such service billed
separately on a claim that also carries a 510090 line.

Covers:
  - 510090 + ventilation code on same claim → violation
  - 510090 + oxygen code on same claim → violation
  - 510090 + nebulizer on same claim → violation
  - 510090 + deep tracheal suction → violation
  - 510090 + monitoring → violation
  - 510090 alone → no violation
  - 510090 + non-bundled procedure (e.g. blood test) → no violation
  - non-ICU claim → no violation
  - outpatient claim → no violation
  - keyword fallback for a variant code → violation
  - 510090 + ICU intermediate package (P55200x) → no violation (different rule)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


def _make_claim_header(
    *,
    claim_id: str = "C1",
    claim_type: str = "yatis",
    admission: date | None = date(2026, 7, 10),
    discharge: date | None = date(2026, 7, 13),
    facility_tier: str = "3_basamak",
):
    from src.bilun.domain.claims.models import ClaimHeader

    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier=facility_tier,
        provider_type="sozlesmeli",
        department="Yogun Bakim",
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission or date.today(),
        claim_end_date=discharge or date.today(),
        primary_icd10="J96.0",
        package_candidate=False,
        expected_total_billed_try=Decimal("10000"),
        expected_total_payable_try=Decimal("9000"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_proc_line(
    *,
    procedure_line_id: str = "ISL-1",
    claim_id: str = "C1",
    procedure_code: str = "510090",
    procedure_name: str = "Yogun bakim",
):
    from src.bilun.domain.claims.models import ProcedureClaimLine

    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 7, 10),
        procedure_code=procedure_code,
        procedure_name=procedure_name,
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("742.60"),
        billed_amount_try=Decimal("742.60"),
        expected_payable_try=Decimal("700.00"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


# ── Positive cases (violations emitted) ──────────────────────────────────────


def test_510090_plus_mechanical_ventilation_violation() -> None:
    """510090 + 530130 (mekanik ventilatöre bağlanma) on same claim → violation."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [
        _make_proc_line(),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="530130",
            procedure_name="Hastanın mekanik ventilatöre bağlanması",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})

    assert len(violations) == 1
    v = violations[0]
    assert v["type"] == "icu_bundled_service_leakage"
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "icu_bundled_leakage_510090"
    assert v["procedure_code"] == "530130"
    assert v["sut_section_id"] == "2.4.4.H"
    assert v["savings_category"] == "audit_exposure"
    assert v["savings_basis"] == "sourced"
    assert v["severity"] == "error"
    assert "510090" in v["detail"]
    assert v["bundled_category"] == "Mekanik ventilasyon"


def test_510090_plus_oxygen_therapy_violation() -> None:
    """510090 + 530360 (oksijen inhalasyon tedavisi) on same claim → violation."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [
        _make_proc_line(),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="530360",
            procedure_name="Oksijen inhalasyon tedavisi, saatlik",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})

    assert len(violations) == 1
    v = violations[0]
    assert v["procedure_code"] == "530360"
    assert v["bundled_category"] == "Oksijen tedavisi"


def test_510090_plus_nebulizer_violation() -> None:
    """510090 + 530350 (nebulizatör ile ilaç uygulaması) on same claim → violation."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [
        _make_proc_line(),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="530350",
            procedure_name="Nebülizatör ile ilaç uygulaması",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})

    assert len(violations) == 1
    v = violations[0]
    assert v["procedure_code"] == "530350"
    assert v["bundled_category"] == "Nebülizasyon"


def test_510090_plus_deep_tracheal_suction_violation() -> None:
    """510090 + 551251 (derin trakeal aspirasyon) on same claim → violation."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [
        _make_proc_line(),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="551251",
            procedure_name="Derin trakeal aspirasyon",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})

    assert len(violations) == 1
    v = violations[0]
    assert v["procedure_code"] == "551251"
    assert v["bundled_category"] == "Derin trakeal aspirasyon"


def test_510090_plus_monitoring_violation() -> None:
    """510090 + 530330 (monitörizasyon) on same claim → violation."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [
        _make_proc_line(),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="530330",
            procedure_name="Monitörizasyon",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})

    assert len(violations) == 1
    v = violations[0]
    assert v["procedure_code"] == "530330"
    assert v["bundled_category"] == "Hasta monitorizasyonu"


def test_510090_plus_multiple_bundled_services_multiple_violations() -> None:
    """510090 + ventilation + oxygen + monitoring → one violation per service."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [
        _make_proc_line(),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="530130",
            procedure_name="Hastanın mekanik ventilatöre bağlanması",
        ),
        _make_proc_line(
            procedure_line_id="ISL-3",
            procedure_code="530360",
            procedure_name="Oksijen inhalasyon tedavisi, saatlik",
        ),
        _make_proc_line(
            procedure_line_id="ISL-4",
            procedure_code="530330",
            procedure_name="Monitörizasyon",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})

    assert len(violations) == 3
    codes = {v["procedure_code"] for v in violations}
    assert codes == {"530130", "530360", "530330"}


def test_keyword_fallback_catches_variant_code() -> None:
    """A variant code naming 'nebulizatör' (not in exact set) still flagged."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [
        _make_proc_line(),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="999999",  # not a real bundled code
            procedure_name="Nebülizatör ilaç tedavisi (variant)",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})

    assert len(violations) == 1
    v = violations[0]
    assert v["procedure_code"] == "999999"
    assert v["bundled_category"] == "Nebülizasyon"


# ── Negative cases (no violations) ───────────────────────────────────────────


def test_510090_alone_no_violation() -> None:
    """510090 with no bundled services → no violation."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [_make_proc_line()]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})
    assert violations == []


def test_510090_plus_non_bundled_procedure_no_violation() -> None:
    """510090 + an unrelated procedure (e.g. blood test) → no violation."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [
        _make_proc_line(),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="090101",
            procedure_name="Tam kan sayımı (hemogram)",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})
    assert violations == []


def test_510090_plus_icu_intermediate_package_no_violation() -> None:
    """510090 + P552003 ICU intermediate package → no violation (different rule).

    The P552001-008 EK-2C packages are a separate bundled-service regime
    audited by icu_puani; flagging them here would conflate two rules.
    """
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [
        _make_proc_line(),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="P552003",
            procedure_name="Üçüncü basamak yoğun bakım (ara günü)",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})
    assert violations == []


def test_non_icu_claim_no_violation() -> None:
    """Inpatient claim with no 510090 line → no violation (no ICU day)."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [
        _make_proc_line(
            procedure_line_id="ISL-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
        ),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="530330",
            procedure_name="Monitörizasyon",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})
    assert violations == []


def test_outpatient_claim_no_violation() -> None:
    """Outpatient claim carrying 510090-style data → skipped (inpatient-only)."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header(claim_type="ayakta")
    procs = [
        _make_proc_line(),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="530360",
            procedure_name="Oksijen inhalasyon tedavisi, saatlik",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})
    assert violations == []


def test_no_procedure_lines_no_violation() -> None:
    """No procedure lines at all → cannot confirm 510090 day → skip."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    assert detect_icu_bundled_leakage([header], None) == []
    assert detect_icu_bundled_leakage([header], []) == []


def test_claim_not_in_filter_no_violation() -> None:
    """Claim not in claim_ids_with_procs filter → skipped."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [
        _make_proc_line(),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="530360",
            procedure_name="Oksijen inhalasyon tedavisi, saatlik",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"OTHER"})
    assert violations == []


def test_p_prefixed_510090_detected() -> None:
    """A P-prefixed 510090 (MEDULA convention) still triggers the rule."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header = _make_claim_header()
    procs = [
        _make_proc_line(procedure_code="P510090"),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="530330",
            procedure_name="Monitörizasyon",
        ),
    ]
    violations = detect_icu_bundled_leakage([header], procs, claim_ids_with_procs={"C1"})
    assert len(violations) == 1
    assert violations[0]["procedure_code"] == "530330"


def test_multiple_claims_isolated() -> None:
    """Bundled service on claim-2 without 510090 there → no violation for claim-2."""
    from src.bilun.domain.prose_rules.icu_bundled_leakage import (
        detect_icu_bundled_leakage,
    )

    header_icu = _make_claim_header(claim_id="ICU")
    header_plain = _make_claim_header(
        claim_id="PLAIN", claim_type="yatis"
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1"),
        _make_proc_line(
            claim_id="ICU",
            procedure_line_id="ICU-2",
            procedure_code="530330",
            procedure_name="Monitörizasyon",
        ),
        # PLAIN claim has a bundled service but NO 510090 day.
        _make_proc_line(
            claim_id="PLAIN",
            procedure_line_id="PLAIN-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
        ),
        _make_proc_line(
            claim_id="PLAIN",
            procedure_line_id="PLAIN-2",
            procedure_code="530330",
            procedure_name="Monitörizasyon",
        ),
    ]
    violations = detect_icu_bundled_leakage(
        [header_icu, header_plain], procs, claim_ids_with_procs={"ICU", "PLAIN"}
    )
    assert len(violations) == 1
    assert violations[0]["claim_id"] == "ICU"
