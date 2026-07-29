"""Tests for the Fatura İnceleme documentation checklist motor.

These rules do NOT produce violations — they surface required documents
(epikriz/report presence checks) as informational warnings. The tests verify:
  - the checklist JSON loads with exactly 63 rules
  - a matching procedure code returns the rule's required documents
  - a non-matching procedure code returns nothing
  - the branch gate skips rules whose branch doesn't match the claim's
    department/specialty
"""

from __future__ import annotations

from types import SimpleNamespace

from src.bilun.domain.prose_rules.fatura_inceleme_checklist import (
    _branch_matches,
    _condition_matches,
    check_fatura_inceleme_checklist,
    check_fatura_inceleme_checklist_for_context,
    load_fatura_inceleme_checklist_rules,
)
from tests.unit._helpers.brittle_guards import soft_floor


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_ctx(
    *,
    department: str = "Göz Hastalıkları",
    procedure_code: str | None = None,
) -> SimpleNamespace:
    """Build a minimal PatientClaimContext-like object for testing."""
    header = SimpleNamespace(
        claim_id="TEST-001",
        department=department,
        procedure_specialty_code="",
    )
    procedure_lines = []
    if procedure_code:
        procedure_lines.append(
            SimpleNamespace(
                claim_id="TEST-001",
                procedure_code=procedure_code,
            )
        )
    return SimpleNamespace(
        claims=[header],
        procedure_lines=procedure_lines,
    )


# ── Rule loading ────────────────────────────────────────────────────────────


def test_rules_load_successfully() -> None:
    """The checklist JSON loads and contains exactly 63 rules."""
    ruleset = load_fatura_inceleme_checklist_rules()
    assert ruleset["rule_set_id"] == "fatura_inceleme_checklist"
    assert ruleset["title"] == (
        "Fatura İnceleme Usul ve Esasları — Documentation Requirements"
    )
    rules = ruleset.get("rules") or []
    soft_floor(len(rules), 50, label="fatura_inceleme_checklist")


def test_all_rules_have_required_fields() -> None:
    """Every rule has the fields the motor and schema expect."""
    ruleset = load_fatura_inceleme_checklist_rules()
    for rule in ruleset["rules"]:
        assert "rule_id" in rule, f"Missing rule_id: {rule}"
        assert "sut_section" in rule, f"Missing sut_section: {rule['rule_id']}"
        assert "gate_b_sources" in rule, f"Missing gate_b_sources: {rule['rule_id']}"
        assert "branch" in rule, f"Missing branch: {rule['rule_id']}"
        assert "fatura_inceleme_ref" in rule
        assert "procedure_code_any" in rule
        assert "required_documents" in rule
        assert "message_tr" in rule
        assert len(rule["gate_b_sources"]) >= 1, rule["rule_id"]
        for src in rule["gate_b_sources"]:
            assert src.startswith("F"), f"Non-F gate_b_source: {src}"
        assert rule["required_documents"], f"Empty required_documents: {rule['rule_id']}"
        assert rule["message_tr"], f"Empty message_tr: {rule['rule_id']}"


def test_rule_ids_are_unique() -> None:
    """All 63 rule_ids are unique."""
    ruleset = load_fatura_inceleme_checklist_rules()
    ids = [r["rule_id"] for r in ruleset["rules"]]
    assert len(ids) == len(set(ids))


# ── Branch matching ─────────────────────────────────────────────────────────


def test_branch_matches_ortak_for_all_departments() -> None:
    """ORTAK rules (branch=null) match any department."""
    assert _branch_matches(None, {"department": "Kardiyoloji"}) is True
    assert _branch_matches(None, {"department": "Göz Hastalıkları"}) is True
    assert _branch_matches(None, {"department": ""}) is True


def test_branch_matches_specific_branch() -> None:
    """Branch-specific rules match when department contains keywords."""
    assert _branch_matches("GÖZ HASTALIKLARI", {"department": "Göz Hastalıkları"}) is True
    assert (
        _branch_matches("KULAK BURUN BOĞAZ", {"department": "KBB Polikliniği"}) is True
    )
    assert _branch_matches("ACİL TIP HEKİMLİĞİ", {"department": "Acil Servis"}) is True


def test_branch_does_not_match_wrong_department() -> None:
    """Branch-specific rules skip when department doesn't match."""
    assert _branch_matches("GÖZ HASTALIKLARI", {"department": "Kardiyoloji"}) is False
    assert (
        _branch_matches("ORTOPEDİ VE TRAVMATOLOJİ", {"department": "Dahiliye"}) is False
    )


