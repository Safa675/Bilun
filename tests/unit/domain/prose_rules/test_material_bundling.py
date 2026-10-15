"""L1.4 partial material bundling prose."""

from __future__ import annotations

import pytest

from src.bilun.domain.materials.catalog_lookup import (
    ek3c_material_code_set,
    is_material_in_ek3c_catalog,
)
from src.bilun.domain.materials.coverage_scope import prose_engine_status
from src.bilun.domain.prose_rules.material_bundling import (
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


def _assert_cites_in_force_3_1_1_13(hit: dict) -> None:
    # In-force §3.1.1(11) is the quality-document clause; the material/procedure
    # billing text it once held now lives only in superseded copies. The in-force
    # anchor is §3.1.1(13) (EK-3 codes billed in addition to procedure codes).
    assert "(§3.1.1(13))" in hit["message"]
    assert "§3.1.1(11)" not in hit["message"]
    assert hit["clause_ref"]["clause_coordinate"] == "3.1.1.(13)"
    assert hit["clause_ref"]["clause_key"].startswith("3.1.1.(13)#")


def test_missing_material_code() -> None:
    hits = check_material_bundling_prose(
        [{"name": "Kodsuz malzeme", "unit_price": 10.0}]
    )
    assert len(hits) == 1
    assert hits[0]["rule_id"] == "3.1.1.(11).missing_material_code"
    _assert_cites_in_force_3_1_1_13(hits[0])


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
    _assert_cites_in_force_3_1_1_13(hits[0])


def test_procedure_not_reimbursed_link_cites_in_force_3_1_1_9() -> None:
    # In-force §3.1.1(9) (C002747) is the clause that withholds payment for
    # materials of procedures whose price the Kurum does not cover. In-force
    # §3.1.1(11) is the quality-document clause and (12) the foreign-facility
    # overhead clause; the rule id keeps its historical (11) label.
    hits = check_material_bundling_prose(
        [
            {
                "name": "Islem malzemesi",
                "code": "PR1",
                "unit_price": 60.0,
                "procedure_not_reimbursed": True,
            }
        ]
    )
    assert len(hits) == 1
    hit = hits[0]
    assert hit["rule_id"] == "3.1.1.(11).procedure_not_reimbursed_link"
    assert hit["material_outcome"] == "no_pay"
    assert "(§3.1.1(9))" in hit["message"]
    assert "§3.1.1(11)" not in hit["message"]
    assert "(12)" not in hit["message"]
    assert hit["clause_ref"]["clause_coordinate"] == "3.1.1.(9)"
    assert hit["clause_ref"]["clause_key"].startswith("3.1.1.(9)#")


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
        is_covered_by_sut_3_1_4_category,
        is_separate_billing_allowed,
    )

    code = next(
        c
        for c in sorted(ek3_all_material_code_set() - ek3c_material_code_set())
        if not is_separate_billing_allowed(c)
        # #262: a §3.1.4(2) category is SUT permission too.
        and not is_covered_by_sut_3_1_4_category(c)
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
    # rule_id keeps its legacy (17) label for stability; in force the
    # barcode-SUT mismatch text is §3.1.1(15) (C002753).
    assert "(§3.1.1(15))" in hits[0]["message"]
    assert "§3.1.1(17)" not in hits[0]["message"]
    assert hits[0]["clause_ref"]["clause_coordinate"] == "3.1.1.(15)"
    assert hits[0]["clause_ref"]["clause_key"].startswith("3.1.1.(15)#")


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


# ── Inpatient-scope care-setting gate (false-positive guard) ─────────────────
# The §3.1.1(6) "Karşılanmayan yatarak malzeme" rule (rule id keeps its
# historical (7) label) asserts an inpatient context. It must NOT fire on an
# outpatient (poliklinik) claim — that is a false compliance violation an
# auditor can falsify on the spot.

def test_inpatient_rule_suppressed_on_outpatient_care_setting() -> None:
    """Inpatient-scoped flag must not fire when care_setting is outpatient."""
    hits = check_material_bundling_prose(
        [
            {
                "name": "Omuz artroplasti implantı",
                "code": "AP1030",
                "unit_price": 12500.0,
                "non_reimbursed_inpatient_patient_charge": True,
            }
        ],
        care_setting="outpatient",
    )
    inpatient_hits = [
        h for h in hits if h["rule_id"] == "3.1.1.(7).non_reimbursed_inpatient_patient_charge"
    ]
    assert inpatient_hits == [], "inpatient rule must be suppressed on outpatient claim"


def test_inpatient_rule_fires_on_inpatient_care_setting() -> None:
    """The same rule MUST fire when the claim is genuinely inpatient (yatarak)."""
    hits = check_material_bundling_prose(
        [
            {
                "name": "Renal replasman seti",
                "code": "NF1017",
                "unit_price": 5000.0,
                "non_reimbursed_inpatient_patient_charge": True,
            }
        ],
        care_setting="inpatient",
    )
    inpatient_hits = [
        h for h in hits if h["rule_id"] == "3.1.1.(7).non_reimbursed_inpatient_patient_charge"
    ]
    assert len(inpatient_hits) == 1, "inpatient rule must fire on a yatarak claim"


def test_patient_charge_rule_message_cites_in_force_3_1_1_6() -> None:
    # In-force §3.1.1(6) (C002744) is the paragraph where the patient buys a
    # non-reimbursed inpatient material and the invoice is paid to the patient and
    # offset; in-force (7) is the EK-3/B clause. The rule id and its gate_b_sources
    # keep the historical (7) label until the owner decides on the L1.4 manifest
    # side effect of re-anchoring (see _EXTRA_MESSAGE_CITES in the golden test).
    hits = check_material_bundling_prose(
        [
            {
                "name": "Renal replasman seti",
                "code": "NF1017",
                "unit_price": 5000.0,
                "non_reimbursed_inpatient_patient_charge": True,
            }
        ],
        care_setting="inpatient",
    )
    (hit,) = [
        h for h in hits if h["rule_id"] == "3.1.1.(7).non_reimbursed_inpatient_patient_charge"
    ]
    assert "(§3.1.1(6))" in hit["message"]
    assert "§3.1.1(7)" not in hit["message"]


def test_inpatient_rule_uses_per_material_care_setting() -> None:
    """A mixed patient (one outpatient + one inpatient material) must gate each
    material by ITS OWN claim's care setting, not the patient's first claim."""
    hits = check_material_bundling_prose(
        [
            {
                "name": "Outpatient material",
                "code": "OP1",
                "unit_price": 5000.0,
                "non_reimbursed_inpatient_patient_charge": True,
                "care_setting": "outpatient",  # must suppress
            },
            {
                "name": "Inpatient material",
                "code": "IP1",
                "unit_price": 5000.0,
                "non_reimbursed_inpatient_patient_charge": True,
                "care_setting": "inpatient",  # must fire
            },
        ],
        care_setting="inpatient",  # global fallback, overridden per-material
    )
    rule_ids = [h["rule_id"] for h in hits]
    assert "3.1.1.(7).non_reimbursed_inpatient_patient_charge" in rule_ids
    # The outpatient material (OP1) must NOT carry the inpatient finding.
    op_hits = [h for h in hits if h.get("material_code") == "OP1"]
    assert not any(
        h["rule_id"] == "3.1.1.(7).non_reimbursed_inpatient_patient_charge"
        for h in op_hits
    )


def test_duplicate_material_code_lines_both_evaluated_in_bundling_prose() -> None:
    """#238 regression: two distinct lines sharing the same material_code must
    each be evaluated and preserve their material_line_id and claim_id."""
    hits = check_material_bundling_prose(
        [
            {
                "material_line_id": "MLZ-003",
                "claim_id": "F-053",
                "name": "STENT, TRAKEAL, SİLİKON, DÜZ",
                "code": "GHC1220",
                "unit_price": 18528.13,
            },
            {
                "material_line_id": "MLZ-004",
                "claim_id": "F-053",
                "name": "STENT, TRAKEAL, SİLİKON, DÜZ",
                "code": "GHC1220",
                "unit_price": 18528.13,
            },
        ]
    )
    assert len(hits) == 2
    assert [h["material_line_id"] for h in hits] == ["MLZ-003", "MLZ-004"]
    assert [h["claim_id"] for h in hits] == ["F-053", "F-053"]


def test_coronary_stent_clause_3_1_4_g_excludes_non_coronary_stents() -> None:
    """#231: non-coronary stents must not get §3.1.4(g), while coronary stents do."""
    non_coronary_hits = check_material_bundling_prose(
        [
            {
                "name": "STENT, TRAKEAL, SİLİKON, DÜZ, İNCE DUVARLI",
                "code": "GHC1230",
                "unit_price": 18528.13,
            },
            {
                "name": "Üreteral J stent",
                "code": "UR1000",
                "unit_price": 2400.0,
            },
        ]
    )
    assert not any(
        h["rule_id"] == "3.1.4.(g).coronary_stents" for h in non_coronary_hits
    )
    # Non-coronary stent lines still receive applicable §3.1 rules (e.g. procedure_pairing / not_in_ek3c)
    assert len(non_coronary_hits) == 2

    coronary_hits = check_material_bundling_prose(
        [
            {
                "name": "KORONER STENT, İLAÇ SALINIMLI",
                "code": "KR1151",
                "unit_price": 9500.0,
            },
            {
                "name": "STENT, KORONER, BALONA MONTE EDİLMİŞ ÇIPLAK",
                "code": "KR1150",
                "unit_price": 8000.0,
            },
        ]
    )
    coronary_rule_hits = [
        h for h in coronary_hits if h["rule_id"] == "3.1.4.(g).coronary_stents"
    ]
    assert len(coronary_rule_hits) == 2


def test_informational_3_1_4_finding_adds_zero_billed_at_risk_and_does_not_mask_violations() -> None:
    """#231: §3.1.4 informational findings have 0.0 risk_amount (0 TL billed at risk)
    and do not suppress subsequent §3.1 violation rules on the same material line."""
    from src.bilun.domain.billing.billing_actions import _material_row_billed_try

    hits = check_material_bundling_prose(
        [
            {
                "name": "KORONER STENT, İLAÇ SALINIMLI",
                "unit_price": 9500.0,
            }
        ]
    )
    info_hits = [h for h in hits if h["rule_id"] == "3.1.4.(g).coronary_stents"]
    violation_hits = [
        h for h in hits if h["rule_id"] == "3.1.1.(11).missing_material_code"
    ]
    assert len(info_hits) == 1
    assert info_hits[0]["severity"] == "info"
    assert info_hits[0]["risk_amount"] == 0.0
    assert _material_row_billed_try(info_hits[0]) is None
    assert len(violation_hits) == 1
    assert violation_hits[0]["risk_amount"] == 9500.0


# ── #262: hip hemiarthroplasty (showcase S5) ────────────────────────────────
_SEPARATE_BILLING = "3.1.1.(15).separate_billing_not_authorized"
_BONE_CEMENT = "3.1.4.(b).bone_cement"
_TITUBB_UTS = "3.1.1.(2).titubb_uts_incomplete"
_S5_STEM = ("AP2070", "KALÇA | PRİMER | FEMORAL STEM | ÇİMENTOSUZ | CoCr/TİTANYUM | KAPLAMALI - KUMLAMA")
_S5_HEAD = ("AP1880", "KALÇA | PRİMER | FEMORAL BIPOLAR BAŞ ( SHELL + İNSERT) | TÜM BOYLAR | CoCr")


def _package_claim_ctx(
    package_code: str,
    materials: list[tuple[str, str]],
    *,
    linked: bool = True,
    uts_registered: tuple[bool, ...] = (),
):
    """One inpatient claim: an EK-2/C package line on 2026-09-04 plus materials."""
    from datetime import date
    from decimal import Decimal

    from src.bilun.domain.claims.models import (
        ClaimHeader,
        MaterialClaimLine,
        ProcedureClaimLine,
    )
    from src.bilun.domain.claims.patient_context import PatientClaimContext

    day, amount = date(2026, 9, 4), Decimal("1000.00")
    header = ClaimHeader(
        claim_id="C1", patient_id="PT1", episode_id="E1", claim_type="yatis",
        facility_tier="2_3_basamak_ozel", provider_type="Ozel",
        department="Ortopedi ve Travmatoloji", admission_date=day, discharge_date=day,
        claim_start_date=day, claim_end_date=day, primary_icd10="S72.0",
        package_candidate=True, expected_total_billed_try=amount,
        expected_total_payable_try=amount, expected_denial_reason="", scenario_tag="",
    )
    package = ProcedureClaimLine(
        procedure_line_id="C1-P01", claim_id="C1", patient_id="PT1", episode_id="E1",
        procedure_date=day, procedure_code=package_code, procedure_name="paket",
        procedure_category="paket", quantity=1, unit_price_try=amount,
        billed_amount_try=amount, expected_payable_try=amount, is_package_included=False,
        package_code="", surcharge_applicable=False, copay_rate_applicable=False,
        denial_reason_expected="", rule_trace_expected="",
    )
    lines = tuple(
        MaterialClaimLine(
            material_line_id=f"C1-M{i:02d}", claim_id="C1",
            procedure_line_id="C1-P01" if linked else "", patient_id="PT1",
            material_date=day, material_code=code, material_name=name,
            material_type="implant", specialty_category="", quantity=1,
            unit_price_try=amount, billed_amount_try=amount, expected_payable_try=amount,
            is_bundled=False, requires_pre_auth=False, denial_reason_expected="",
            rule_trace_expected="", titubb_registered=True,
            uts_registered=uts_registered[i - 1] if uts_registered else True,
        )
        for i, (code, name) in enumerate(materials, start=1)
    )
    return PatientClaimContext(
        patient_id="PT1", claims=(header,), procedure_lines=(package,),
        material_lines=lines, drug_lines=(), diagnoses=(),
    )


def _rules_by_code(ctx) -> dict[str, list[str]]:
    from src.bilun.domain.prose_rules.material_bundling import (
        check_material_bundling_for_context,
    )

    out: dict[str, list[str]] = {}
    for hit in check_material_bundling_for_context(ctx):
        out.setdefault(hit["material_code"], []).append(hit["rule_id"])
    return out


def test_clean_hip_hemiarthroplasty_gets_no_separate_billing_or_bone_cement_row() -> None:
    """#262: P612320 + EK-3/F-1 cementless stem and bipolar head is a correct bill."""
    rules = _rules_by_code(_package_claim_ctx("P612320", [_S5_STEM, _S5_HEAD]))
    flat = [rule for hits in rules.values() for rule in hits]
    assert _SEPARATE_BILLING not in flat
    assert _BONE_CEMENT not in flat


def test_faulty_hip_hemiarthroplasty_still_gets_titubb_uts_incomplete() -> None:
    """#262: the stem billed without a completed ÜTS notification is still no-pay."""
    rules = _rules_by_code(
        _package_claim_ctx("P612320", [_S5_STEM, _S5_HEAD], uts_registered=(False, True))
    )
    assert _TITUBB_UTS in rules["AP2070"]
    assert _SEPARATE_BILLING not in rules.get("AP1880", [])


def test_joint_implant_category_holds_without_a_package_line() -> None:
    """#262: §3.1.4(2)(ç) is SUT permission for the joint implant on any claim."""
    hits = check_material_bundling_prose(
        [{"name": _S5_STEM[1], "code": _S5_STEM[0], "unit_price": 12630.99}]
    )
    assert not any(hit["rule_id"] == _SEPARATE_BILLING for hit in hits)


def test_material_without_any_permission_is_still_warned_on_a_package_claim() -> None:
    """#262 true positive: an EK-3/F-1 tourniquet is no implant, and P612320 bills only the prosthesis."""
    tourniquet = ("AP3260", "DİZ | PRİMER/REVİZYON | TEK KULLANIMLIK TURNİKE | TÜM BOYLAR")
    rules = _rules_by_code(_package_claim_ctx("P612320", [_S5_STEM, tourniquet]))
    assert rules["AP3260"] == [_SEPARATE_BILLING]
    assert _SEPARATE_BILLING not in rules.get("AP2070", [])

    hits = check_material_bundling_prose(
        [{"name": tourniquet[1], "code": tourniquet[0], "unit_price": 980.67}]
    )
    assert [hit["rule_id"] for hit in hits] == [_SEPARATE_BILLING]
    assert hits[0]["risk_amount"] == 980.67
    # rule_id keeps its legacy (15) label; the clause it cites is §3.1.1(13) (C002751).
    assert hits[0]["clause_ref"]["clause_coordinate"] == "3.1.1.(13)"


def test_ek2c_aciklama_naming_the_code_allows_separate_billing() -> None:
    """#262: P614870 "KN1271, ..., KN1064 ... malzemeleri ayrıca faturalandırılır"."""
    electrode = ("KN1064", "BEYİN ELEKTRODU (LEAD)")
    assert _SEPARATE_BILLING not in _rules_by_code(
        _package_claim_ctx("P614870", [electrode])
    ).get("KN1064", [])
    # Unlinked materials read every package on their claim.
    assert _SEPARATE_BILLING not in _rules_by_code(
        _package_claim_ctx("P614870", [electrode], linked=False)
    ).get("KN1064", [])
    # Without that package nothing in SUT or its annexes bills it separately.
    assert _SEPARATE_BILLING in _rules_by_code(
        _package_claim_ctx("P612320", [electrode])
    )["KN1064"]


def test_ek2c_aciklama_dahildir_keeps_the_separate_billing_warning() -> None:
    """#262: P621180 bills the penile prosthesis separately; P621190 includes it."""
    prosthesis = ("UR1001", "İNFLATABLE PROTEZLERİ SET (İKİ PARÇALI)")
    assert _SEPARATE_BILLING not in _rules_by_code(
        _package_claim_ctx("P621180", [prosthesis])
    ).get("UR1001", [])
    assert _SEPARATE_BILLING in _rules_by_code(
        _package_claim_ctx("P621190", [prosthesis])
    )["UR1001"]


def test_bone_cement_rule_matches_real_cement_rows_and_no_ek3f1_row() -> None:
    """#262: the bare keyword "çimento" also matched ÇİMENTOSUZ/ÇİMENTOLU stems."""
    import polars as pl

    from src.bilun.domain.constants import _GAZETTE_CURATED_DIR

    cement_rows = [
        # EK-3/F-1 bone cements (repealed 30/04/2024, so absent from the curated list).
        ("AP3180", "KALÇA/DİZ | PRİMER/REVİZYON | KEMİK ÇİMENTOSU - ANTİBİYOTİKLİ | STANDART - 40 gr | PMMA"),
        ("AP3220", "KALÇA/DİZ | PRİMER/REVİZYON | KEMİK ÇİMENTOSU - NORMAL | STANDART - 40 gr | PMMA"),
    ]
    spine = pl.read_parquet(_GAZETTE_CURATED_DIR / "ek3e1_spine_surgery_materials.parquet")
    cement_rows += spine.filter(pl.col("sut_code").is_in(["102295", "102296", "102465"])).select(
        "sut_code", "material_name"
    ).rows()
    assert len(cement_rows) == 5
    hits = check_material_bundling_prose(
        [{"name": name, "code": code, "unit_price": 100.0} for code, name in cement_rows]
    )
    assert sorted(h["material_code"] for h in hits if h["rule_id"] == _BONE_CEMENT) == sorted(
        code for code, _ in cement_rows
    )

    ek3f1 = pl.read_parquet(_GAZETTE_CURATED_DIR / "ek3f1_arthroplasty_materials.parquet")
    names = ek3f1.select(
        "sut_code", pl.concat_str(["material_name", "description"], separator=" | ")
    ).rows()
    assert len(names) == 337
    hits = check_material_bundling_prose(
        [{"name": name, "code": code, "unit_price": 100.0} for code, name in names]
    )
    assert not [h["material_code"] for h in hits if h["rule_id"] == _BONE_CEMENT]

