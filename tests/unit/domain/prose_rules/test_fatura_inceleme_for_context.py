"""Tests for the Fatura İnceleme Usul ve Esasları prose rule motor.

These tests verify the motor fires correctly on denial conditions and
honest-skips when conditions don't match (wrong branch, wrong care setting,
missing data).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from src.bilun.domain.prose_rules.fatura_inceleme import (
    _branch_matches,
    _condition_matches,
    check_fatura_inceleme,
    check_fatura_inceleme_for_context,
    load_fatura_inceleme_rules,
)
from tests.unit._helpers.brittle_guards import soft_floor


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_ctx(
    *,
    department: str = "Kardiyoloji",
    claim_type: str = "Ayakta",
    procedure_category: str | None = None,
    procedure_code: str | None = None,
    is_emergency: bool = False,
    care_setting: str | None = None,
    provider_type: str = "sozlesmeli",
    facility_tier: str = "Özel Sağlık Tesisleri",
    drug_category: str | None = None,
) -> SimpleNamespace:
    """Build a minimal PatientClaimContext-like object for testing."""
    claim_type_val = claim_type
    if is_emergency:
        department = "Acil Servis"
        claim_type_val = "Acil"

    header = SimpleNamespace(
        claim_id="TEST-001",
        department=department,
        claim_type=claim_type_val,
        provider_type=provider_type,
        facility_tier=facility_tier,
        scenario_tag="",
        procedure_specialty_code="",
        admission_date=None,
        claim_start_date=None,
    )

    procedure_lines = []
    if procedure_code or procedure_category:
        procedure_lines.append(
            SimpleNamespace(
                claim_id="TEST-001",
                procedure_code=procedure_code or "",
                procedure_category=procedure_category or "",
                procedure_date=None,
            )
        )

    drug_lines = []
    if drug_category:
        drug_lines.append(
            SimpleNamespace(
                claim_id="TEST-001",
                drug_category=drug_category,
                drug_specialty_board_report_present=False,
            )
        )

    return SimpleNamespace(
        claims=[header],
        procedure_lines=procedure_lines,
        drug_lines=drug_lines,
        material_lines=[],
    )


# ── Rule loading ────────────────────────────────────────────────────────────

def test_rules_load_successfully() -> None:
    """The rule JSON loads and contains 91 rules."""
    ruleset = load_fatura_inceleme_rules()
    assert ruleset["rule_set_id"] == "fatura_inceleme_prose"
    rules = ruleset.get("rules") or []
    soft_floor(len(rules), 70, label="fatura_inceleme_prose")


def test_all_rules_have_required_fields() -> None:
    """Every rule has rule_id, sut_section, gate_b_sources, condition, action."""
    ruleset = load_fatura_inceleme_rules()
    for rule in ruleset["rules"]:
        assert "rule_id" in rule, f"Missing rule_id: {rule}"
        assert "sut_section" in rule, f"Missing sut_section: {rule['rule_id']}"
        assert "gate_b_sources" in rule, f"Missing gate_b_sources: {rule['rule_id']}"
        assert "condition" in rule, f"Missing condition: {rule['rule_id']}"
        assert "action" in rule, f"Missing action: {rule['rule_id']}"
        assert len(rule["gate_b_sources"]) >= 1
        for src in rule["gate_b_sources"]:
            assert src.startswith("F"), f"Non-F gate_b_source: {src}"


# ── Branch matching ─────────────────────────────────────────────────────────

def test_branch_matches_ortak_for_all_departments() -> None:
    """ORTAK rules (branch=null) match any department."""
    assert _branch_matches(None, {"department": "Kardiyoloji"}) is True
    assert _branch_matches(None, {"department": "Acil Servis"}) is True
    assert _branch_matches(None, {"department": ""}) is True


def test_branch_matches_specific_branch() -> None:
    """Branch-specific rules match when department contains keywords."""
    assert _branch_matches("KARDİYOLOJİ", {"department": "Kardiyoloji"}) is True
    assert _branch_matches("ACİL TIP HEKİMLİĞİ", {"department": "Acil Servis"}) is True
    assert _branch_matches("KULAK BURUN BOĞAZ", {"department": "KBB"}) is True


def test_branch_does_not_match_wrong_department() -> None:
    """Branch-specific rules skip when department doesn't match."""
    assert _branch_matches("KARDİYOLOJİ", {"department": "Dahiliye"}) is False
    assert _branch_matches("ORTOPEDİ VE TRAVMATOLOJİ", {"department": "Kardiyoloji"}) is False


# ── Condition matching ──────────────────────────────────────────────────────

def test_condition_matches_boolean_true() -> None:
    """Boolean flag matches when context value is true."""
    assert _condition_matches({"is_emergency": True}, {"is_emergency": True}) is True


def test_condition_does_not_match_boolean_false() -> None:
    """Boolean flag does not match when context value is false."""
    assert _condition_matches({"is_emergency": True}, {"is_emergency": False}) is False


def test_condition_matches_set_membership() -> None:
    """Set membership matches when at least one value is present."""
    ctx = {"procedure_code_any": ["530160", "700620"]}
    assert _condition_matches({"procedure_code_any": ["530160"]}, ctx) is True