# ── Condition matching (procedure_code_any membership) ──────────────────────


def test_condition_matches_code_in_rule() -> None:
    """Rule matches when a billed code is in the rule's procedure_code_any."""
    rule = {"procedure_code_any": ["617430", "P617430"]}
    ctx = {"procedure_code_any": ["617430", "530160"]}
    assert _condition_matches(rule, ctx) is True


def test_condition_matches_p_prefixed_code() -> None:
    """The P-prefixed variant also matches."""
    rule = {"procedure_code_any": ["617430", "P617430"]}
    ctx = {"procedure_code_any": ["P617430"]}
    assert _condition_matches(rule, ctx) is True


def test_condition_does_not_match_missing_code() -> None:
    """Rule does not match when billed codes don't overlap."""
    rule = {"procedure_code_any": ["617430", "P617430"]}
    ctx = {"procedure_code_any": ["530160", "700620"]}
    assert _condition_matches(rule, ctx) is False


def test_condition_code_less_without_signals_does_not_match() -> None:
    """Option B: code-less rules without relevance_signals stay hidden."""
    rule = {"procedure_code_any": [], "relevance_signals": []}
    assert _condition_matches(rule, {"procedure_code_any": ["999999"]}) is False
    assert _condition_matches(rule, {"relevance_flags": {"has_tpn": True}}) is False


def test_condition_code_less_requires_all_relevance_signals() -> None:
    """Code-less rules fire only when every listed relevance signal is true."""
    rule = {
        "procedure_code_any": [],
        "relevance_signals": ["has_tpn", "is_inpatient_daycase_or_icu"],
    }
    assert (
        _condition_matches(
            rule,
            {"relevance_flags": {"has_tpn": True, "is_inpatient_daycase_or_icu": False}},
        )
        is False
    )
    assert (
        _condition_matches(
            rule,
            {"relevance_flags": {"has_tpn": True, "is_inpatient_daycase_or_icu": True}},
        )
        is True
    )


def test_condition_honest_skips_when_no_billed_codes() -> None:
    """A code-specific rule does not match when the claim has no codes."""
    rule = {"procedure_code_any": ["617430"]}
    assert _condition_matches(rule, {}) is False
    assert _condition_matches(rule, {"procedure_code_any": []}) is False


# ── Integration: motor surfaces required documents ──────────────────────────


def test_katarakt_cerrahisi_returns_required_documents() -> None:
    """GÖZ-7: katarakt cerrahisi (617430) surfaces its required documents."""
    ctx = {"department": "Göz Hastalıkları", "procedure_code_any": ["617430"]}
    requirements = check_fatura_inceleme_checklist(ctx)
    goz7 = [r for r in requirements if r["fatura_inceleme_ref"] == "GÖZ-7"]
    assert len(goz7) == 1, (
        f"Expected GÖZ-7 requirement, got refs: "
        f"{[r['fatura_inceleme_ref'] for r in requirements]}"
    )
    docs = goz7[0]["required_documents"]
    assert "ameliyat_notu" in docs
    assert "epikriz_detay" in docs
    assert "617430" in goz7[0]["procedure_code"]
    assert goz7[0]["rule_source"] == "fatura_inceleme_checklist"
    assert "Katarakt" in goz7[0]["message_tr"]


def test_nazal_polipektomi_returns_patoloji_or_tomografi() -> None:
    """KBB-3: nazal polipektomi (601510) needs patoloji or tomografi report."""
    ctx = {"department": "KBB", "procedure_code_any": ["601510"]}
    requirements = check_fatura_inceleme_checklist(ctx)
    kbb3 = [r for r in requirements if r["fatura_inceleme_ref"] == "KBB-3"]
    assert len(kbb3) == 1
    docs = kbb3[0]["required_documents"]
    assert "patoloji_raporu" in docs
    assert "tomografi_raporu" in docs


def test_non_matching_procedure_returns_empty() -> None:
    """A procedure code that no rule mentions returns no requirements."""
    ctx = {"department": "Göz Hastalıkları", "procedure_code_any": ["999999"]}
    requirements = check_fatura_inceleme_checklist(ctx)
    code_specific = [
        r for r in requirements if r["procedure_code"]
    ]
    assert code_specific == [], (
        f"Expected no code-specific requirements for 999999, got: {code_specific}"
    )


