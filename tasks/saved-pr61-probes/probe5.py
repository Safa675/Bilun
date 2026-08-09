"""Probe 5: remaining details (per-surface origin, copay manifest ids, 4234 artifacts, 4238 date, oral switch)."""
import json, re, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import polars as pl
import yaml

_CLAUSES = ROOT / "data/gazette/sut_clauses.parquet"
RULE = ROOT / "data/gazette/prose_rule_sources"
DEF = ROOT / "data/gazette/prose_rules" / "deferral_table.yaml"
CSTAR = re.compile(r"^[CF]\d{6}$")

from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
from scripts.sut.gate_b_wave_config import DRUG_INDICATION_WAVE_CLAUSE_KEYS
from scripts.sut.compile_rules import _PAYMENT_SESSION_MANIFEST_STUB

def refs_sources():
    s=set()
    for p in sorted(RULE.glob("**/*.yaml")):
        try: payload=yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception: continue
        for rule in payload.get("rules") or []:
            for src in rule.get("gate_b_sources") or []:
                if CSTAR.fullmatch(str(src)): s.add(str(src))
    return s
def refs_defer():
    payload=yaml.safe_load(DEF.read_text(encoding="utf-8"))
    return {str(e.get("clause_id")) for e in payload.get("entries") or [] if CSTAR.fullmatch(str(e.get("clause_id") or ""))}
def refs_sections():
    s=set()
    for section in ALL_SECTIONS.values():
        for ov in section.tier_a_overrides+section.tier_b_overrides: s.update(c for c in ov.clause_ids if CSTAR.fullmatch(c))
        s.update(c for c in section.superseded_ids if CSTAR.fullmatch(c))
        for ids in section.force_include_ids.values(): s.update(c for c in ids if CSTAR.fullmatch(c))
    return s
sources=refs_sources(); defer=refs_defer(); sections=refs_sections()
wave={ref for keys in DRUG_INDICATION_WAVE_CLAUSE_KEYS.values() for ref in keys if CSTAR.fullmatch(ref)}
stub={ref for ref in _PAYMENT_SESSION_MANIFEST_STUB.get("encoded_clause_keys") or [] if CSTAR.fullmatch(ref)}

from scripts.sut.prose.clause_identity import resolve_gate_b_ref_to_clause_ids
from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides
frame=apply_clause_type_overrides(pl.read_parquet(_CLAUSES))
by_id={r["clause_id"]: r for r in frame.iter_rows(named=True)}
refs=sources|defer|sections|wave|stub
eligible=[c for c in sorted(refs) if by_id.get(c) and by_id[c]["clause_type"] in ("bent","numbered_item","fikra") and by_id[c]["is_in_force"] is True]
non_identical=[]
for cid in eligible:
    row=by_id[cid]; key=f"{row['clause_coordinate']}#{row['content_hash']}"
    try: ids=resolve_gate_b_ref_to_clause_ids(key, frame, in_force_only=True, encode_eligible_only=True)
    except Exception: non_identical.append(cid); continue
    if ids==[cid]: non_identical.append(cid)
non_identical=set(non_identical)
print("non_identical total:", len(non_identical))
print("  subset of deferral:", non_identical <= defer, "| in deferral:", len(non_identical & defer))
print("  outside deferral:", sorted(non_identical - defer)[:20])

# copay manifest details (fresh write)
from scripts.sut.prose.gate_b_generic import write_artifacts
from scripts.sut.prose.gate_b_sections import SECTION_COPAY_18
with tempfile.TemporaryDirectory() as td:
    manifest_path = Path(td)/"manifest.json"
    write_artifacts(clauses_path=_CLAUSES, section=SECTION_COPAY_18, effective_date="2026-08-09",
                    rules_path=ROOT/"data/gazette/prose_rules/copay_general_1_8.json",
                    manifest_path=manifest_path, write_corpus=False)
    m=json.loads(manifest_path.read_text(encoding="utf-8"))
    enc=set(m["encoded_clause_ids"])
    print("copay encoded:", sorted(enc))
    for cid in ("C000364","C000361","C000326","C000362","C000355","C000378","C000365","C000379"):
        print("  copay", cid, "encoded?", cid in enc)
    ct=m.get("compositor_clause_traces") or {}
    print("  occupational:", ct.get("copay_exemption_occupational"))
    print("  patient_status:", ct.get("copay_exemption_patient_status"))
    print("  visit_type:", ct.get("copay_exemption_visit_type"))
    print("  rules_in_json:", m.get("rules_in_json"))

# 4234 full-rules artifacts (fresh write)
with tempfile.TemporaryDirectory() as td:
    mp=Path(td)/"m.json"
    write_artifacts(clauses_path=_CLAUSES, section=ALL_SECTIONS["4234"],
                    effective_date="2026-06-27", rules_path=ROOT/"data/gazette/prose_rules/drug_indication_prose.json",
                    manifest_path=mp, write_corpus=False)
    m=json.loads(mp.read_text(encoding="utf-8"))
    print("4234 fresh-full encoded count:", m["encoded_clause_count"], "ids:", sorted(m["encoded_clause_ids"]))
    print("4234 fresh-full section_total:", m["section_clause_total"], "tier_a_pending:", m["tier_a_pending_count"], "tierC:", m.get("tier_c_deferred_count"))

# 4238 on-disk date + ids
m4238=json.loads((ROOT/"data/gazette/prose_manifests/L4.2_drug_indication_4238_manifest.json").read_text(encoding="utf-8"))
print("4238 on-disk eff date:", m4238.get("effective_date"), "encoded:", m4238.get("encoded_clause_ids"))

# 4201 live artifacts (fresh write using rules_path like test)
with tempfile.TemporaryDirectory() as td:
    manifest_path=Path(td)/"m.json"
    write_artifacts(section=ALL_SECTIONS["4201"], clauses_path=_CLAUSES,
                    rules_path=ROOT/"data/gazette/prose_rules/drug_indication_prose.json",
                    corpus_csv=Path(td)/"c.csv", manifest_path=manifest_path,
                    effective_date="2026-06-27", write_corpus=True)
    m=json.loads(manifest_path.read_text(encoding="utf-8"))
    print("4201 fresh:", {k: m.get(k) for k in ("encoded_clause_count","tier_a_pending_count","tier_b_pending_count","section_clause_total","rules_in_json")})
    c=pl.read_csv(Path(td)/"c.csv")
    print("4201 corpus height:", c.height)

# oral switch: search section 4.2.13 rows with "oral" or switch-like (wave refs?)
frame13 = pl.read_parquet(_CLAUSES).filter(pl.col("section_id").str.starts_with("4.2.13."))
rows = frame13.filter(pl.col("text_tr").str.to_lowercase().str.contains("örneği|günlük|toplam|de") | pl.col("clause_coordinate").str.contains("A-5|A-6|A-7"))
for r in rows.sort("clause_coordinate").iter_rows(named=True):
    print("4213 candidate:", r["clause_id"], r["clause_coordinate"], r["text_tr"][:60])
# old two ids in corpus?
raw = pl.read_parquet(_CLAUSES)
for cid in ("C004584","C004593"):
    rr = raw.filter(pl.col("clause_id")==cid)
    print(cid, "in raw:", rr.height, rr.select(["clause_coordinate","text_tr"]).to_dicts()[:1])