def test_condition_honest_skips_missing_field() -> None:
    """Condition returns False (honest skip) when field is absent."""
    assert _condition_matches({"care_setting": "outpatient"}, {}) is False


# ── Integration: motor fires on matching claims ─────────────────────────────

def test_ortak7_acilde_kontrol_muayenesi_fires() -> None:
    """ORTAK-7: acil serviste kontrol muayenesi → violation."""
    ctx = _make_ctx(
        department="Acil Servis",
        is_emergency=True,
        procedure_category="kontrol_muayene",
    )
    violations = check_fatura_inceleme_for_context(ctx)
    # ORTAK-7 should fire
    ortak7 = [v for v in violations if "ORTAK-7" in v.get("details", {}).get("fatura_inceleme_ref", "")]
    assert len(ortak7) >= 1, f"Expected ORTAK-7 violation, got: {[v['rule_id'] for v in violations]}"
    assert ortak7[0]["billable"] is False


def test_ortak7_does_not_fire_non_emergency() -> None:
    """ORTAK-7 should NOT fire when not in emergency department."""
    ctx = _make_ctx(
        department="Kardiyoloji",
        is_emergency=False,
        procedure_category="kontrol_muayene",
    )
    violations = check_fatura_inceleme_for_context(ctx)
    ortak7 = [v for v in violations if "ORTAK-7" in v.get("details", {}).get("fatura_inceleme_ref", "")]
    assert len(ortak7) == 0


def test_ortak16_iv_infuzyon_fires() -> None:
    """ORTAK-16: 530160 IV infüzyon without IV drugs → violation."""
    ctx = _make_ctx(
        procedure_code="530160",
    )
    violations = check_fatura_inceleme_for_context(ctx)
    ortak16 = [v for v in violations if "ORTAK-16" in v.get("details", {}).get("fatura_inceleme_ref", "")]
    assert len(ortak16) >= 1, f"Expected ORTAK-16 violation, got: {[v['rule_id'] for v in violations]}"


def test_branch_specific_rule_skips_wrong_department() -> None:
    """A KARDİYOLOJİ rule should not fire on a Dermatoloji claim."""
    ctx = _make_ctx(
        department="Dermatoloji",
        procedure_code="700811",  # Kardiyoloji code
    )
    violations = check_fatura_inceleme_for_context(ctx)
    kard_rules = [v for v in violations if v.get("sut_section") == "KARDİYOLOJİ"]
    assert len(kard_rules) == 0, f"Kardiyoloji rules fired on Dermatoloji claim: {kard_rules}"


def test_empty_context_returns_empty() -> None:
    """Empty context (no claims) returns no violations."""
    ctx = SimpleNamespace(claims=[], procedure_lines=[], drug_lines=[], material_lines=[])
    violations = check_fatura_inceleme_for_context(ctx)
    assert violations == []


def test_violations_have_correct_structure() -> None:
    """All violations have the expected dict structure."""
    ctx = _make_ctx(
        department="Acil Servis",
        is_emergency=True,
        procedure_category="kontrol_muayene",
    )
    violations = check_fatura_inceleme_for_context(ctx)
    for v in violations:
        assert "rule" in v
        assert "severity" in v
        assert "message" in v
        assert "rule_id" in v
        assert "billable" in v
        assert "material_outcome" in v
        assert "details" in v
        assert v["details"]["prose_rule_set"] == "fatura_inceleme_prose"


def test_rules_naming_no_billed_evidence_do_not_fire_on_every_bill_of_their_branch() -> None:
    """EI-24: four rules have no condition and GÖĞÜS-6 only the inpatient setting; the department alone is no evidence."""
    no_evidence = {
        "GÖĞÜS_HASTALIKLARI-6.yatan_hasta_derin_trakeal_aspirasyon",
        "KARDİYOLOJİ-4.ayni_seans_periferik_anjiografi",
        "KARDİYOLOJİ-9.kalp_kat_sirasi_cerrahi_sadece_cerrahi",
        "KALP_VE_DAMAR_CERRAHİSİ-1.kag_sonrasi_cabg_islem_yok_kesinti",
        "KALP_VE_DAMAR_CERRAHİSİ-4.ek2b_lazer_tedavi_kdc_odenmez",
    }
    for department, care_setting in (
        ("Kardiyoloji", "outpatient"),
        ("Kardiyoloji", "inpatient"),
        ("Göğüs Hastalıkları", "inpatient"),
        ("KVC", "inpatient"),
    ):
        flat = {"department": department, "care_setting": care_setting, "procedure_code_any": ["520030"]}
        assert not {v["rule_id"] for v in check_fatura_inceleme(flat)} & no_evidence, (department, care_setting)
    # a rule of the same branch keyed on a billed code still fires
    flat = {"department": "Kardiyoloji", "care_setting": "outpatient"}
    keyed = next(
        r for r in load_fatura_inceleme_rules()["rules"]
        if r["rule_id"] == "KARDİYOLOJİ-2.spect_gated_ayri_ayri_odeme"
    )
    fired = check_fatura_inceleme({**flat, **{k: v for k, v in keyed["condition"].items()}})
    assert "KARDİYOLOJİ-2.spect_gated_ayri_ayri_odeme" in {v["rule_id"] for v in fired}
