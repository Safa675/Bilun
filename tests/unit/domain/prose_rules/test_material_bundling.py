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


def test_separate_billing_not_authorized_for_unlisted_ek3_code() -> None:
    from src.bilun.domain.materials.catalog_lookup import (
        ek3_all_material_code_set,
        ek3c_material_code_set,
        is_separate_billing_allowed,
    )

    code = next(
        c
        for c in sorted(ek3_all_material_code_set() - ek3c_material_code_set())
        if not is_separate_billing_allowed(c)
    )
    hits = check_material_bundling_prose(
        [
            {
                "name": "Listed material",
                "code": code,
                "unit_price": 50.0,
                "is_bundled": False,
            }
        ]
    )
    assert len(hits) == 1
    assert hits[0]["rule_id"] == "3.1.1.(15).separate_billing_not_authorized"


def test_separate_billing_allowed_code_skips_unauthorized_rule() -> None:
    from src.bilun.domain.materials.catalog_lookup import ek3_separate_billing_allowed_codes

    allowed = next(iter(ek3_separate_billing_allowed_codes()))
    hits = check_material_bundling_prose(
        [
            {
                "name": "Allowed separate",
                "code": allowed,
                "unit_price": 50.0,
                "is_bundled": False,
            }
        ]
    )
    assert not any(
        hit["rule_id"] == "3.1.1.(15).separate_billing_not_authorized" for hit in hits
    )


def test_procurement_price_refs_insufficient_flag() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Listesiz malzeme",
                "code": "PRICE1",
                "unit_price": 50.0,
                "procurement_price_refs_insufficient": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.2.1.(2).procurement_price_refs_insufficient"


def test_medula_code_undefined_on_date_flag() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Malzeme",
                "code": "MED1",
                "unit_price": 50.0,
                "medula_code_undefined_on_date": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.1.(16).medula_code_undefined_on_date"


def test_barcode_sut_mismatch_flag() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Normal malzeme adı",
                "code": "BC1",
                "unit_price": 50.0,
                "barcode_sut_mismatch": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.1.(17).barcode_sut_mismatch"


def test_medula_undefined_not_titubb_rule_when_only_date_flag() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Malzeme",
                "code": "MED2",
                "unit_price": 50.0,
                "medula_code_undefined_on_date": True,
                "titubb_registered": True,
                "uts_registered": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.1.(16).medula_code_undefined_on_date"
    assert not any(h["rule_id"] == "3.1.1.(2).titubb_uts_incomplete" for h in hits)


def test_diagnosis_bundled_material_scope_advisory() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Paket malzeme",
                "code": "PK1",
                "unit_price": 50.0,
                "diagnosis_bundled_material_scope": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.4.(1).diagnosis_bundled_sut_rules_apply"
    assert hits[0]["severity"] == "info"


def test_cross_branch_material_unauthorized() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Cross branch",
                "code": "CB1",
                "unit_price": 50.0,
                "cross_branch_material_unauthorized": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.3.(4).cross_branch_billing_unauthorized"


def test_ortez_protez_contract_billing_invalid() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Ortez",
                "code": "OP1",
                "unit_price": 50.0,
                "ortez_protez_contract_billing_invalid": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.2.b.ortez_protez_contract_billing_invalid"


def test_maintenance_cost_cap_exceeded() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "MIAT malzeme bakım",
                "code": "M1",
                "unit_price": 100.0,
                "maintenance_cost_exceeds_sut_cap": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.2.(11).maintenance_cost_cap_exceeded"


def test_protez_repair_documentation_incomplete() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Protez parça",
                "code": "P1",
                "unit_price": 80.0,
                "protez_repair_documentation_incomplete": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.2.(8).protez_repair_documentation_incomplete"


def test_warranty_maintenance_procedure_incomplete() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Cihaz",
                "code": "D1",
                "unit_price": 60.0,
                "warranty_maintenance_procedure_incomplete": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.2.(8).warranty_maintenance_procedure_incomplete"


