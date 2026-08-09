"""Probe: actual values for every failing gate_b / coverage assertion (new corpus)."""
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

print("=" * 70)
print("4234")
_SECTION = "4234"
frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
BATCH = load_legacy_drug_batch("drug_indication_4234_batch_rules.py:BATCH_MS4234_RULES")
manifest = build_manifest(frame, BATCH, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES), effective_date="2026-06-27")
tier_a_ids = set(frame.filter(pl.col("encode_tier") == "A")["clause_id"].to_list())
print("tier_a_ids:", sorted(tier_a_ids))
print("encoded:", sorted(set(manifest["encoded_clause_ids"])))
print("tier_a_pending:", manifest["tier_a_pending_count"], "| encoded_count:", manifest["encoded_clause_count"])
print("tier_c_deferred:", manifest["tier_c_deferred_count"], "| rules_in_json:", manifest["rules_in_json"], "| section_total:", manifest["section_clause_total"])
print("height:", frame.height)
print("tier A height:", frame.filter(pl.col("encode_tier") == "A").height, "tier C height:", frame.filter(pl.col("encode_tier") == "C").height)

print("=" * 70)
print("4210")
_SECTION = "4210"
frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
from scripts.sut.rule_sources import load_drug_sections_rules
rules = load_drug_sections_rules(
    ["4.2.10.A", "4.2.10.A-3", "4.2.10.A-4", "4.2.10.B-2", "4.2.10.B-3",
     "4.2.10.C-1", "4.2.10.C-2", "4.2.10.C-3", "4.2.10.D-2", "4.2.10.Ç-2"]
)
manifest = build_manifest(frame, rules, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES), effective_date="2026-06-27")
tier_a_ids = set(frame.filter(pl.col("encode_tier") == "A")["clause_id"].to_list())
print("tier_a_ids:", sorted(tier_a_ids))
print("encoded:", sorted(set(manifest["encoded_clause_ids"])))
print("tier counts A/B/C:", frame.filter(pl.col("encode_tier") == "A").height, frame.filter(pl.col("encode_tier") == "B").height, frame.filter(pl.col("encode_tier") == "C").height)
print("tier_a_pending:", manifest["tier_a_pending_count"], "| tier_b_pending:", manifest["tier_b_pending_count"])
print("rules_in_json:", manifest["rules_in_json"], "| section_total:", manifest["section_clause_total"])
print("height:", frame.height)
from scripts.sut.prose.gate_b_audit import default_scan_promotions
promotions = default_scan_promotions(frame, encoded_clause_ids=set(manifest["encoded_clause_ids"]))
print("promotions:", [(p["clause_id"], p.get("reasons")) for p in promotions])
