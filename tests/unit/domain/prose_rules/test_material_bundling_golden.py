"""Golden Gate B fixtures for material bundling prose (Phase 3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.bilun.domain.prose_rules.material_bundling import check_material_bundling_prose

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[4]
_GOLDEN_PATH = _ROOT / "data/gazette/prose_rules/golden/material_bundling_gate_b.json"
_PROSE_JSON = _ROOT / "data/gazette/prose_rules/material_bundling_prose.json"


def _load_golden_cases() -> list[dict]:
    payload = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    return list(payload["cases"])


@pytest.mark.parametrize(
    "case",
    _load_golden_cases(),
    ids=lambda c: f"{c['expected_rule_id']}:{c['material']['code']}",
)
def test_gate_b_golden_expected_rule(case: dict) -> None:
    hits = check_material_bundling_prose([case["material"]])
    assert hits, f"no hit for clause {case['clause_id']}"
    assert hits[0]["rule_id"] == case["expected_rule_id"]


def test_prose_json_required_when_registry_implemented() -> None:
    from scripts.sut.prose.rule_registry import RULE_BY_ID

    entry = RULE_BY_ID["material_bundling_prose"]
    assert entry.coverage_status == "implemented"
    assert _PROSE_JSON.is_file()
    payload = json.loads(_PROSE_JSON.read_text(encoding="utf-8"))
    assert len(payload.get("rules", [])) >= len(_load_golden_cases())


#: Message cites that are deliberately wider than the rule's own gate_b_sources.
#: In-force §3.1.2(19) (C002807) says inpatient external supply follows the 5th
#: and 6th paragraphs of §3.1.1, so the facility-supply rule keeps both labels.
#: The patient-charge rule's text is in-force §3.1.1(6) (C002744: patient buys a
#: non-reimbursed inpatient material, invoice paid to the patient and offset), so
#: its message says (6). Its gate_b_sources still say (7), which in force is the
#: EK-3/B clause (C002745); re-anchoring it is a pending owner decision because
#: C002744 has no deontic signal, so it is outside the L1.4 manifest clause frame
#: and the re-anchor would turn C002745 into tier_c_deferred and drop the finding's
#: clause_ref. Remove this entry when gate_b_sources is moved to (6).
_EXTRA_MESSAGE_CITES: dict[str, set[str]] = {
    "3.1.1.(6).inpatient_facility_supply_violation": {"3.1.1.(6)"},
    "3.1.1.(7).non_reimbursed_inpatient_patient_charge": {"3.1.1.(6)"},
}


def test_message_paragraph_cites_follow_gate_b_sources() -> None:
    """A message's §3.1.1 paragraph cite must name a paragraph the rule is sourced on.

    A corpus renumbering left second, old-numbering labels in several messages
    ("(12)/(14)", "(16)/(18)", "(8)/(19)", ...). Each one pointed at a paragraph
    that is no longer in force or at a different clause than the finding's own
    clause_ref, so the cite shown next to the finding contradicted its source.
    """
    import re

    # "§3.1.1(12)/(14)" cites two paragraphs: read the whole slash-separated run.
    cite = re.compile(r"§3\.1\.1((?:\(\d+\))(?:/\(\d+\))*)")
    payload = json.loads(_PROSE_JSON.read_text(encoding="utf-8"))
    stray: list[str] = []
    for rule in payload["rules"]:
        rule_id = rule["rule_id"]
        cited = {
            f"3.1.1.({n})"
            for run in cite.findall(rule["action"].get("message_tr") or "")
            for n in re.findall(r"\d+", run)
        }
        allowed = set(rule.get("gate_b_sources") or []) | _EXTRA_MESSAGE_CITES.get(rule_id, set())
        if cited - allowed:
            stray.append(f"{rule_id}: cites {sorted(cited - allowed)}, sources {sorted(allowed)}")
    assert not stray, "message cites a paragraph outside the rule's sources:\n" + "\n".join(stray)


def test_golden_clause_ids_follow_rule_gate_b_sources() -> None:
    """clause_id is provenance only (the evaluator test above never reads it).

    Keep it equal to an in-force clause that the rule's gate_b_sources resolves
    to, so a corpus renumbering cannot silently strand the golden again.
    """
    import polars as pl

    from scripts.sut.prose.clause_identity import resolve_gate_b_ref_to_clause_ids
    from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides

    frame = apply_clause_type_overrides(
        pl.read_parquet(_ROOT / "data/gazette/sut_clauses.parquet")
    )
    rules = {
        rule["rule_id"]: rule
        for rule in json.loads(_PROSE_JSON.read_text(encoding="utf-8"))["rules"]
    }
    stale: list[str] = []
    for case in _load_golden_cases():
        refs = rules[case["expected_rule_id"]].get("gate_b_sources") or []
        allowed = {
            cid
            for ref in refs
            for cid in resolve_gate_b_ref_to_clause_ids(
                str(ref), frame, in_force_only=True, encode_eligible_only=False
            )
        }
        if case["clause_id"] not in allowed:
            stale.append(
                f'{case["expected_rule_id"]}: {case["clause_id"]} not in {sorted(allowed)}'
            )
    assert not stale, "golden clause_id is not an in-force source of its rule:\n" + "\n".join(stale)
