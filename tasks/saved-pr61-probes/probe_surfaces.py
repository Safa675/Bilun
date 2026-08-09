"""Probe: which surfaces hold the non_identical eligible C*; also corpus coverage of them."""
import re, yaml, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import polars as pl
from scripts.sut.compile_rules import _PAYMENT_SESSION_MANIFEST_STUB
from scripts.sut.gate_b_wave_config import DRUG_INDICATION_WAVE_CLAUSE_KEYS
from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
from scripts.sut.prose.clause_identity import resolve_gate_b_ref_to_clause_ids
from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides

_RULE_SOURCES = ROOT / "data/gazette/prose_rule_sources"
_DEFERRAL = ROOT / "data/gazette/prose_rules/deferral_table.yaml"
_CSTAR = re.compile(r"^[CF]\d{6}$")


def _cstar_refs_in_gate_b_sources():
    refs = set()
    for path in sorted(_RULE_SOURCES.glob("**/*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for rule in payload.get("rules") or []:
            for src in rule.get("gate_b_sources") or []:
                if _CSTAR.fullmatch(str(src)):
                    refs.add(str(src))
    return refs


def _cstar_refs_in_deferral():
    payload = yaml.safe_load(_DEFERRAL.read_text(encoding="utf-8"))
    return {str(e.get("clause_id")) for e in payload.get("entries") or [] if _CSTAR.fullmatch(str(e.get("clause_id") or ""))}


def _cstar_refs_in_sections():
    refs = set()
    for section in ALL_SECTIONS.values():
        for override in section.tier_a_overrides + section.tier_b_overrides:
            refs.update(c for c in override.clause_ids if _CSTAR.fullmatch(c))
        refs.update(c for c in section.superseded_ids if _CSTAR.fullmatch(c))
        for ids in section.force_include_ids.values():
            refs.update(c for c in ids if _CSTAR.fullmatch(c))
    return refs


def _cstar_refs_in_wave_config():
    return {ref for keys in DRUG_INDICATION_WAVE_CLAUSE_KEYS.values() for ref in keys if _CSTAR.fullmatch(ref)}


def _cstar_refs_in_stub():
    return {ref for ref in _PAYMENT_SESSION_MANIFEST_STUB.get("encoded_clause_keys") or [] if _CSTAR.fullmatch(ref)}


per_surface = {
    "gate_b_sources": _cstar_refs_in_gate_b_sources(),
    "deferral": _cstar_refs_in_deferral(),
    "gate_b_sections": _cstar_refs_in_sections(),
    "wave_config": _cstar_refs_in_wave_config(),
    "payment_stub": _cstar_refs_in_stub(),
}

frame = apply_clause_type_overrides(pl.read_parquet(ROOT / "data/gazette/sut_clauses.parquet"))
by_id = {r["clause_id"]: r for r in frame.iter_rows(named=True)}

non_identical_by_surface = {}
for surface, refs in per_surface.items():
    bad = []
    for cid in sorted(refs):
        row = by_id.get(cid)
        if row is None:
            continue
        if row["clause_type"] not in ("bent", "numbered_item", "fikra") or row["is_in_force"] is not True:
            continue
        key = f"{row['clause_coordinate']}#{row['content_hash']}"
        try:
            ids = resolve_gate_b_ref_to_clause_ids(key, frame, in_force_only=True, encode_eligible_only=True)
        except Exception:
            bad.append(cid)
            continue
        if ids == [cid]:
            bad.append(cid)
    non_identical_by_surface[surface] = bad
    print(f"{surface}: non_identical eligible = {len(bad)}")

# Where does each non_identical C* live (union vs exclusive)?
union_all = set().union(*per_surface.values())
frame_eligible = {cid for cid in union_all if (r := by_id.get(cid)) and r["clause_type"] in ("bent", "numbered_item", "fikra") and r["is_in_force"] is True}
print("\nEligible C* count total:", len(frame_eligible))
