"""Probe: understand why eligible C* are non_identical in new corpus."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import polars as pl
from scripts.sut.prose.clause_identity import resolve_gate_b_ref_to_clause_ids
from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides

clauses_path = ROOT / "data/gazette/sut_clauses.parquet"
frame = apply_clause_type_overrides(pl.read_parquet(clauses_path))
by_id = {r["clause_id"]: r for r in frame.iter_rows(named=True)}

# Look at a few flagged ids
for cid in ["C000296", "C004524", "C006840", "C008293"]:
    row = by_id.get(cid)
    if row is None:
        print(cid, "NOT IN PARQUET")
        continue
    print("=" * 60)
    print(cid, "coordinate:", row["clause_coordinate"], "hash:", row["content_hash"])
    print("  clause_type:", row["clause_type"], "| in_force:", row["is_in_force"])
    print("  section:", row.get("section_id"), "| text:", str(row.get("text_tr"))[:100])
    # how many rows share this coordinate?
    same_coord = frame.filter(pl.col("clause_coordinate") == row["clause_coordinate"])
    print("  rows with same coordinate:", same_coord.height)
    for r in same_coord.iter_rows(named=True):
        print("    -", r["clause_id"], "| type:", r["clause_type"], "| in_force:", r["is_in_force"], "| hash:", r["content_hash"][:12], "| eligible:", r.get("encode_eligible"))
    key = f"{row['clause_coordinate']}#{row['content_hash']}"
    ids = resolve_gate_b_ref_to_clause_ids(key, frame, in_force_only=True, encode_eligible_only=True)
    print("  resolve(key) ->", ids)

print()
print("=== corpus stats ===")
print("rows:", frame.height)
print("distinct coordinates:", frame["clause_coordinate"].n_unique())
print("distinct hashes:", frame["content_hash"].n_unique())
print("dup coordinate+hash rows:", frame.group_by(["clause_coordinate", "content_hash"]).len().filter(pl.col("len") > 1).height)
