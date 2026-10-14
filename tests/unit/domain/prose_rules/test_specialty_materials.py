"""Unit tests for §3.3 specialty materials prose (L4.4 pilot)."""

from __future__ import annotations

import pytest

from src.bilun.domain.prose_rules.specialty_materials import (
    check_specialty_materials_prose,
    load_specialty_materials_rules,
)

pytestmark = pytest.mark.unit


def test_specialty_rules_loaded() -> None:
    ruleset = load_specialty_materials_rules()
    assert ruleset["rule_set_id"] == "specialty_materials_prose"
    assert len(ruleset.get("rules") or []) >= 49


def test_wound_dressing_cover_no_pay_keyword() -> None:
    hits = check_specialty_materials_prose(
        [{"name": "Transparan film yara örtüsü", "code": "WD1", "unit_price": 25.0}]
    )
    assert hits
    assert hits[0]["rule_id"] == "3.3.1.(10).wound_dressing_cover_no_pay"
    assert hits[0]["material_outcome"] == "no_pay"


def test_wound_hydrojel_no_pay() -> None:
    hits = check_specialty_materials_prose(
        [{"name": "Hidrojel yara nemlendirici", "code": "H1", "unit_price": 40.0}]
    )
    assert hits[0]["rule_id"] == "3.3.1.(10).wound_hydrojel_additive_no_pay"


def test_skin_substitute_non_burn_flag() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Malzeme",
                "code": "SS1",
                "unit_price": 200.0,
                "skin_substitute_non_burn_use": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.1.(10).skin_substitute_non_burn_flag"


def test_skin_substitute_keyword_no_pay() -> None:
    hits = check_specialty_materials_prose(
        [{"name": "Deri taklidi yedek", "code": "SS2", "unit_price": 300.0}]
    )
    assert hits[0]["rule_id"] == "3.3.1.(10).skin_substitute_keyword_no_pay"


def test_immunobullous_patient_dispensed() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Yara bakım malzemesi",
                "code": "IB1",
                "unit_price": 50.0,
                "immunobullous_wound_care_patient_supply": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.1.(13).immunobullous_patient_dispensed"
    assert hits[0]["material_outcome"] == "review_required"


def test_immunobullous_non_moh_supply() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Yara bakım",
                "code": "IB2",
                "unit_price": 80.0,
                "immunobullous_wound_care_non_moh_facility": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.1.(13).immunobullous_non_moh_supply"


def test_zero_price_skipped() -> None:
    hits = check_specialty_materials_prose(
        [{"name": "Transparan film", "code": "Z1", "unit_price": 0.0}]
    )
    assert hits == []


def test_contact_lens_solution_keyword() -> None:
    hits = check_specialty_materials_prose(
        [{"name": "Kontakt lens solüsyonu", "code": "CL1", "unit_price": 15.0}]
    )
    assert hits[0]["rule_id"] == "3.3.3.C.(6).contact_lens_solution"


def test_ek3d_lens_upgrade_difference() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Gözlük camı",
                "code": "G1",
                "unit_price": 100.0,
                "optical_lens_upgrade_difference_claim": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.3.A.(4).ek3d_lens_upgrade_difference"


def test_tv5680_combo_flag() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "TV malzeme",
                "code": "TV5680",
                "unit_price": 50.0,
                "tv5680_with_tv1080_tv1090_combo": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.34.(4).tv5680_combo_billing"


def test_cochlear_implant_under_12_months() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Koklear implant",
                "code": "KI1",
                "unit_price": 5000.0,
                "cochlear_implant_under_12_months": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.36.B.(10).cochlear_implant_under_12_months"


def test_bone_stimulator_combined_use() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "DBM kemik materyali",
                "code": "BS1",
                "unit_price": 200.0,
                "bone_stimulator_combined_use": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.4.A.(1).bone_stimulator_combined_use"


def test_dermis_allograft_keyword() -> None:
    hits = check_specialty_materials_prose(
        [{"name": "Dermis allogreft", "code": "DG1", "unit_price": 150.0}]
    )
    assert hits[0]["rule_id"] == "3.3.4.(4).dermis_allograft_no_pay"


def test_primary_ligament_tendon_graft() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Greft",
                "code": "LG1",
                "unit_price": 80.0,
                "primary_ligament_tendon_injury_graft": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.4.B.c.primary_ligament_tendon_graft"


def test_glucose_meter_early_renewal() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Kan şekeri ölçüm cihazı",
                "code": "GM1",
                "unit_price": 120.0,
                "glucose_meter_early_renewal": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.2.b.kan_sekeri_cihaz_yenileme_no_pay"


def test_stand_up_wheelchair_early_renewal() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Stand up wheelchair",
                "code": "WC1",
                "unit_price": 500.0,
                "stand_up_wheelchair_early_renewal": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.7.B.(3).stand_up_wheelchair_early_renewal"


def test_wheelchair_stand_device_duplicate() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Ayakta dik konumlandırma",
                "code": "ST1",
                "unit_price": 300.0,
                "wheelchair_stand_device_duplicate_billing": True,
            },
            # Co-material gate: a wheelchair must be co-billed for the rule to fire.
            {"name": "Tekerlekli sandalye", "code": "WC1", "unit_price": 500.0},
        ]
    )
    assert hits[0]["rule_id"] == "3.3.7.B.(2).wheelchair_stand_device_duplicate"


