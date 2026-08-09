"""Comprehensive probe: extract correct golden constants from live parquet data.
Writes probe output to stdout for each test file that needs updating.
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import yaml

ROOT = Path(__file__).resolve().parents[1]
CLAUSES = ROOT / "data/gazette/sut_clauses.parquet"
COVERAGE = ROOT / "data/gazette/sut_clause_coverage.parquet"
RULES_DIR = ROOT / "data/gazette/prose_rules"
SOURCES_DIR = ROOT / "data/gazette/prose_rule_sources"
MANIFESTS_DIR = ROOT / "data/gazette/prose_manifests"
CORPUS_DIR = ROOT / "data/gazette/prose_corpus"


def section(prefix: str) -> str:
    return prefix


print("=" * 80)
print("PROBE: all golden constants from live 2026-07-01 corpus")
print("=" * 80)

clauses = pl.read_parquet(CLAUSES)
coverage = pl.read_parquet(COVERAGE)

# =========================================================================
# 1. test_sut_coverage.py — TestFullCoverageBuild
# =========================================================================
print("\n" + "=" * 60)
print("1. test_sut_coverage.py")
print("=" * 60)

# 1a. test_specialty_materials_prose_implemented_not_false_gap
print("\n--- test_specialty_materials_prose_implemented_not_false_gap ---")
sp_cov = coverage.filter(pl.col("primary_rule_id") == "specialty_materials_prose")
print(f"specialty_materials_prose rows: {len(sp_cov)}")
print("coverage_status value counts:")
print(sp_cov["coverage_status"].value_counts())
not_implemented = sp_cov.filter(pl.col("coverage_status") != "implemented")
print(f"Not implemented rows ({len(not_implemented)}):")
if len(not_implemented) > 0:
    print(not_implemented.select(["clause_id", "section_id", "coverage_status"]))
    print(not_implemented)

# 1b. test_copay_exemption_ek4d_implemented_has_mapping
print("\n--- test_copay_exemption_ek4d_implemented_has_mapping ---")
ce4d = coverage.filter(pl.col("primary_rule_id") == "copay_exemption_ek4d")
print(f"copay_exemption_ek4d primary rows: {len(ce4d)}")
if len(ce4d) > 0:
    print(f"has_algorithmic_gap sum: {ce4d['has_algorithmic_gap'].sum()}")
    print("gap rows:")
    print(ce4d.filter(pl.col("has_algorithmic_gap") == True).select(["clause_id", "section_id", "coverage_status"]))

# 1c. test_emr_blocked_catalog_and_coverage
print("\n--- test_emr_blocked_catalog_and_coverage ---")
from scripts.sut.prose.coverage import _load_drug_indication_emr_blocked_clause_ids
blocked = _load_drug_indication_emr_blocked_clause_ids()
print(f"len(blocked) = {len(blocked)}")
print(f"blocked sample: {sorted(blocked)[:10]}")

# 1d. test_drug_indication_deontic_fully_encoded
print("\n--- test_drug_indication_deontic_fully_encoded ---")
di = coverage.filter(pl.col("primary_rule_id") == "drug_indication_prose")
deontic = di.filter(pl.col("deontic_modality").is_not_null())
print(f"deontic drug_indication rows: {len(deontic)}")
unencoded = deontic.filter(~pl.col("has_rule_encoding"))
print(f"unencoded deontic rows: {len(unencoded)}")
if len(unencoded) > 0:
    print(unencoded.select(["clause_id", "section_id", "deontic_modality"]))

# 1e. test_unclassified_gaps_reduced_from_tier2_baseline
print("\n--- test_unclassified_gaps_reduced_from_tier2_baseline ---")
uncl = coverage.filter(
    (pl.col("primary_rule_category") == "unclassified")
    & pl.col("has_algorithmic_gap")
)
print(f"unclassified gaps: {len(uncl)}")
print(f"suggested upper bound: {len(uncl) + 5}")

# =========================================================================
# 2. test_drug_indication_4210_gate_b.py
# =========================================================================
print("\n" + "=" * 60)
print("2. test_drug_indication_4210_gate_b.py")
print("=" * 60)

from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
from scripts.sut.prose.gate_b_generic import export_candidates, build_manifest
from scripts.sut.rule_sources import load_drug_sections_rules

frame_4210 = export_candidates(CLAUSES, ALL_SECTIONS["4210"])
tier_a_4210 = set(frame_4210.filter(pl.col("encode_tier") == "A")["clause_id"].to_list())
print(f"\nActual _TIER_A_IDS ({len(tier_a_4210)}):")
print(f"    {json.dumps(sorted(tier_a_4210), indent=4)}")

rules_4210 = load_drug_sections_rules(
    ["4.2.10.A", "4.2.10.A-3", "4.2.10.A-4", "4.2.10.B-2", "4.2.10.B-3",
     "4.2.10.C-1", "4.2.10.C-2", "4.2.10.C-3", "4.2.10.D-2", "4.2.10.Ç-2"]
)
manifest_4210 = build_manifest(frame_4210, rules_4210, ALL_SECTIONS["4210"],
    resolve_clauses=clauses, effective_date="2026-06-27")
encoded_4210 = set(manifest_4210["encoded_clause_ids"])
tier_b_4210_enc = set(manifest_4210.get("tier_b_pending_clause_ids", []))

print(f"\nEncoded IDs ({len(encoded_4210)}): {sorted(encoded_4210)}")
# Tier B encoded (subset of encoded)
print(f"Tier B pending: {tier_b_4210_enc}")
print(f"tier_a_pending_count: {manifest_4210['tier_a_pending_count']}")
print(f"tier_b_pending_count: {manifest_4210['tier_b_pending_count']}")
print(f"rules_in_json: {manifest_4210['rules_in_json']}")

# Promotions scan
from scripts.sut.prose.gate_b_audit import default_scan_promotions
promotions = default_scan_promotions(frame_4210, encoded_clause_ids=encoded_4210)
print(f"\nPromotions count: {len(promotions)}")
if promotions:
    for p in promotions:
        print(f"  {p['clause_id']} ({p['section_id']}) — reasons: {p['reasons']}")

# =========================================================================
# 3. test_drug_indication_4234_gate_b.py
# =========================================================================
print("\n" + "=" * 60)
print("3. test_drug_indication_4234_gate_b.py")
print("=" * 60)

frame_4234 = export_candidates(CLAUSES, ALL_SECTIONS["4234"])
tier_a_4234 = set(frame_4234.filter(pl.col("encode_tier") == "A")["clause_id"].to_list())
print(f"\nActual _TIER_A_IDS ({len(tier_a_4234)}):")
print(f"    {json.dumps(sorted(tier_a_4234), indent=4)}")

from scripts.sut.rule_sources import load_legacy_drug_batch
BATCH_MS4234_RULES = load_legacy_drug_batch("drug_indication_4234_batch_rules.py:BATCH_MS4234_RULES")
manifest_4234 = build_manifest(frame_4234, BATCH_MS4234_RULES, ALL_SECTIONS["4234"],
    resolve_clauses=clauses, effective_date="2026-06-27")
encoded_4234 = set(manifest_4234["encoded_clause_ids"])
print(f"\nEncoded (fresh build) ({len(encoded_4234)}): {sorted(encoded_4234)}")
print(f"encoded_clause_count: {manifest_4234['encoded_clause_count']}")
print(f"tier_c_deferred_count: {manifest_4234['tier_c_deferred_count']}")

# =========================================================================
# 4. test_drug_indication_4206_gate_b.py
# =========================================================================
print("\n" + "=" * 60)
print("4. test_drug_indication_4206_gate_b.py")
print("=" * 60)

A6_RULES = load_legacy_drug_batch("drug_indication_4206_batch_rules.py:BATCH_A6_RULES")
A2_RULES = load_legacy_drug_batch("drug_indication_4206_a2_batch_rules.py:BATCH_A2_RULES")
all_4206_rules = [*A6_RULES, *A2_RULES]

frame_4206 = export_candidates(CLAUSES, ALL_SECTIONS["4206"])
manifest_4206 = build_manifest(frame_4206, all_4206_rules, ALL_SECTIONS["4206"],
    resolve_clauses=clauses, effective_date="2026-06-27")
encoded_4206 = set(manifest_4206["encoded_clause_ids"])
tier_a_4206 = set(frame_4206.filter(pl.col("encode_tier") == "A")["clause_id"].to_list())

print(f"\nAll tier A IDs ({len(tier_a_4206)}): {sorted(tier_a_4206)}")
print(f"All encoded IDs ({len(encoded_4206)}): {sorted(encoded_4206)}")

# Figure out the A2 vs A6 split
a6_sources = set()
for r in A6_RULES:
    for s in r.get("gate_b_sources", []):
        if isinstance(s, str):
            a6_sources.add(s)
a2_sources = set()
for r in A2_RULES:
    for s in r.get("gate_b_sources", []):
        if isinstance(s, str):
            a2_sources.add(s)

print(f"\na6_sources: {sorted(a6_sources)}")
print(f"a2_sources: {sorted(a2_sources)}")

# =========================================================================
# 5. test_drug_indication_4235_4237_gate_b.py
# =========================================================================
print("\n" + "=" * 60)
print("5. test_drug_indication_4235_4237_gate_b.py")
print("=" * 60)

BATCH_A5_RULES = load_legacy_drug_batch("drug_indication_4235_4237_batch_rules.py:BATCH_A5_RULES")
frame_4235 = export_candidates(CLAUSES, ALL_SECTIONS["4235_4237"])
manifest_4235 = build_manifest(frame_4235, BATCH_A5_RULES, ALL_SECTIONS["4235_4237"],
    resolve_clauses=clauses, effective_date="2026-06-27")
encoded_4235 = set(manifest_4235["encoded_clause_ids"])
print(f"\nEncoded IDs ({len(encoded_4235)}): {sorted(encoded_4235)}")
print(f"'C006717' in encoded: {'C006717' in encoded_4235}")
print(f"tier_c_deferred_count: {manifest_4235['tier_c_deferred_count']}")
print(f"section_4.2.35_clause_total: {manifest_4235.get('section_4.2.35_clause_total')}")
print(f"section_4.2.37_clause_total: {manifest_4235.get('section_4.2.37_clause_total')}")

tier = frame_4235.group_by("encode_tier").len().sort("encode_tier")
counts = {row["encode_tier"]: row["len"] for row in tier.iter_rows(named=True)}
print(f"\nTier counts: {counts}")

s4235 = frame_4235.filter(pl.col("section_id").str.starts_with("4.2.35"))
s4237 = frame_4235.filter(pl.col("section_id").str.starts_with("4.2.37"))
s4235_tiers = {row["encode_tier"]: row["len"] for row in s4235.group_by("encode_tier").len().iter_rows(named=True)}
s4237_tiers = {row["encode_tier"]: row["len"] for row in s4237.group_by("encode_tier").len().iter_rows(named=True)}
print(f"4.2.35 tier counts: {s4235_tiers}")
print(f"4.2.37 tier counts: {s4237_tiers}")

encoded_clause_count_4235 = len(encoded_4235)
print(f"encoded_clause_count (from manifest): {encoded_clause_count_4235}")

# =========================================================================
# 6. test_drug_indication_4215_gate_b.py
# =========================================================================
print("\n" + "=" * 60)
print("6. test_drug_indication_4215_gate_b.py")
print("=" * 60)

BATCH_A15_RULES = load_legacy_drug_batch("BATCH_A15_RULES")
frame_4215 = export_candidates(CLAUSES, ALL_SECTIONS["4215"])
manifest_4215 = build_manifest(frame_4215, BATCH_A15_RULES, ALL_SECTIONS["4215"],
    resolve_clauses=clauses, effective_date="2026-06-27")
encoded_4215 = set(manifest_4215["encoded_clause_ids"])
print(f"\nEncoded IDs (fresh build) ({len(encoded_4215)}): {sorted(encoded_4215)}")
print(f"encoded_clause_count: {manifest_4215['encoded_clause_count']}")
print(f"tier_c_deferred_count: {manifest_4215['tier_c_deferred_count']}")

# =========================================================================
# 7. test_drug_indication_4214c_gate_b.py
# =========================================================================
print("\n" + "=" * 60)
print("7. test_drug_indication_4214c_gate_b.py")
print("=" * 60)

section_4214c = ALL_SECTIONS["4214c"]
frame_4214c = export_candidates(CLAUSES, section_4214c)
print(f"\nframe.height: {frame_4214c.height}")

in_force_4214c = set(
    clauses.filter(
        (pl.col("section_id") == "4.2.14.C") & (pl.col("is_in_force") == True)
    )["clause_id"].to_list()
)
print(f"in-force 4.2.14.C count: {len(in_force_4214c)}")

# =========================================================================
# 8. test_authored_cstar_inventory.py
# =========================================================================
print("\n" + "=" * 60)
print("8. test_authored_cstar_inventory.py")
print("=" * 60)

CSTAR_RE = __import__("re").compile(r"^[CF]\d{6}$")

def cstar_refs_in_gate_b_sources():
    refs = set()
    for path in sorted((SOURCES_DIR).glob("**/*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for rule in payload.get("rules") or []:
            for src in rule.get("gate_b_sources") or []:
                text = str(src)
                if CSTAR_RE.fullmatch(text):
                    refs.add(text)
    return refs

def cstar_refs_in_deferral():
    payload = yaml.safe_load((RULES_DIR / "deferral_table.yaml").read_text(encoding="utf-8"))
    return {
        str(e.get("clause_id"))
        for e in payload.get("entries") or []
        if CSTAR_RE.fullmatch(str(e.get("clause_id") or ""))
    }

def cstar_refs_in_sections():
    refs = set()
    for section in ALL_SECTIONS.values():
        for override in section.tier_a_overrides + section.tier_b_overrides:
            refs.update(c for c in override.clause_ids if CSTAR_RE.fullmatch(c))
        refs.update(c for c in section.superseded_ids if CSTAR_RE.fullmatch(c))
        for ids in section.force_include_ids.values():
            refs.update(c for c in ids if CSTAR_RE.fullmatch(c))
    return refs

def cstar_refs_in_wave_config():
    from scripts.sut.gate_b_wave_config import DRUG_INDICATION_WAVE_CLAUSE_KEYS
    return {
        ref
        for keys in DRUG_INDICATION_WAVE_CLAUSE_KEYS.values()
        for ref in keys
        if CSTAR_RE.fullmatch(ref)
    }

def cstar_refs_in_stub():
    from scripts.sut.compile_rules import _PAYMENT_SESSION_MANIFEST_STUB
    return {
        ref
        for ref in _PAYMENT_SESSION_MANIFEST_STUB.get("encoded_clause_keys") or []
        if CSTAR_RE.fullmatch(ref)
    }

per_surface = {
    "gate_b_sources": cstar_refs_in_gate_b_sources(),
    "deferral": cstar_refs_in_deferral(),
    "gate_b_sections": cstar_refs_in_sections(),
    "wave_config": cstar_refs_in_wave_config(),
    "payment_stub": cstar_refs_in_stub(),
}
for surface, refs in per_surface.items():
    print(f"  {surface}: {len(refs)}")

total = sum(len(refs) for refs in per_surface.values())
print(f"  total: {total}")

# Eligible C* check
from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides
frame_t = apply_clause_type_overrides(clauses)
by_id = {r["clause_id"]: r for r in frame_t.iter_rows(named=True)}

refs_all = set()
for s in per_surface.values():
    refs_all |= s

eligible = []
for cid in sorted(refs_all):
    row = by_id.get(cid)
    if row is None:
        continue
    if row["clause_type"] in ("bent", "numbered_item", "fikra") and row["is_in_force"] is True:
        eligible.append(cid)

non_identical = []
identical = 0
from scripts.sut.prose.clause_identity import resolve_gate_b_ref_to_clause_ids
for cid in eligible:
    row = by_id[cid]
    key = f"{row['clause_coordinate']}#{row['content_hash']}"
    try:
        ids = resolve_gate_b_ref_to_clause_ids(key, frame_t, in_force_only=True, encode_eligible_only=True)
    except Exception:
        non_identical.append(cid)
        continue
    if ids == [cid]:
        non_identical.append(cid)
    else:
        identical += 1

print(f"\nEligible identical-duplicate C*: {identical}")
print(f"Non-identical (losslessly keyable): {non_identical[:20]}")
print(f"Suggested identical assertion: assert identical == {identical}")

# =========================================================================
# 9. test_track_e_public_contract.py
# =========================================================================
print("\n" + "=" * 60)
print("9. test_track_e_public_contract.py")
print("=" * 60)

# What clause does C002684 resolve to?
c002684 = clauses.filter(pl.col("clause_id") == "C002684")
print(f"\nC002684 rows: {len(c002684)}")
if len(c002684) > 0:
    row = c002684.to_dicts()[0]
    print(f"clause_coordinate: {row.get('clause_coordinate')}")
    print(f"clause_key: {row.get('clause_key')}")
    print(f"is_in_force: {row.get('is_in_force')}")
else:
    print("C002684 NOT IN PARQUET — need to find a replacement")

# Find a clause that exists with coordinate
sample = clauses.filter(
    pl.col("clause_coordinate").is_not_null()
    & (pl.col("clause_coordinate") != "")
).limit(1)
if len(sample) > 0:
    row = sample.to_dicts()[0]
    print(f"\nSample clause with coordinate: {row['clause_id']} → {row['clause_coordinate']}")
    print(f"clause_key: {row.get('clause_key')}")

test_coord_clause = clauses.filter(
    pl.col("clause_coordinate").is_not_null()
    & (pl.col("clause_coordinate") != "")
    & pl.col("is_in_force")
).limit(5).to_dicts()
print(f"\n5 in-force clauses with coordinates:")
for r in test_coord_clause:
    print(f"  {r['clause_id']} → coord={r['clause_coordinate']}, key={r.get('clause_key')}")

# =========================================================================
# 10. test_drug_indication_4238_gate_b.py
# =========================================================================
print("\n" + "=" * 60)
print("10. test_drug_indication_4238_gate_b.py")
print("=" * 60)

BATCH_A5_RULES_4238 = load_legacy_drug_batch("drug_indication_4238_batch_rules.py:BATCH_A5_RULES")
frame_4238 = export_candidates(CLAUSES, ALL_SECTIONS["4238"])
manifest_4238 = build_manifest(frame_4238, BATCH_A5_RULES_4238, ALL_SECTIONS["4238"],
    resolve_clauses=clauses, effective_date="2026-06-27")
encoded_4238 = set(manifest_4238["encoded_clause_ids"])
print(f"\nEncoded (fresh) ({len(encoded_4238)}): {sorted(encoded_4238)}")
print(f"encoded_clause_count: {manifest_4238['encoded_clause_count']}")
print(f"tier_c_deferred_count: {manifest_4238['tier_c_deferred_count']}")
print(f"tier_b_pending_count: {manifest_4238['tier_b_pending_count']}")

# =========================================================================
# 11. test_drug_indication_4224_gate_b.py
# =========================================================================
print("\n" + "=" * 60)
print("11. test_drug_indication_4224_gate_b.py")
print("=" * 60)

BATCH_A24_RULES = load_legacy_drug_batch("BATCH_A24_RULES")
frame_4224 = export_candidates(CLAUSES, ALL_SECTIONS["4224"])
manifest_4224 = build_manifest(frame_4224, BATCH_A24_RULES, ALL_SECTIONS["4224"],
    resolve_clauses=clauses, effective_date="2026-06-27")
encoded_4224 = set(manifest_4224["encoded_clause_ids"])
print(f"\nEncoded (fresh) ({len(encoded_4224)}): {sorted(encoded_4224)}")
print(f"encoded_clause_count: {manifest_4224['encoded_clause_count']}")

# =========================================================================
# 12. test_drug_indication_4213_gate_b.py — oral switch
# =========================================================================
print("\n" + "=" * 60)
print("12. test_drug_indication_4213_gate_b.py — oral switch")
print("=" * 60)

frame_4213 = export_candidates(CLAUSES, ALL_SECTIONS["4213"])
oral_switch = frame_4213.filter(pl.col("clause_id").is_in(["C004584", "C004593"]))
print(f"\nOral switch rows: {oral_switch.height}")
if oral_switch.height > 0:
    for r in oral_switch.to_dicts():
        print(f"  {r['clause_id']}: encode_tier={r['encode_tier']}, encode_priority={r.get('encode_priority')}")
else:
    print("No oral switch rows found — both C* absent from 4213 export")

# =========================================================================
# 13. test_drug_indication_4201_gate_b.py — artifacts on disk
# =========================================================================
print("\n" + "=" * 60)
print("13. test_drug_indication_4201_gate_b.py")
print("=" * 60)

from scripts.sut.rule_sources import load_drug_sections_rules
from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
from scripts.sut.prose.gate_b_generic import export_candidates, write_artifacts

import tempfile
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    mf = tmp / "L4.2_drug_indication_4201_manifest.json"
    cp = tmp / "L4.2_drug_indication_4201.csv"
    rules_path = ROOT / "data/gazette/prose_rules/drug_indication_prose.json"
    write_artifacts(
        section=ALL_SECTIONS["4201"],
        clauses_path=CLAUSES,
        rules_path=rules_path,
        corpus_csv=cp,
        manifest_path=mf,
        effective_date="2026-06-27",
        write_corpus=True,
    )
    manif = json.loads(mf.read_text(encoding="utf-8"))
    print(f"\ntier_a_pending_count: {manif['tier_a_pending_count']}")
    print(f"tier_b_pending_count: {manif['tier_b_pending_count']}")
    print(f"encoded_clause_count: {manif['encoded_clause_count']}")
    print(f"section_clause_total: {manif['section_clause_total']}")

# =========================================================================
# 14. test_copay_exemption_gate_b.py — JSON rules mapping
# =========================================================================
print("\n" + "=" * 60)
print("14. test_copay_exemption_gate_b.py")
print("=" * 60)

from scripts.sut.prose.clause_identity import (
    resolve_gate_b_sources_to_clause_ids,
)

rules_payload = json.loads((RULES_DIR / "copay_general_1_8.json").read_text(encoding="utf-8"))
mapping = {}
for rule in rules_payload.get("rules") or []:
    rid = str(rule.get("rule_id") or "")
    if not rid:
        continue
    refs = rule.get("gate_b_sources") or []
    try:
        ids = sorted(
            resolve_gate_b_sources_to_clause_ids(refs, clauses, in_force_only=True,
                encode_eligible_only=False, allow_ambiguous=True)
        )
    except Exception:
        ids = [str(r) for r in refs if str(r).startswith(("C", "F"))]
    mapping[rid] = ids

print(f"\nmapping['1.8.2.(1)'] = {mapping.get('1.8.2.(1)')}")
print(f"mapping['1.8.5.(10).organ_nakli'] = {mapping.get('1.8.5.(10).organ_nakli')}")

print("\n" + "=" * 80)
print("PROBE COMPLETE")
print("=" * 80)