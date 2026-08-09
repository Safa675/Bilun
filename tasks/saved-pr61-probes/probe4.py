"""Probe 4: inventory eligible counts + copay + track_e + 4213 in-force."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import polars as pl
import yaml

_CLAUSES = ROOT / "data/gazette/sut_clauses.parquet"
RULE = ROOT / "data/gazette/prose_rule_sources"
DEF = ROOT / "data/gazette/prose_rules" / "deferral_table.yaml"

CSTAR = re.compile(r"^[CF]\d{6}$")

def refs_sources():
    s = set()
    for p in sorted(RULE.glob("**/*.yaml")):
        try: payload = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception: continue
        for rule in payload.get("rules") or []:
            for src in rule.get("gate_b_sources") or []:
                if CSTAR.fullmatch(str(src)): s.add(str(src))
    return s

def refs_defer():
    payload = yaml.safe_load(DEF.read_text(encoding="utf-8"))
    return {str(e.get("clause_id")) for e in payload.get("entries") or [] if CSTAR.fullmatch(str(e.get("clause_id") or ""))}

def refs_sections():
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
    s=set()
    for section in ALL_SECTIONS.values():
        for ov in section.tier_a_overrides + section.tier_b_overrides:
            s.update(c for c in ov.clause_ids if CSTAR.fullmatch(c))
        s.update(c for c in section.superseded_ids if CSTAR.fullmatch(c))
        for ids in section.force_include_ids.values(): s.update(c for c in ids if CSTAR.fullmatch(c))
    return s

sources = refs_sources(); defer = refs_defer(); sections = refs_sections()
from scripts.sut.gate_b_wave_config import DRUG_INDICATION_WAVE_CLAUSE_KEYS
from scripts.sut.compile_rules import _PAYMENT_SESSION_MANIFEST_STUB
wave = {ref for keys in DRUG_INDICATION_WAVE_CLAUSE_KEYS.values() for ref in keys if CSTAR.fullmatch(ref)}
stub = {ref for ref in _PAYMENT_SESSION_MANIFEST_STUB.get("encoded_clause_keys") or [] if CSTAR.fullmatch(ref)}
print("inv sizes:", len(sources), len(defer), len(sections), len(wave), len(stub), "total:", len(sources)+len(defer)+len(sections)+len(wave)+len(stub))

# eligible identical / non-identical (mirrors test)
from scripts.sut.prose.clause_identity import resolve_gate_b_ref_to_clause_ids
from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides
frame = apply_clause_type_overrides(pl.read_parquet(_CLAUSES))
by_id = {r["clause_id"]: r for r in frame.iter_rows(named=True)}
refs = sources | defer | sections | wave | stub
eligible = []
for cid in sorted(refs):
    row = by_id.get(cid)
    if row is None: continue
    if row["clause_type"] in ("bent","numbered_item","fikra") and row["is_in_force"] is True:
        eligible.append(cid)
print("eligible total:", len(eligible))
non_identical = []; identical = 0
for cid in eligible:
    row = by_id[cid]
    key = f"{row['clause_coordinate']}#{row['content_hash']}"
    try:
        ids = resolve_gate_b_ref_to_clause_ids(key, frame, in_force_only=True, encode_eligible_only=True)
    except Exception:
        non_identical.append(cid); continue
    if ids == [cid]: non_identical.append(cid)
    else: identical += 1
print("identical:", identical, "non_identical:", len(non_identical))
print("non_identical sample:", non_identical[:15])

# copay
from scripts.sut.prose.clause_identity import resolve_gate_b_sources_to_clause_ids
RESOLVE = pl.read_parquet(_CLAUSES)
payload = json.loads((ROOT/"data/gazette/prose_rules/copay_general_1_8.json").read_text(encoding="utf-8"))
for rule in payload.get("rules") or []:
    rid = str(rule.get("rule_id") or "")
    if rid in ("1.8.2.(1)", "1.8.5.(10).organ_nakli"):
        ids = sorted(resolve_gate_b_sources_to_clause_ids(rule.get("gate_b_sources") or [], RESOLVE, in_force_only=True, encode_eligible_only=False, allow_ambiguous=True))
        print(rid, "->", ids)

# track_e
from src.bilun.domain.sut import rules_catalog as rc
rc.reset_cache()
by_id = rc.get_clause("C002684")
print("C002684 exists:", by_id is not None)
for cid in ("C000006","C000001"):
    r = rc.get_clause(cid)
    if r: print(cid, "->", r.get("clause_coordinate"), "key:", r.get("clause_key"))
    else: print(cid, "MISSING")

# 4201 on-disk
m4201 = json.loads((ROOT/"data/gazette/prose_manifests/L4.2_drug_indication_4201_manifest.json").read_text(encoding="utf-8"))
print("4201 on-disk:", {k: m4201.get(k) for k in ("encoded_clause_count","tier_a_pending_count","tier_b_pending_count","section_clause_total","rules_in_json","section_id")})

# specialty C003117 detail
cov = pl.read_parquet(ROOT/"data/gazette/sut_clause_coverage.parquet")
if cov.filter(pl.col("clause_id")=="C003117").height:
    print("C003117 coverage:", cov.filter(pl.col("clause_id")=="C003117").select(["section_id","primary_rule_id","coverage_status","has_rule_encoding","has_algorithmic_gap","clause_type"]).to_dicts())
from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides
f2 = apply_clause_type_overrides(pl.read_parquet(_CLAUSES))
print("C003117 row:", f2.filter(pl.col("clause_id")=="C003117").select(["clause_type","is_in_force","section_id"]).to_dicts())
print("C000373 row:", f2.filter(pl.col("clause_id")=="C000373").select(["clause_type","is_in_force","section_id"]).to_dicts())