def test_returned_device_without_kurum_approval() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "CPAP cihazı",
                "code": "RD1",
                "unit_price": 400.0,
                "returned_device_without_kurum_approval": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.6.(2).returned_device_without_kurum_approval"


def test_nimv_heated_humidifier_separate() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Isıtıcılı nemlendirici",
                "code": "HN1",
                "unit_price": 80.0,
                "nimv_heated_humidifier_separate_billing": True,
            },
            # Co-material gate: an NIMV device must be co-billed for the rule to fire.
            {"name": "NIMV cihazı (spinal)", "code": "NV1", "unit_price": 400.0},
        ]
    )
    assert hits[0]["rule_id"] == "3.3.6.A-1.heated_humidifier_nimv_separate"


def test_paraplegia_standing_table_over_age() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Standing table",
                "code": "ST2",
                "unit_price": 200.0,
                "paraplegia_standing_table_over_age_limit": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.8.A.d.paraplegia_standing_table_over_age"


def test_spinal_mobility_device_duplicate() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Parapodium",
                "code": "PP1",
                "unit_price": 150.0,
                "spinal_mobility_device_duplicate_billing": True,
            },
            # Co-material gate: a spinal device must be co-billed for the rule to fire.
            {"name": "Spinal mobilite cihazı", "code": "SM1", "unit_price": 600.0},
        ]
    )
    assert hits[0]["rule_id"] == "3.3.8.B.(2).spinal_mobility_device_bundle_excluded"


def test_dental_prosthesis_adhesive_keyword() -> None:
    hits = check_specialty_materials_prose(
        [{"name": "Protez yapıştırıcı", "code": "DA1", "unit_price": 25.0}]
    )
    assert hits[0]["rule_id"] == "3.3.12.(4).dental_prosthesis_adhesive_no_pay"


def test_dual_mesh_primary_hernia_flag() -> None:
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Mesh",
                "code": "M1",
                "unit_price": 300.0,
                "dual_mesh_primary_hernia_repair": True,
            }
        ]
    )
    assert hits[0]["rule_id"] == "3.3.16.(4).dual_mesh_primary_hernia_no_pay"


# ── Co-material presence gate (false-positive guard) ─────────────────────────
# The §3.3.7.B(2) wheelchair duplicate-billing rule asserts a SECOND device
# (wheelchair) was co-billed. It must NOT fire on a lone material with no
# wheelchair present — that is a false violation an auditor can falsify.

def test_wheelchair_duplicate_rule_suppressed_without_comaterial() -> None:
    """A lone shoulder implant with the flag set but NO wheelchair on the claim
    must not trigger the wheelchair duplicate-billing rule."""
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Omuz artroplasti implantı",
                "code": "AP1030",
                "unit_price": 12500.0,
                "wheelchair_stand_device_duplicate_billing": True,
            }
        ]
    )
    wheelchair_hits = [
        h for h in hits if h["rule_id"] == "3.3.7.B.(2).wheelchair_stand_device_duplicate"
    ]
    assert wheelchair_hits == [], "wheelchair rule must not fire without a wheelchair present"


def test_wheelchair_duplicate_rule_fires_with_comaterial() -> None:
    """When a wheelchair IS co-billed, the duplicate rule must fire on the
    flagged standing-device material."""
    hits = check_specialty_materials_prose(
        [
            {
                "name": "Ayakta dik konumlandırma cihazı",
                "code": "STD1",
                "unit_price": 8000.0,
                "wheelchair_stand_device_duplicate_billing": True,
            },
            {
                "name": "Tekerlekli sandalye, manuel",
                "code": "WC1",
                "unit_price": 5000.0,
            },
        ]
    )
    wheelchair_hits = [
        h for h in hits if h["rule_id"] == "3.3.7.B.(2).wheelchair_stand_device_duplicate"
    ]
    assert len(wheelchair_hits) == 1, "wheelchair rule must fire when a wheelchair is co-billed"


def test_duplicate_material_code_lines_both_evaluated_in_specialty_prose() -> None:
    """#238 regression: two distinct lines with the same material_code must both
    emit specialty prose findings and retain their material_line_id and claim_id."""
    hits = check_specialty_materials_prose(
        [
            {
                "material_line_id": "MLZ-1",
                "claim_id": "C1",
                "name": "Transparan film yara örtüsü",
                "code": "WD1",
                "unit_price": 25.0,
            },
            {
                "material_line_id": "MLZ-2",
                "claim_id": "C1",
                "name": "Transparan film yara örtüsü",
                "code": "WD1",
                "unit_price": 40.0,
            },
        ]
    )
    assert len(hits) == 2
    assert [h["material_line_id"] for h in hits] == ["MLZ-1", "MLZ-2"]
    assert [h["claim_id"] for h in hits] == ["C1", "C1"]
    assert [h["risk_amount"] for h in hits] == [25.0, 40.0]

