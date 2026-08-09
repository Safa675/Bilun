"""Master probe: replicate every failing test's computation, print ACTUAL values."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import polars as pl

_REPO = ROOT
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_COVERAGE = _REPO / "data/gazette/sut_clause_coverage.parquet"

# ---------------------------------------------------------------- coverage
import pandas as pd
from scripts.sut.prose.coverage import build_sut_coverage, build_registry_coverage_summary
from scripts.sut.prose.rule_registry import RULE_BY_ID

print("=" * 70)
print("test_sut_coverage.py actuals")
clauses = pd.read_parquet(_CLAUSES)
coverage, _, _, registry = build_sut_coverage(clauses)

# 1) copay_exemption_ek4d primary gaps
primary = coverage[coverage["primary_rule_id"] == "copay_exemption_ek4d"]
print("copay ek4d primary count:", len(primary))
if len(primary):
    print("  gap sum:", int(primary["has_algorithmic_gap"].sum()))
    print("  encoding sum:", int(primary["has_rule_encoding"].sum()))
    gap_rows = primary[primary["has_algorithmic_gap"]]
    for _, r in gap_rows.iterrows():
        print("  GAP ROW:", r["clause_id"], r["section_id"], "enc:", r["has_rule_encoding"], "status:", r["coverage_status"])

# 2) drug_indication deontic unencoded
di = coverage[coverage["primary_rule_id"] == "drug_indication_prose"]
deontic = di[di["deontic_modality"].notna()]
unencoded = deontic[~deontic["has_rule_encoding"]]
print("drug_indication deontic total:", len(deontic), "unencoded:", len(unencoded))
for _, r in unencoded.iterrows():
    print("  UNENCODED:", r["clause_id"], r["section_id"], r["clause_type"], r["deontic_modality"], "in_force?", r.get("is_in_force"))

# 3) specialty materials statuses
sp = coverage[coverage["primary_rule_id"] == "specialty_materials_prose"]
print("specialty materials count:", len(sp))
print("  status counts:", sp["coverage_status"].value_counts().to_dict())
non_impl = sp[sp["coverage_status"] != "implemented"]
for _, r in non_impl.iterrows():
    print("  NON-IMPL:", r["clause_id"], r["section_id"], r["coverage_status"], "enc:", r["has_rule_encoding"], "gap:", r["has_algorithmic_gap"])

# 4) EMR blocked catalog
from scripts.sut.prose.coverage import _load_drug_indication_emr_blocked_clause_ids
catalog_path = _REPO / "data/gazette/prose_corpus/L4.2_drug_tier_c_emr_blocked_catalog.json"
catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
print("emr_blocked catalog clauses:", len(catalog.get("clauses") or []))
blocked = _load_drug_indication_emr_blocked_clause_ids()
print("emr_blocked loaded ids:", len(blocked))
