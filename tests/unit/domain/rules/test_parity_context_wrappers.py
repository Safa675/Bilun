"""Phase 2.1e parity tests — bundling/exclusion context wrappers.

Hard-gate test for the unified-claim-engine roadmap. Proves that
``check_bundling_violations_for_context(ctx)`` and
``check_exclusion_violations_for_context(ctx)`` produce violation sets
equivalent to the dict-based ``check_bundling_violations`` /
``check_exclusion_violations`` for the same logical materials.

Parity is structural (both paths call the same canonical matcher via the
build-time enricher), but this test verifies it empirically against fixtures
covering: EK-3B-1-positive, EK-3B-1-negative (pricing-bundle only),
EK-3B-2-positive, and clean materials.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from src.bilun.domain.claims.models import (
    ClaimHeader,
    ClaimDiagnosis,
    MaterialClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.rules.bundling_rules import (
    check_bundling_violations,
    check_bundling_violations_for_context,
)
from src.bilun.domain.rules.exclusion_rules import (
    check_exclusion_violations,
    check_exclusion_violations_for_context,
)

pytestmark = pytest.mark.unit


def _make_material_line(
    *,
    name: str,
    code: str = "",
    is_bundled: bool = False,
    is_ek3b1_bundled: bool = False,
    is_excluded: bool = False,
    billed: float = 10.0,
) -> MaterialClaimLine:
    """Build a minimal MaterialClaimLine for parity-test fixtures."""
    return MaterialClaimLine(
        material_line_id=f"ML-{name[:8]}",
        claim_id="C1",
        procedure_line_id="PL1",
        patient_id="P1",
        material_date="2026-01-01",
        material_code=code,
        material_name=name,
        material_type="consumable",
        specialty_category="general",
        quantity=1,
        unit_price_try=billed,
        billed_amount_try=billed,
        expected_payable_try=billed,
        is_bundled=is_bundled,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
        is_ek3b1_bundled=is_ek3b1_bundled,
        is_excluded=is_excluded,
    )


def _make_ctx(materials: list[MaterialClaimLine]) -> PatientClaimContext:
    """Build a minimal PatientClaimContext carrying just the material lines."""
    header = ClaimHeader(
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        claim_type="inpatient",
        facility_tier="state",
        provider_type="public",
        department="general",
        admission_date="2026-01-01",
        discharge_date="2026-01-02",
        claim_start_date="2026-01-01",
        claim_end_date="2026-01-02",
        primary_icd10="Z00.0",
        expected_total_billed_try=100.0,
        expected_total_payable_try=90.0,
        expected_denial_reason="",
        scenario_tag="parity_test",
    )
    return PatientClaimContext(
        patient_id="P1",
        claims=(header,),
        procedure_lines=(),
        material_lines=tuple(materials),
        drug_lines=(),
        diagnoses=(),
    )


def test_bundling_parity_dict_vs_context_for_ek3b1_positive() -> None:
    """A material on EK-3B-1 (e.g. 'Bistüri ucu') must be flagged by BOTH paths."""
    name = "Bistüri ucu"
    # Dict path
    dict_violations = check_bundling_violations(
        [{"name": name, "code": "", "unit_price": 10.0, "quantity": 1}]
    )
    assert len(dict_violations) == 1, "dict path must flag EK-3B-1 material"
    # Context path — simulate the build-time enricher having set is_ek3b1_bundled
    ctx = _make_ctx([_make_material_line(name=name, is_ek3b1_bundled=True)])
    ctx_violations = check_bundling_violations_for_context(ctx)
    assert len(ctx_violations) == 1, "context path must flag the enriched material"
    # Same severity + rule
    assert dict_violations[0]["rule"] == ctx_violations[0]["rule"] == "bundling"
    assert dict_violations[0]["severity"] == ctx_violations[0]["severity"] == "error"


def test_bundling_parity_dict_vs_context_for_clean_material() -> None:
    """A material NOT on EK-3B-1 must be unflagged by BOTH paths."""
    name = "Aspirin 500mg tablet"
    dict_violations = check_bundling_violations(
        [{"name": name, "code": "", "unit_price": 5.0, "quantity": 1}]
    )
    assert dict_violations == [], "dict path must not flag clean material"
    ctx = _make_ctx([_make_material_line(name=name, is_ek3b1_bundled=False)])
    ctx_violations = check_bundling_violations_for_context(ctx)
    assert ctx_violations == [], "context path must not flag clean material"


def test_bundling_context_path_ignores_pricing_bundle_only_flag() -> None:
    """A material with is_bundled=True (pricing bundle) but is_ek3b1_bundled=False
    must NOT be flagged by the context wrapper — the two concepts are distinct.

    This is the load-bearing assertion from the Phase 2.1c/d rescope: the CSV
    is_bundled flag is a broader pricing-bundle concept (prostheses, pumps);
    EK-3B-1 is a narrower regulatory consumable list. The wrapper reads only
    is_ek3b1_bundled, so a pricing-bundle-only material is correctly unflagged.
    """
    ctx = _make_ctx(
        [_make_material_line(name="EL BİLEĞİ (prosthesis)", is_bundled=True, is_ek3b1_bundled=False)]
    )
    ctx_violations = check_bundling_violations_for_context(ctx)
    assert ctx_violations == [], (
        "context wrapper must read is_ek3b1_bundled, not the broader is_bundled"
    )


def test_exclusion_parity_dict_vs_context_for_ek3b2_positive(monkeypatch) -> None:
    """A material on EK-3B-2 must be flagged by BOTH paths.

    Uses monkeypatching to inject a known exclusion entry so the test is
    deterministic regardless of the live EK-3B-2 annex contents. Patches both
    the canonical exclusions module (consumed by match_exclusion_entry /
    is_material_reimbursable) and the exclusion_rules module's bound import
    (consumed by check_exclusion_violations directly).
    """
    from src.bilun.domain.materials import exclusions as excl
    from src.bilun.domain.rules import exclusion_rules as er

    fake_exclusion = [{"sira_no": 1, "material_name": "Testos teron enjektör"}]
    monkeypatch.setattr(excl, "get_non_reimbursable_materials", lambda: fake_exclusion)
    monkeypatch.setattr(er, "get_non_reimbursable_materials", lambda: fake_exclusion)

    name = "Testos teron enjektör"
    # Dict path
    dict_violations = check_exclusion_violations([{"name": name, "code": "", "unit_price": 20.0, "quantity": 1}])
    assert len(dict_violations) == 1, "dict path must flag EK-3B-2 material"
    # Context path — enricher would have set is_excluded=True
    ctx = _make_ctx([_make_material_line(name=name, is_excluded=True, billed=20.0)])
    ctx_violations = check_exclusion_violations_for_context(ctx)
    assert len(ctx_violations) == 1, "context path must flag the enriched material"
    assert dict_violations[0]["rule"] == ctx_violations[0]["rule"] == "exclusion"


def test_exclusion_parity_dict_vs_context_for_clean_material() -> None:
    """A material NOT on EK-3B-2 must be unflagged by BOTH paths."""
    name = "Aspirin 500mg tablet"
    dict_violations = check_exclusion_violations(
        [{"name": name, "code": "", "unit_price": 5.0, "quantity": 1}]
    )
    assert dict_violations == []
    ctx = _make_ctx([_make_material_line(name=name, is_excluded=False)])
    ctx_violations = check_exclusion_violations_for_context(ctx)
    assert ctx_violations == []


def test_enricher_sets_is_ek3b1_bundled_for_known_annex_material() -> None:
    """The build-time enricher must set is_ek3b1_bundled=True for 'Bistüri ucu'."""
    from src.bilun.domain.claims.dataset_builder import _enrich_material_regulatory_flags

    line = _make_material_line(name="Bistüri ucu", code="")
    materials = {line.material_line_id: line}
    enriched = _enrich_material_regulatory_flags(materials)
    assert enriched[line.material_line_id].is_ek3b1_bundled is True, (
        "enricher must derive is_ek3b1_bundled=True for known EK-3B-1 material"
    )
    # is_bundled must be UNCHANGED (additive, not override)
    assert enriched[line.material_line_id].is_bundled == line.is_bundled


def test_enricher_preserves_csv_is_bundled_for_pricing_bundle_material() -> None:
    """The enricher must NOT touch is_bundled for pricing-bundle-only materials.

    A material with is_bundled=True (CSV pricing bundle) that is NOT on EK-3B-1
    must retain is_bundled=True after enrichment — the additive enricher only
    sets is_ek3b1_bundled / is_excluded, never overrides is_bundled.
    """
    from src.bilun.domain.claims.dataset_builder import _enrich_material_regulatory_flags

    line = _make_material_line(name="EL BİLEĞİ (prosthesis)", code="AP1260", is_bundled=True)
    materials = {line.material_line_id: line}
    enriched = _enrich_material_regulatory_flags(materials)
    out = enriched[line.material_line_id]
    assert out.is_bundled is True, "CSV is_bundled must be preserved (pricing-bundle concept)"
    assert out.is_ek3b1_bundled is False, "prosthesis is not on EK-3B-1"
