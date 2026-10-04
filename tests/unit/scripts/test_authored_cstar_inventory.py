"""Track E — authored C* inventory must never grow (Paket 1, subtask 1.4).

Every remaining authored C* cite is a reviewed exception. This test locks the
active inventory and the deferred source judgments so new opaque cites or
source assignments require an explicit review.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from scripts.sut.compile_rules import _PAYMENT_SESSION_MANIFEST_STUB
from scripts.sut.gate_b_wave_config import DRUG_INDICATION_WAVE_CLAUSE_KEYS
from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[3]
_RULE_SOURCES = _ROOT / "data" / "gazette" / "prose_rule_sources"
_DEFERRAL = _ROOT / "data" / "gazette" / "prose_rules" / "deferral_table.yaml"

_CSTAR = re.compile(r"^[CF]\d{6}$")


def _cstar_refs_in_gate_b_sources() -> set[str]:
    refs: set[str] = set()
    for path in sorted(_RULE_SOURCES.glob("**/*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for rule in payload.get("rules") or []:
            for src in rule.get("gate_b_sources") or []:
                text = str(src)
                if _CSTAR.fullmatch(text):
                    refs.add(text)
    return refs


def _cstar_refs_in_deferral() -> set[str]:
    payload = yaml.safe_load(_DEFERRAL.read_text(encoding="utf-8"))
    return {
        str(e.get("clause_id"))
        for e in payload.get("entries") or []
        if _CSTAR.fullmatch(str(e.get("clause_id") or ""))
    }


def _cstar_refs_in_sections() -> set[str]:
    refs: set[str] = set()
    for section in ALL_SECTIONS.values():
        for override in section.tier_a_overrides + section.tier_b_overrides:
            refs.update(c for c in override.clause_ids if _CSTAR.fullmatch(c))
        refs.update(c for c in section.superseded_ids if _CSTAR.fullmatch(c))
        for ids in section.force_include_ids.values():
            refs.update(c for c in ids if _CSTAR.fullmatch(c))
    return refs


def _cstar_refs_in_wave_config() -> set[str]:
    return {
        ref
        for keys in DRUG_INDICATION_WAVE_CLAUSE_KEYS.values()
        for ref in keys
        if _CSTAR.fullmatch(ref)
    }


def _cstar_refs_in_stub() -> set[str]:
    return {
        ref
        for ref in _PAYMENT_SESSION_MANIFEST_STUB.get("encoded_clause_keys") or []
        if _CSTAR.fullmatch(ref)
    }


def test_authored_cstar_inventory_is_frozen() -> None:
    per_surface = {
        "gate_b_sources": _cstar_refs_in_gate_b_sources(),
        "deferral": _cstar_refs_in_deferral(),
        "gate_b_sections": _cstar_refs_in_sections(),
        "wave_config": _cstar_refs_in_wave_config(),
        "payment_stub": _cstar_refs_in_stub(),
    }
    # Frozen at Paket 1 (2026-08-08): every C* here is a documented exception
    # (non-eligible prose/amendment/structural, or identical duplicate).
    # Updated 2026-08-12 (PR #66, MIH-8 gate verification): C007814 removed
    # (wrong clause — 4.4.1.(12) drug-price clause), replaced by C005778-C005785
    # (4.2.14.C ravulizumab PNH gates), C000349 (1.8.3.(2) copay cap) and
    # C001593 (2.6.1.B-4 ambulance cap note). All new cites verified present in
    # sut_clauses.parquet.
    expected = {
        # 2026-08-29: two duplicate YAML C003750 cites collapsed to one hashed
        # twin (4.2.1.C-5.(4)#4804adef) → 217 → 215.
        # 2026-10-02: prior clinical-source repair removed C007082/C007088;
        # enteral continuation C004140 is replaced by content-pinned prose:...99f29955.
        # 2026-10-04: two source-unsafe executable rows were withdrawn; 490
        # deferrals now use canonical keys, 149 opaque exceptions have source
        # pins, and 55 unchanged judgments await review outside active entries.
        "gate_b_sources": 206,
        "deferral": 149,
        "gate_b_sections": 30,
        "wave_config": 15,
        "payment_stub": 1,
    }
    for surface, refs in per_surface.items():
        assert len(refs) == expected[surface], (
            f"{surface} C* inventory moved: {len(refs)} != {expected[surface]} "
            f"(new cites need an explicit exception decision)"
        )
    assert not ({"C007082", "C007088"} & per_surface["gate_b_sources"])
    assert not ({"C005346", "C005348"} & per_surface["gate_b_sources"])
    total = sum(len(refs) for refs in per_surface.values())
    assert total == 401, f"total authored C* moved: {total}"


def test_deferral_cstar_pins_and_original_pending_judgments_are_frozen() -> None:
    payload = yaml.safe_load(_DEFERRAL.read_text(encoding="utf-8"))
    active = payload["entries"]
    pending = payload["review_pending_entries"]
    opaque = [entry for entry in active if entry.get("clause_id")]
    pin_fields = ("source_contract_sha256", "source_corpus_sha256")
    pinned = [entry for entry in active if any(field in entry for field in pin_fields)]
    assert len(active) == 1490
    assert len(opaque) == len(_cstar_refs_in_deferral()) == 149
    assert pinned == opaque, "Every active opaque deferral needs the paired source pins"
    corpus_hash = "40b2b7ebdb44c2483867d5413f7af3d97bb55c92d43d3a4be2737d80135425ec"
    for entry in opaque:
        assert _CSTAR.fullmatch(str(entry["clause_id"]))
        assert set(pin_fields) <= entry.keys()
        assert entry["source_corpus_sha256"] == corpus_hash
        assert re.fullmatch(r"[0-9a-f]{64}", entry["source_contract_sha256"])

    assert len(pending) == 55
    original_fields = {
        "clause_id", "clause_coordinate", "section_id", "status",
        "defer_themes", "defer_reason", "source_manifest",
    }
    assert all(set(entry) == original_fields and entry not in active for entry in pending)
    # Full original dictionaries, including their historical source identity and
    # authored status/themes/reason, are retained without a new body assignment.
    serialized = json.dumps(pending, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert hashlib.sha256(serialized.encode("utf-8")).hexdigest() == (
        "df5de7e889d97e7e745043a2a034f3a1b736ba5a98afee451db0d8eef3af49e8"
    )


def test_every_remaining_cstar_exists_in_parquet() -> None:
    """1.7 guard: any C* absent from the corpus must fail compile — this locks it."""
    import polars as pl

    clauses_path = _ROOT / "data" / "gazette" / "sut_clauses.parquet"
    if not clauses_path.exists():
        pytest.skip("sut_clauses.parquet missing")
    frame = pl.read_parquet(clauses_path)
    cids = set(frame["clause_id"].cast(pl.String).to_list())
    refs = (
        _cstar_refs_in_gate_b_sources()
        | _cstar_refs_in_deferral()
        | _cstar_refs_in_sections()
        | _cstar_refs_in_wave_config()
        | _cstar_refs_in_stub()
    )
    missing = sorted(c for c in refs if c not in cids)
    assert not missing, f"C* cites absent from sut_clauses.parquet: {missing[:10]}"


def test_eligible_cstars_are_identical_duplicates_only() -> None:
    """1.5 guard: freeze the eligible C* inventory after PR61 corpus remap.

    Both unique-content and identical-duplicate exception counts are frozen;
    new eligible opaque citations require an explicit decision. This is a
    technical source inventory, not a clinical payment-eligibility assertion.
    """
    import polars as pl

    from scripts.sut.prose.clause_identity import resolve_gate_b_ref_to_clause_ids
    from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides

    clauses_path = _ROOT / "data" / "gazette" / "sut_clauses.parquet"
    if not clauses_path.exists():
        pytest.skip("sut_clauses.parquet missing")
    frame = apply_clause_type_overrides(pl.read_parquet(clauses_path))
    by_id = {r["clause_id"]: r for r in frame.iter_rows(named=True)}

    refs = (
        _cstar_refs_in_gate_b_sources()
        | _cstar_refs_in_deferral()
        | _cstar_refs_in_sections()
        | _cstar_refs_in_wave_config()
        | _cstar_refs_in_stub()
    )
    eligible = []
    for cid in sorted(refs):
        row = by_id.get(cid)
        if row is None:
            continue
        if (
            row["clause_type"] in ("bent", "numbered_item", "fikra")
            and row["is_in_force"] is True
        ):
            eligible.append(cid)

    non_identical: list[str] = []
    identical = 0
    for cid in eligible:
        row = by_id[cid]
        key = f"{row['clause_coordinate']}#{row['content_hash']}"
        ids = resolve_gate_b_ref_to_clause_ids(
            key, frame, in_force_only=True, encode_eligible_only=True
        )
        assert cid in ids, f"eligible opaque cite lost its source body: {cid} ({key})"
        if ids == [cid]:
            non_identical.append(cid)
        else:
            identical += 1

    # Frozen after PR61 remap (2026-08-09): 232 unique-content eligible C*
    # (non-identical, legitimately keyed by clause_id) + 31 identical duplicates.
    # Updated 2026-08-12 (PR #66, MIH-8 gate verification): +3 unique-content
    # eligible (C000349, C005778, C001593); C007814 removed (was an identical
    # duplicate — the wrong 4.4.1.(12) clause) so identical dropped 31 -> 30.
    # Updated 2026-08-29: positional C* id shift left remaining eligible C*
    # on distinct in-force fikra/bent rows (249 unique-content + 15 identical).
    # 2026-10-04: the 490 canonical / 149 pinned / 55 pending deferral migration
    # removes 235 deferral-only eligible old C slots from this opaque inventory.
    # The reviewed live source/config exceptions retain 27 unique + 2 identical.
    assert len(non_identical) == 27, (
        f"unique-content eligible C* inventory moved: {len(non_identical)} != 27"
    )
    assert identical == 2, f"eligible identical-duplicate C* inventory moved: {identical}"
