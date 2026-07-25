"""Regression tests for §2.4 treatment-pricing + dental encoded rules.

Validates three things:
1. Rule JSON structure is well-formed (required keys, valid action shape).
2. Provenance integrity: every gate_b_sources clause ID exists in the SUT corpus.
3. Golden fixtures match the rules (clause → rule_id mapping round-trips).
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_RULES_DIR = _PROJECT_ROOT / "data/gazette/prose_rules"
_GOLDEN_DIR = _RULES_DIR / "golden"
_CLAUSES_PATH = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"

pytestmark = pytest.mark.unit

_REQUIRED_RULE_KEYS = {"rule_id", "sut_section", "condition", "action", "gate_b_sources"}
_VALID_SEVERITY = {"error", "warning", "info", None}


@pytest.fixture(scope="module")
def clauses_frame() -> set[str]:
    df = pl.read_parquet(_CLAUSES_PATH)
    return set(df["clause_id"].to_list())


@pytest.fixture(scope="module")
def clauses_polars() -> pl.DataFrame:
    return pl.read_parquet(_CLAUSES_PATH)


def _resolved_clause_ids(refs: list, clauses: pl.DataFrame) -> set[str]:
    from scripts.sut.prose.clause_identity import (
        AmbiguousClauseCiteError,
        UnknownClauseCiteError,
        is_clause_id,
        resolve_gate_b_ref_to_clause_ids,
    )

    out: set[str] = set()
    for raw in refs:
        ref = str(raw)
        if is_clause_id(ref):
            out.add(ref)
            continue
        try:
            out.update(
                resolve_gate_b_ref_to_clause_ids(
                    ref,
                    clauses,
                    in_force_only=True,
                    allow_ambiguous=True,
                )
            )
        except (AmbiguousClauseCiteError, UnknownClauseCiteError):
            out.add(ref)
    return out


@pytest.fixture(scope="module")
def treatment_rules() -> list[dict]:
    payload = json.loads((_RULES_DIR / "treatment_pricing_2_4.json").read_text(encoding="utf-8"))
    return payload["rules"]


@pytest.fixture(scope="module")
def dental_rules() -> list[dict]:
    payload = json.loads((_RULES_DIR / "dental_2_4_1.json").read_text(encoding="utf-8"))
    return payload["rules"]


# ── Structure tests ────────────────────────────────────────────────────────

def test_treatment_rules_have_required_keys(treatment_rules):
    assert len(treatment_rules) >= 30, f"expected ≥30 treatment rules, got {len(treatment_rules)}"
    for r in treatment_rules:
        missing = _REQUIRED_RULE_KEYS - set(r.keys())
        assert not missing, f"{r.get('rule_id')}: missing keys {missing}"


def test_dental_rules_have_required_keys(dental_rules):
    assert len(dental_rules) >= 8, f"expected ≥8 dental rules, got {len(dental_rules)}"
    for r in dental_rules:
        missing = _REQUIRED_RULE_KEYS - set(r.keys())
        assert not missing, f"{r.get('rule_id')}: missing keys {missing}"


def test_rule_ids_unique(treatment_rules, dental_rules):
    all_ids = [r["rule_id"] for r in treatment_rules + dental_rules]
    assert len(all_ids) == len(set(all_ids)), "duplicate rule_id detected"


def test_actions_well_formed(treatment_rules, dental_rules):
    for r in treatment_rules + dental_rules:
        action = r["action"]
        assert isinstance(action, dict), f"{r['rule_id']}: action must be dict"
        # billable is the key decision flag
        assert "billable" in action, f"{r['rule_id']}: action must declare billable"
        assert isinstance(action["billable"], bool)
        # severity must be valid if present
        sev = action.get("severity")
        assert sev in _VALID_SEVERITY, f"{r['rule_id']}: bad severity {sev!r}"


# ── Provenance integrity tests ────────────────────────────────────────────

def test_treatment_gate_b_sources_exist(treatment_rules, clauses_frame, clauses_polars):
    """Every gate_b_sources cite must resolve to a SUT corpus clause_id."""
    missing_total = []
    for r in treatment_rules:
        for cid in _resolved_clause_ids(r.get("gate_b_sources") or [], clauses_polars):
            if cid not in clauses_frame:
                missing_total.append((r["rule_id"], cid))
    assert not missing_total, f"unknown clause IDs: {missing_total[:5]}"


def test_dental_gate_b_sources_exist(dental_rules, clauses_frame, clauses_polars):
    missing_total = []
    for r in dental_rules:
        for cid in _resolved_clause_ids(r.get("gate_b_sources") or [], clauses_polars):
            if cid not in clauses_frame:
                missing_total.append((r["rule_id"], cid))
    assert not missing_total, f"unknown clause IDs: {missing_total[:5]}"


def test_all_rules_have_provenance(treatment_rules, dental_rules):
    """Every rule must trace to ≥1 SUT clause (the audit-trail contract)."""
    for r in treatment_rules + dental_rules:
        srcs = r.get("gate_b_sources") or []
        assert len(srcs) >= 1, f"{r['rule_id']}: no gate_b_sources provenance"


# ── Section coverage tests ────────────────────────────────────────────────

def test_treatment_covers_expected_sections(treatment_rules):
    """Verify the major §2.4.4 treatment blocks are all covered."""
    sections = {r["sut_section"] for r in treatment_rules}
    expected_blocks = {
        "2.4.4.D-1",  # hemodiyaliz
        "2.4.4.İ-1",  # IVF
        "2.4.4.H",    # yoğun bakım
        "2.4.4.K",    # palyatif
        "2.4.4.F-2",  # fizik tedavi
        "2.4.4.G-2",  # moleküler/genetik
    }
    missing = expected_blocks - sections
    assert not missing, f"missing expected treatment blocks: {missing}"


def test_dental_covers_exclusion_rules(dental_rules):
    """Verify the core §2.4.1 exclusion rules are present."""
    ids = {r["rule_id"] for r in dental_rules}
    assert "2.4.1.(1).precious_metal_no_pay" in ids
    assert "2.4.1.(2).bone_implant_no_pay_default" in ids
    assert "2.4.1.(3).prosthesis_4yr_renewal_cap" in ids
    assert "2.4.1.(4a).orthodontics_over_18_no_pay" in ids


# ── Golden fixture round-trip ─────────────────────────────────────────────

def test_treatment_golden_matches_rules(treatment_rules):
    golden = json.loads((_GOLDEN_DIR / "treatment_pricing_2_4.json").read_text(encoding="utf-8"))
    rule_ids = {r["rule_id"] for r in treatment_rules}
    for case in golden["cases"]:
        assert case["expected_rule_id"] in rule_ids, (
            f"golden references unknown rule {case['expected_rule_id']}"
        )


def test_dental_golden_matches_rules(dental_rules):
    golden = json.loads((_GOLDEN_DIR / "dental_2_4_1.json").read_text(encoding="utf-8"))
    rule_ids = {r["rule_id"] for r in dental_rules}
    for case in golden["cases"]:
        assert case["expected_rule_id"] in rule_ids, (
            f"golden references unknown rule {case['expected_rule_id']}"
        )
