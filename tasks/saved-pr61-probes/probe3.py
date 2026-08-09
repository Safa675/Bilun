"""Master probe v3: replicate each failing test's exact computation and print actual goldens."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import polars as pl
from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
from scripts.sut.rule_sources import load_legacy_drug_batch, load_drug_sections_rules

_CLAUSES = ROOT / "data/gazette/sut_clauses.parquet"
RESOLVE = pl.read_parquet(_CLAUSES)

def man(section_id, rules, effective_date="2026-06-27"):
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[section_id])
    m = build_manifest(frame, rules, ALL_SECTIONS[section_id], resolve_clauses=RESOLVE, effective_date=effective_date)
    return frame, m

# ---------------- 4210
R4210 = load_drug_sections_rules(["4.2.10.A","4.2.10.A-3","4.2.10.A-4","4.2.10.B-2","4.2.10.B-3","4.2.10.C-1","4.2.10.C-2","4.2.10.C-3","4.2.10.D-2","4.2.10.Ç-2"])
frame, m = man("4210", R4210)
tier_a = set(frame.filter(pl.col("encode_tier")=="A")["clause_id"].to_list())
print("4210 tier_a:", sorted(tier_a))
print("4210 encoded:", sorted(set(m["encoded_clause_ids"])))
print("4210 tier_a_pending:", m["tier_a_pending_count"], "tier_b_pending:", m["tier_b_pending_count"])
print("4210 height:", frame.height, "tierC:", m["tier_c_deferred_count"])
from scripts.sut.prose.gate_b_audit import default_scan_promotions
promo = default_scan_promotions(frame, encoded_clause_ids=set(m["encoded_clause_ids"]))
print("4210 promotions:", [(p["clause_id"], p["section_id"], p["reasons"]) for p in promo])

# ============ 4234 ============
R4234 = load_legacy_drug_batch("drug_indication_4234_batch_rules.py:BATCH_MS4234_RULES")
frame, m = man("4234", R4234)
tiers_4234 = sorted(frame.filter(pl.col("encode_tier")=="A")["clause_id"].to_list())
print("4234 tier_a actual:", tiers_4234)
print("4234 encoded actual:", sorted(m["encoded_clause_ids"]))
print("4234 tier_a_pending:", m["tier_a_pending_count"], "tier_b_pending:", m["tier_b_pending_count"])
print("4234 height:", frame.height, "tierC:", m["tier_c_deferred_count"], "rules_in_json:", m["rules_in_json"], "section_total:", m["section_clause_total"])
on_disk_4234 = json.loads((ROOT/"data/gazette/prose_manifests/L4.2_drug_indication_4234_manifest.json").read_text(encoding="utf-8"))
print("4234 on-disk encoded count:", on_disk_4234.get("encoded_clause_count"), "ids:", sorted(on_disk_4234.get("encoded_clause_ids") or []))

# ============ 4206 exact (like test)
R4206 = [
    *load_legacy_drug_batch("drug_indication_4206_batch_rules.py:BATCH_A6_RULES"),
    *load_legacy_drug_batch("drug_indication_4206_a2_batch_rules.py:BATCH_A2_RULES"),
]
frame, m = man("4206", R4206)
tiers_4206 = sorted(frame.filter(pl.col("encode_tier")=="A")["clause_id"].to_list())
print("4206 tier A:", tiers_4206)
print("4206 encoded:", sorted(m["encoded_clause_ids"]))
print("4206 tier_a_pending:", m["tier_a_pending_count"], "tier_b_pending:", m["tier_b_pending_count"], "tierC:", m["tier_c_deferred_count"], "rules:", m["rules_in_json"])

# ============ 4235_4237 exact
R4235 = load_legacy_drug_batch("drug_indication_4235_4237_batch_rules.py:BATCH_A5_RULES")
frame, m = man("4235_4237", R4235)
tier = {row["encode_tier"]: row["len"] for row in frame.group_by("encode_tier").len().iter_rows(named=True)}
s4235 = frame.filter(pl.col("section_id").str.starts_with("4.2.35"))
s4237 = frame.filter(pl.col("section_id").str.starts_with("4.2.37"))
s4235_t = {row["encode_tier"]: row["len"] for row in s4235.group_by("encode_tier").len().iter_rows(named=True)}
s4237_t = {row["encode_tier"]: row["len"] for row in s4237.group_by("encode_tier").len().iter_rows(named=True)}
print("4235_4237 tiers:", tier)
print("4235 tiers:", s4235_t, "| 4237 tiers:", s4237_t)
print("4235 encoded:", sorted(m["encoded_clause_ids"]))
print("4235 section_4.2.35_clause_total:", m.get("section_4.2.35_clause_total"), "| 4.2.37:", m.get("section_4.2.37_clause_total"))
print("4235 tier_a_pending:", m["tier_a_pending_count"], "tier_b_pending:", m["tier_b_pending_count"], "tierC:", m["tier_c_deferred_count"])
on_disk_4235 = json.loads((ROOT/"data/gazette/prose_manifests/L4.2_drug_indication_4235_4237_manifest.json").read_text(encoding="utf-8"))
print("4235 on-disk encoded:", sorted(on_disk_4235.get("encoded_clause_ids") or []))

# ============ 4238 exact
R4238 = load_legacy_drug_batch("drug_indication_4238_batch_rules.py:BATCH_A5_RULES")
frame, m = man("4238", R4238)
on_disk_4238 = json.loads((ROOT/"data/gazette/prose_manifests/L4.2_drug_indication_4238_manifest.json").read_text(encoding="utf-8"))
print("4238 encoded:", sorted(m["encoded_clause_ids"]))
print("4238 on-disk encoded:", sorted(on_disk_4238.get("encoded_clause_ids") or []))
print("4238 tierC fresh:", m["tier_c_deferred_count"], "on-disk:", on_disk_4238.get("tier_c_deferred_count"), "tier_b_pending:", m["tier_b_pending_count"])

# ============ 4215 exact
R = load_legacy_drug_batch("BATCH_A15_RULES")
frame, m = man("4215", R)
print("4215 encoded:", sorted(m["encoded_clause_ids"]))
print("4215 tierC:", m["tier_c_deferred_count"], "tier_a_pending:", m["tier_a_pending_count"], "rules:", m["rules_in_json"])
on_disk = json.loads((ROOT/"data/gazette/prose_manifests/L4.2_drug_indication_4215_manifest.json").read_text(encoding="utf-8"))
print("4215 on-disk encoded:", sorted(on_disk.get("encoded_clause_ids") or []))

# ============ 4224 exact
R = load_legacy_drug_batch("BATCH_A24_RULES")
frame, m = man("4224", R)
print("4224 encoded:", sorted(m["encoded_clause_ids"]))
print("4224 tierC:", m["tier_c_deferred_count"], "tier_a_pending:", m["tier_a_pending_count"], "rules:", m["rules_in_json"])

# ============ 4213 oral switch
frame = export_candidates(_CLAUSES, ALL_SECTIONS["4213"])
print("4213 has C004584:", frame.filter(pl.col("clause_id")=="C004584").select(["encode_tier","encode_priority"]).to_dicts(), "C004593:", frame.filter(pl.col("clause_id")=="C004593").select(["encode_tier","encode_priority"]).to_dicts())
oral = frame.filter(pl.col("clause_id").is_in(["C004584","C004593"]))
print("4213 oral rows:", [(r["clause_id"], r["encode_tier"], r["encode_priority"]) for r in oral.iter_rows(named=True)])
print("4213 count in-force:", len(set(frame.filter(pl.col("is_in_force")==True)["clause_id"].to_list())))

# ============ 4201 on-disk manifest
m4201 = json.loads((ROOT/"data/gazette/prose_manifests/L4.2_drug_indication_4201_manifest.json").read_text(encoding="utf-8"))
print("4201 on-disk:", {k: m420.get(k) for k in ("encoded_clause_count","tier_a_pending_count","tier_b_pending_count","section_clause_total","rules_in_json")})

# ============ copay tokens
from scripts.sut.prose.clause_identity import resolve_gate_b_sources_to_clause_ids
payload = json.loads((ROOT/"data/gazette/prose_rules/copay_general_1_8.json").read_text(encoding="utf-8"))
for rule in payload.get("rules") or []:
    if str(rule.get("rule_id")) == "1.8.2.(1)":
        ids = sorted(resolve_gate_b_sources_to_clause_ids(rule.get("gate_b_sources") or [], RESOLVE, in_force_only=True, encode_eligible_only=False, allow_ambiguous=True))
        print("1.8.2.(1) ids:", ids)
    if str(rule.get("rule_id")) == "1.8.5.(10).organ_nakli":
        ids = sorted(resolve_gate_b_sources_to_clause_ids(rule.get("gate_b_sources") or [], RESOLVE, in_force_only=True, encode_eligible_only=False, allow_ambiguous=True))
        print("1.8.5.(10) ids:", ids)

# ============ track_e id C002684?
from src.bilun.domain.sut import rules_catalog as rc
rc.reset_cache()
try:
    by_id = rc.get_clause("C002684")
    print("C002684:", by_id)
except Exception as e:
    print("C002684 ERROR:", e)
for cid in ("C000006", "C000001"):
    r = rc.get_clause(cid)
    if r:
        print(cid, "->", r.get("clause_coordinate"), "key:", r.get("clause_key"))
    else:
        print(cid, "MISSING")

# ============ inventory counts
import yaml, re
CSTAR = re.compile(r"^[CF]\d{6}$")
RULE = ROOT / "data/gazette/prose_rule_sources"
DEF = ROOT / "data/gazette/prose_rules" / "deferral_table.yaml"
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
    from scripts.sut.gate_b_wave_config import DRUG_INDICATION_WAVE_CLAUSE_KEYS
    from scripts.sut.compile_rules import _PAYMENT_SESSION_MANIFEST_STUB
    s=set()
    for section in ALL_SECTIONS.values():
        for ov in section.tier_a_overrides + section.tier_b_overrides:
            s.update(c for c in ov.clause_ids if CSTAR.fullmatch(c))
        s.update(c for c in section.superseded_ids if CSTAR.fullmatch(c))
        for ids in section.force_include_ids.values(): s.update(c for c in ids if CSTAR.fullmatch(c))
    return s
sources = refs_sources(); defer = refs_defer(); sections = refs_sections()
wave = {ref for keys in DRUG_INDICATION_WAVE_CLAUSE_KEYS.values() for ref in keys if CSTAR.fullmatch(ref)}
stub = {ref for ref in _PAYMENT_SESSION_MANIFEST_STUB.get("encoded_clause_keys") or [] if CSTAR.fullmatch(ref)}
print("inv:", len(sources), len(defer), len(sections), len(wave), len(stub), "total:", len(sources)+len(defer)+len(sections)+len(wave)+len(stub))

# eligible identical / non-identical
from scripts.sut.prose.clause_identity import resolve_gate_g_ref_to_clause_ids as RREF
print("RREF has resolve_gate_g? ", hasattr(sys.modules["scripts.sut.prose.clause_identity"], "resolve_gate_g_ref_to_clause_ids"))