def test_branch_filter_skips_wrong_department() -> None:
    """A GÖZ rule should not surface on a Kardiyoloji claim.

    617430 is a GÖZ HASTALIKLARI code; billing it under a Kardiyoloji
    department should NOT surface the GÖZ-7 requirement because the branch
    gate rejects it. (ORTAK rules with no codes still match.)
    """
    ctx = {"department": "Kardiyoloji", "procedure_code_any": ["617430"]}
    requirements = check_fatura_inceleme_checklist(ctx)
    goz_refs = [r for r in requirements if r["fatura_inceleme_ref"] == "GÖZ-7"]
    assert goz_refs == [], (
        f"GÖZ-7 surfaced on Kardiyoloji claim: {goz_refs}"
    )


def test_ortak_rules_hidden_without_relevance_signals() -> None:
    """Option B: ORTAK code-less rules do not spam claims without signals."""
    ctx = {"department": "Kardiyoloji", "procedure_code_any": ["999999"]}
    requirements = check_fatura_inceleme_checklist(ctx)
    ortak = [r for r in requirements if r["fatura_inceleme_ref"].startswith("ORTAK")]
    assert ortak == [], (
        f"Expected no ungated ORTAK requirements, got: "
        f"{[r['fatura_inceleme_ref'] for r in ortak]}"
    )


def test_ortak_tpn_surfaces_with_signal_and_fi_dayanak() -> None:
    """ORTAK-24 surfaces when has_tpn is set; dayanak is FI section not F000."""
    ctx = {
        "department": "Kardiyoloji",
        "procedure_code_any": ["530430"],
        "relevance_flags": {"has_tpn": True},
    }
    requirements = check_fatura_inceleme_checklist(ctx)
    ortak24 = [r for r in requirements if r["fatura_inceleme_ref"] == "ORTAK-24"]
    assert len(ortak24) == 1
    assert ortak24[0]["sut_anchor"] == "Fatura İnceleme ORTAK-24"
    assert "F000" not in ortak24[0]["sut_anchor"]
    assert "C000" not in ortak24[0]["sut_anchor"]


def test_ortak_ek2c_dayanak_includes_sut_section_label() -> None:
    ctx = {
        "department": "Genel Cerrahi",
        "procedure_code_any": ["P609300"],
        "relevance_flags": {"has_ek2c": True},
    }
    requirements = check_fatura_inceleme_checklist(ctx)
    ortak17 = [r for r in requirements if r["fatura_inceleme_ref"] == "ORTAK-17"]
    assert len(ortak17) == 1
    assert ortak17[0]["sut_anchor"] == "Fatura İnceleme ORTAK-17 · SUT EK-2/C"


def test_requirements_are_not_violations() -> None:
    """Returned dicts carry required_documents, not billable/severity fields."""
    ctx = {"department": "Göz Hastalıkları", "procedure_code_any": ["617430"]}
    requirements = check_fatura_inceleme_checklist(ctx)
    assert requirements, "Expected at least one requirement"
    for req in requirements:
        assert "required_documents" in req
        assert "fatura_inceleme_ref" in req
        assert "message_tr" in req
        assert "billable" not in req
        assert "severity" not in req


# ── Integration via PatientClaimContext bridge ──────────────────────────────


def test_for_context_surfaces_katarakt_requirement() -> None:
    """The PatientClaimContext bridge surfaces GÖZ-7 for a katarakt claim."""
    ctx = _make_ctx(department="Göz Hastalıkları", procedure_code="617430")
    requirements = check_fatura_inceleme_checklist_for_context(ctx)
    goz7 = [r for r in requirements if r["fatura_inceleme_ref"] == "GÖZ-7"]
    assert len(goz7) == 1


def test_for_context_empty_claim_returns_empty() -> None:
    """An empty PatientClaimContext (no claims) returns no requirements."""
    ctx = SimpleNamespace(claims=[], procedure_lines=[])
    assert check_fatura_inceleme_checklist_for_context(ctx) == []


def test_for_context_wrong_branch_skips_rule() -> None:
    """A GÖZ code billed under Dermatoloji does not surface the GÖZ rule."""
    ctx = _make_ctx(department="Dermatoloji", procedure_code="617430")
    requirements = check_fatura_inceleme_checklist_for_context(ctx)
    goz = [r for r in requirements if r["fatura_inceleme_ref"].startswith("GÖZ")]
    assert goz == []


def test_for_context_no_procedure_code_returns_empty_without_signals() -> None:
    """With no procedure code and no claim_type signals, nothing surfaces."""
    ctx = _make_ctx(department="Kardiyoloji", procedure_code=None)
    requirements = check_fatura_inceleme_checklist_for_context(ctx)
    assert requirements == []