def test_ihale_dts_mandatory_fields_incomplete() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Malzeme",
                "code": "I1",
                "unit_price": 50.0,
                "ihale_dts_mandatory_fields_incomplete": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.1.(4).ihale_dts_mandatory_fields_incomplete"


def test_supplier_contract_pricing_path_advisory() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Sözleşmeli malzeme",
                "code": "S1",
                "unit_price": 70.0,
                "supplier_contract_pricing_path": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.2.1.A.(3).supplier_contract_pricing_path"
    assert hits[0]["severity"] == "info"


def test_ihale_dts_distinct_from_procurement_screen_incomplete() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Malzeme",
                "code": "I2",
                "unit_price": 50.0,
                "ihale_dts_mandatory_fields_incomplete": True,
                "procurement_record_incomplete": False,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.1.(4).ihale_dts_mandatory_fields_incomplete"


def test_ek3c_inpatient_external_supply_invalid() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "EK-3/C malzeme",
                "code": "E1",
                "unit_price": 50.0,
                "ek3c_inpatient_external_supply_invalid": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.1.(8).ek3c_inpatient_external_supply_invalid"


def test_ek3c_list_price_missing_review() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Fiyatsız EK-3/C",
                "code": "E2",
                "unit_price": 40.0,
                "ek3c_list_price_missing": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.2.2.(2).ek3c_list_price_missing"


def test_ek3c_medical_appropriateness_incomplete() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "C-1 malzeme",
                "code": "E3",
                "unit_price": 30.0,
                "ek3c_medical_appropriateness_incomplete": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.2.(5).ek3c_medical_appropriateness_incomplete"


def test_ek3c_miat_early_renewal_unauthorized() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "MIAT malzeme",
                "code": "E4",
                "unit_price": 20.0,
                "ek3c_miat_early_renewal_unauthorized": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.2.(9).ek3c_miat_early_renewal_unauthorized"


def test_inpatient_facility_supply_violation() -> None:
    hits = check_material_bundling_prose(
        [{"name": "M", "code": "Y1", "unit_price": 50.0, "inpatient_material_facility_supply_violation": True}]
    )
    assert hits[0]["rule_id"] == "3.1.1.(6).inpatient_facility_supply_violation"


def test_lab_material_separate_billing() -> None:
    hits = check_material_bundling_prose(
        [{"name": "Lab sarf", "code": "L1", "unit_price": 10.0, "lab_material_separate_billing": True}]
    )
    assert hits[0]["rule_id"] == "3.1.3.(10).lab_material_separate_billing"
    assert hits[0]["material_outcome"] == "must_not_bill_separately"


def test_material_report_prescription_invalid() -> None:
    hits = check_material_bundling_prose(
        [{"name": "M", "code": "R1", "unit_price": 30.0, "material_report_prescription_invalid": True}]
    )
    assert hits[0]["rule_id"] == "3.1.2.report_prescription_invalid"


def test_ismarlama_device_component_titubb_incomplete() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Ismarlama bileşen",
                "code": "ISM1",
                "unit_price": 100.0,
                "ismarlama_device_component_titubb_incomplete": True,
                "titubb_registered": True,
                "uts_registered": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.1.(3).ismarlama_device_component_titubb_incomplete"
    assert hits[0]["material_outcome"] == "no_pay"
    assert not any(h["rule_id"] == "3.1.1.(2).titubb_uts_incomplete" for h in hits)


def test_titubb_uts_barcode_documentation_missing() -> None:
    hits = check_material_bundling_prose(
        [
            {
                "name": "Malzeme",
                "code": "BR1",
                "unit_price": 150.0,
                "titubb_uts_barcode_documentation_missing": True,
            }
        ],
    )
    assert hits[0]["rule_id"] == "3.1.1.(4).titubb_uts_barcode_documentation_missing"
    assert hits[0]["material_outcome"] == "review_required"
    assert hits[0]["severity"] == "warning"
