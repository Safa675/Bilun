"""Probe 2: actual values for remaining failing gate_b tests."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import polars as pl

_REPO = ROOT
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"

from scripts.sut.prose.gate_b_generic import export_candidates, build_manifest, write_artifacts
from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
from scripts.sut.rule_sources import load_legacy_drug_batch

def show(section_id):
    print("=" * 70)
    print(section_id)
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[section_id])
    print("height:", frame.height)

# ---------------- 4206
show("4206")
from scripts.sut.rule_sources import load_legacy_drug_batch as llb
rules_4206 = [
    *llb("drug_indication_4206_batch_rules.py:BATCH_A6_RULES"),
    *llb("drug_indication_4206_a2_batch_rules.py:BATCH_A2_RULES"),
]
frame = export_candidates(_CLAUSES, ALL_SECTIONS["4206"])
manifest = build_manifest(frame, rules_4206, ALL_SECTIONS["4206"], resolve_clauses=pl.read_parquet(_CLAUSES), effective_date="2026-06-27")
print("4206 encoded:", sorted(set(manifest["encoded_clause_ids"])))
print("4206 tier A:", sorted(set(frame.filter(pl.col("encode_tier") == "A")["clause_id"].to_list())))
print("4206 tier_c_deferred:", manifest["tier_c_deferred_count"], "| tier_a_pending:", manifest["tier_a_pending_count"], "| tier_b_pending:", manifest["tier_b_pending_count"])
print("4206 on-disk manifest encoded:", sorted(set(json.loads((_REPO/"data/gazette/prose_manifests/L4.2_drug_indication_4206_manifest.json").read_text(encoding="utf-8")).get("encoded_clause_ids") or [])))

# ---------------- 4215
show("4215")
batch_4215 = llb("BATCH_A15_RULES")
frame = export_candidates(_CLAUSES, ALL_SECTIONS["4215"])
manifest = build_manifest(frame, batch_4215, ALL_SECTIONS["4215"], resolve_clauses=pl.read_parquet(_CLAUSES), effective_date="2026-06-27")
print("4215 encoded:", sorted(set(manifest["encoded_clause_ids"])))
print("4215 tier_c_deferred:", manifest["tier_c_deferred_count"], "| tier_a_pending:", manifest["tier_a_pending_count"], "| rules_in_json:", manifest["rules_in_json"])

# ---------------- 4235_4237
show("4235_4237")
batch_a5 = llb("drug_indication_4235_4237_batch_rules.py:BATCH_A5_RULES")
frame = export_candidates(_CLAUSES, ALL_SECTIONS["4235_4237"])
manifest = build_manifest(frame, batch_a5, ALL_SECTIONS["4235_4237"], resolve_clauses=pl.read_parquet(_CLAUSES), effective_date="2026-06-27")
tier = frame.group_by("encode_tier").len().sort("encode_tier")
print("4235_4237 counts:", {row["encode_tier"]: row["len"] for row in tier.iter_rows(named=True)})
s4235 = frame.filter(pl.col("section_id").str.starts_with("4.2.35"))
print("  s4235 tiers:", {row["encode_tier"]: row["len"] for row in s4235.group_by("encode_tier").len().iter_rows(named=True)})
s4237 = frame.filter(pl.col("section_id").str.starts_with("4.2.37"))
print("  s4237 tiers:", {row["encode_tier"]: row["len"] for row in s4237.group_by("encode_tier").len().iter_rows(named=True)})
print("  encoded:", sorted(set(manifest["encoded_clause_ids"])))
print("  tier_c_deferred:", manifest["tier_c_deferred_count"], "| rules_in_json:", manifest["rules_in_json"])
print("  section_4.2.35_clause_total:", manifest.get("section_4.2.35_clause_total"), "| section_4.2.37_clause_total:", manifest.get("section_4.2.37_clause_total"))
print("  on-disk encoded:", sorted(set(json.loads((_REPO/"data/gazette/prose_manifests/L4.2_drug_indication_4235_4237_manifest.json").read_text(encoding="utf-8")).get("encoded_clause_ids") or [])))

# ---------------- 4238
show("4238")
batch_4238 = llb("drug_indication_4238_batch_rules.py:BATCH_A5_RULES")
frame = export_candidates(_CLAUSES, ALL_SECTIONS["4238"])
manifest = build_manifest(frame, batch_4238, ALL_SECTIONS["4238"], resolve_clauses=pl.read_parquet(_CLAUSES), effective_date="2026-06-27")
print("4238 encoded:", sorted(set(manifest["encoded_clause_ids"])))
print("4238 tier_c_deferred:", manifest["tier_c_deferred_count"], "| tier_b_pending:", manifest["tier_b_pending_count"])

# ---------------- 4224
show("4224")
batch_4224 = llb("BATCH_A24_RULES")
frame = export_candidates(_CLAUSES, ALL_SECTIONS["4224"])
manifest = build_manifest(frame, batch_4224, ALL_SECTIONS["4224"], resolve_clauses=pl.read_parquet(_CLAUSES), effective_date="2026-06-27")
print("4224 encoded:", sorted(set(manifest["encoded_clause_ids"])))

# ---------------- 4213 oral switch
show("4213")
frame = export_candidates(_CLAUSES, ALL_SECTIONS["4213"])
oral = frame.filter(pl.col("clause_id").is_in(["C004584", "C004593"]))
print("4213 oral switch rows:"); 
for row in oral.iter_rows(named=True):
    print("  ", row["clause_id"], "tier:", row["encode_tier"], "prio:", row["encode_priority"])

# ---------------- 4201 pending
show("4201")
print("4201 in-force ids len:", len(ALL_SECTIONS))
# read committed manifest
m4201 = json.loads((_REPO/"data/gazette/prose_manifests/L4.2_drug_indication_4201_manifest.json").read_text(encoding="utf-8"))
print("4201 committed tier_a_pending:", m4201.get("tier_a_pending_count"), "tier_b_pending:", m4201.get("tier_b_pending_count"))

# ---------------- copay 1.8.2.(1)
from scripts.sut.prose.clause_identity import resolve_gate_b_sources_to_clause_ids
_rules_copay = _REPO / "data/gazette/prose_rules/copay_general_1_8.json"
payload = json.loads(_rules_copay.read_text(encoding="utf-8"))
clauses = pl.read_parquet(_CLAUSES)
for r in payload.get("rules") or []:
    if str(r.get("rule_id")) == "1.8.2.(1)":
        refs = r.get("gate_b_sources") or []
        try:
            ids = sorted(resolve_gate_b_sources_to_clause_ids(refs, clauses, in_force_only=True, encode_eligible_only=False, allow_ambiguous=True))
        except Exception as e:
            ids = [str(x) for x in refs if str(x).startswith(("C", "F"))]
        print("copay 1.8.2.(1):", ids)

# ---------------- track_e sample id
sample = pl.read_parquet(_CLAUSES)
print("sample clause rows:", sample.height, "| first ids:", sample["clause_id"].head(5).to_list())
lookup = "C000006"
row = sample.filter(pl.col("clause_id") == lookup)
if row.height:
    print(lookup, "coordinate:", row["clause_coordinate"].to_list()[0])
else:
    print(lookup, "NOT FOUND")