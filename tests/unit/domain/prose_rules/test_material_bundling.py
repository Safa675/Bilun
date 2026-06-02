"""L1.4 partial material bundling prose."""

from __future__ import annotations

import pytest

from src.bilun.domain.materials.catalog_lookup import (
    ek3c_material_code_set,
    is_material_in_ek3c_catalog,
)
from src.bilun.domain.materials.coverage_scope import prose_engine_status
from src.bilun.domain.prose_rules.material_bundling import (
    check_material_bundling_for_context,
    check_material_bundling_prose,
)

pytestmark = pytest.mark.unit


def test_prose_engine_status_implemented_when_json_present() -> None:
    assert prose_engine_status() == "implemented"


def test_keyword_rule_demirbas() -> None:
    hits = check_material_bundling_prose(
        [{"name": "Hastane demirbaş yedek parça", "unit_price": 50.0}]
    )
    assert len(hits) == 1
    assert hits[0]["rule_id"] == "3.1.3.(8).demirbas"


def test_not_in_ek3c_when_code_unknown() -> None:
    hits = check_material_bundling_prose(
        [{"name": "Protez", "code": "NOT-IN-EK3C-99999", "unit_price": 100.0}]
    )
    assert len(hits) == 1
    assert hits[0]["rule_id"] == "3.1.2.(2).not_in_ek3c"


def test_missing_material_code() -> None:
    hits = check_material_bundling_prose(
        [{"name": "Kodsuz malzeme", "unit_price": 10.0}]
    )
    assert len(hits) == 1
    assert hits[0]["rule_id"] == "3.1.1.(11).missing_material_code"


def test_procedure_pairing_when_ek3c_code_unlinked() -> None:
    known = next(iter(ek3c_material_code_set()))
    assert is_material_in_ek3c_catalog(known)
    hits = check_material_bundling_prose(
        [{"name": "Listed material", "code": known, "unit_price": 50.0}],
        procedure_codes_on_claim=frozenset(),
        billed_procedure_line_ids=frozenset(),
    )
    assert len(hits) == 1
    assert hits[0]["rule_id"] == "3.1.1.(11).procedure_pairing"


def test_procedure_pairing_ok_via_line_id() -> None:
    known = next(iter(ek3c_material_code_set()))
    hits = check_material_bundling_prose(
        [
            {
                "name": "Listed material",
                "code": known,
                "unit_price": 50.0,
                "procedure_line_id": "proc-1",
            }
        ],
        procedure_codes_on_claim=frozenset(),
        billed_procedure_line_ids=frozenset({"proc-1"}),
    )
    assert hits == []


def test_procedure_pairing_ok_via_claim_procedure_code() -> None:
    known = next(iter(ek3c_material_code_set()))
    hits = check_material_bundling_prose(
        [{"name": "Listed material", "code": known, "unit_price": 50.0}],
        procedure_code="L100010",
        procedure_codes_on_claim=frozenset({"L100010"}),
    )
    assert hits == []


def test_validate_claim_prose_integration() -> None:
    from src.bilun.domain.rule_engine import validate_claim

    result = validate_claim(
        {
            "claim_id": "T",
            "materials": [
                {
                    "name": "Tekrar kullanılabilir set",
                    "unit_price": 25.0,
                    "quantity": 1,
                }
            ],
        }
    )
    prose = [v for v in result.violations if v.rule == "material_bundling_prose"]
    assert len(prose) == 1
    assert result.coverage_scope["prose_engine_status"] == "implemented"
    assert result.coverage_scope["prose_coverage_tier"] == "partial"


def test_titubb_uts_incomplete_when_flags_false() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Protez",
                "code": "999999",
                "unit_price": 100.0,
                "titubb_registered": False,
                "uts_registered": True,
            }
        ],
    )
    assert any(h["rule_id"] == "3.1.1.(2).titubb_uts_incomplete" for h in hits)


def test_material_not_in_ek3c_when_code_unknown() -> None:
    hits = check_material_bundling_prose(
        [{"name": "X", "code": "NOT-IN-ANY-EK3-99999", "unit_price": 50.0}],
    )
    assert hits[0]["rule_id"] == "3.1.2.(2).not_in_ek3c"


def test_lost_stolen_keyword() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Malzeme kaybolması nedeniyle yenileme",
                "code": "LOST1",
                "unit_price": 10.0,
            }
        ],
    )
    assert any(h["rule_id"] == "3.1.2.(7).lost_stolen_miat" for h in hits)


def test_procurement_record_incomplete() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Malzeme",
                "code": "P1",
                "unit_price": 50.0,
                "procurement_record_incomplete": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.1.(5).procurement_screen_incomplete"


def test_foreign_facility_flag() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Malzeme",
                "code": "AB1",
                "unit_price": 40.0,
                "foreign_facility": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.1.(14).foreign_facility_overhead"


def test_warranty_maintenance_c002741_keyword() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Bakım ve onarım masrafları garanti süresi içinde",
                "code": "W1",
                "unit_price": 35.0,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.2.c.warranty_maintenance"


def test_claim_precheck_surfaces_prose_violations() -> None:
    from datetime import date
    from decimal import Decimal

    from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims
    from src.bilun.domain.claims.models import MaterialClaimLine
    from src.bilun.domain.claims.patient_context import PatientClaimContext

    known = "1"
    assert is_material_in_ek3c_catalog(known)
    line = MaterialClaimLine(
        material_line_id="M1",
        claim_id="C1",
        procedure_line_id="",
        patient_id="PT1",
        material_date=date(2024, 6, 1),
        material_code=known,
        material_name="Test mat",
        material_type="consumable",
        specialty_category="general",
        quantity=1,
        unit_price_try=Decimal("40"),
        billed_amount_try=Decimal("40"),
        expected_payable_try=Decimal("40"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    ctx = PatientClaimContext(
        patient_id="PT1",
        claims=(),
        procedure_lines=(),
        material_lines=(line,),
        drug_lines=(),
        diagnoses=(),
    )
    result = precheck_materials_from_claims(ctx)
    assert len(result.prose_bundling_violations) == 1
    assert result.prose_bundling_violations[0]["rule_id"] == "3.1.1.(11).procedure_pairing"
