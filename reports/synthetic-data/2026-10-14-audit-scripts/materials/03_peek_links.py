"""Peek: materials joined to their linked procedure line and claim header (read-only)."""
import polars as pl

B = "/home/safa/Documents/Bilun/data/synthetic/sut/claims/"
m = pl.read_parquet(B + "material_claim_lines.parquet")
p = pl.read_parquet(B + "procedure_claim_lines.parquet")
h = pl.read_parquet(B + "claim_headers.parquet")

j = (
    m.select("material_line_id", "claim_id", "procedure_line_id", "material_code", "material_name")
    .join(
        p.select("procedure_line_id", "procedure_code", "procedure_name", "procedure_category",
                 pl.col("claim_id").alias("p_claim")),
        on="procedure_line_id", how="left",
    )
    .join(h.select("claim_id", "claim_type", "department", "primary_icd10", "package_candidate",
                   "scenario_tag"), on="claim_id", how="left")
)
for r in j.iter_rows(named=True):  # display only
    print(f"{r['material_line_id'][4:]:<32} {r['material_code']:<8} {r['material_name'][:45]:<45} || "
          f"{str(r['procedure_code']):<8} {str(r['procedure_name'])[:60]:<60} | {r['procedure_category']} "
          f"| {r['claim_type']} | {r['department']} | {r['primary_icd10']} | pkg={r['package_candidate']}")
print()
print(h.group_by("department").len().sort("len", descending=True))
print(h.group_by("claim_type").len())
