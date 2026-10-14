"""(b) Material -> linked procedure: referential integrity + clinical compatibility.

Writes link.parquet (scratchpad). Compatibility table is in compat.py (printed here).
"""
import os

import polars as pl

from common import HERE, load, norm_expr
from compat import FAMILY_PROC_RE, GENERIC_TOLERATED, GENERIC_VISIT_RE, material_family_expr

pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_rows(120)
pl.Config.set_fmt_str_lengths(60)
pl.Config.set_tbl_width_chars(260)

m, p, h, a, cp = load()
print("polars", pl.__version__)

mm = m.select("material_line_id", "claim_id", "patient_id", "procedure_line_id", "material_date", "material_code",
              "material_name", "material_type", "is_bundled", "billed_amount_try").with_columns(
    material_family_expr().alias("family"))
pp = p.select("procedure_line_id", pl.col("claim_id").alias("p_claim_id"), pl.col("patient_id").alias("p_patient_id"),
              "procedure_date", "procedure_code", "procedure_name", "procedure_category", "package_code",
              "is_package_included").with_columns(norm_expr("procedure_name").alias("k_proc"))

j = mm.join(pp, on="procedure_line_id", how="left")

# family-specific regex: loop over the 11-entry dict (not over rows) -> vectorised per family
compat = pl.lit(False)
for fam, rx in FAMILY_PROC_RE.items():
    compat = pl.when(pl.col("family") == fam).then(pl.col("k_proc").fill_null("").str.contains(rx)).otherwise(compat)
j = j.with_columns(compat.alias("compatible")).with_columns(
    pl.col("p_claim_id").is_null().alias("dangling"),
    (pl.col("p_claim_id").is_not_null() & (pl.col("p_claim_id") != pl.col("claim_id"))).alias("cross_claim"),
    (pl.col("p_patient_id").is_not_null() & (pl.col("p_patient_id") != pl.col("patient_id"))).alias("cross_patient"),
    (pl.col("procedure_date").is_not_null() & (pl.col("procedure_date") != pl.col("material_date"))).alias("date_mismatch"),
    pl.when(pl.col("p_claim_id").is_null()).then(pl.lit("DANGLING"))
    .when(pl.col("compatible")).then(pl.lit("COMPATIBLE"))
    .when(pl.col("procedure_code").str.starts_with("L") | (pl.col("procedure_category") == "laboratuvar")).then(pl.lit("LAB_TEST"))
    .when(pl.col("k_proc").str.contains(GENERIC_VISIT_RE)).then(pl.lit("GENERIC_VISIT_OR_BED"))
    .when(pl.col("procedure_name") == pl.col("procedure_code")).then(pl.lit("UNNAMED_PROC"))
    .otherwise(pl.lit("UNRELATED_SPECIFIC")).alias("link_class"),
)
j = j.with_columns(
    (pl.col("link_class").is_in(["LAB_TEST", "UNRELATED_SPECIFIC", "UNNAMED_PROC"])
     | ((pl.col("link_class") == "GENERIC_VISIT_OR_BED") & ~pl.col("family").is_in(list(GENERIC_TOLERATED))))
    .alias("incompatible")
)

# claim-level rescue: does ANY procedure line on the same claim fit the material family?
cl = mm.select("material_line_id", "claim_id", "family").join(
    pp.select(pl.col("p_claim_id").alias("claim_id"), "k_proc", "procedure_code", "procedure_name"), on="claim_id", how="left")
resc = pl.lit(False)
for fam, rx in FAMILY_PROC_RE.items():
    resc = pl.when(pl.col("family") == fam).then(pl.col("k_proc").fill_null("").str.contains(rx)).otherwise(resc)
cl = cl.with_columns(resc.alias("fits"))
rescue = cl.group_by("material_line_id").agg(
    pl.col("fits").any().alias("claim_has_fitting_proc"),
    pl.col("procedure_name").filter(pl.col("fits")).unique().alias("fitting_procs_on_claim"),
    pl.len().alias("n_procs_on_claim"))
j = j.join(rescue, on="material_line_id", how="left")
j.write_parquet(os.path.join(HERE, "link.parquet"))

N = j.height
print(f"\nmaterial lines: {N}")
print("[b] referential integrity:", j.select(
    pl.col("dangling").sum(), pl.col("cross_claim").sum(), pl.col("cross_patient").sum(),
    pl.col("date_mismatch").sum(), pl.col("procedure_line_id").is_null().sum().alias("null_proc_id")).to_dicts()[0])

print("\n[b] COMPATIBILITY TABLE (family -> allowed linked-procedure regex) with counts")
tab = j.group_by("family").agg(
    pl.len().alias("lines"), pl.col("compatible").sum().alias("compatible"),
    pl.col("incompatible").sum().alias("incompatible"), pl.col("claim_has_fitting_proc").sum().alias("claim_has_fit"),
    pl.col("material_code").unique().sort().alias("codes")).sort("lines", descending=True)
tab = tab.with_columns(pl.col("family").replace_strict(FAMILY_PROC_RE, default="").alias("allowed_proc_regex"))
print(tab)
print("\n[b] linked-line class:")
print(j.group_by("link_class").agg(pl.len(), pl.col("billed_amount_try").sum().round(2).alias("billed_try")).sort("len", descending=True))
print("\n[b] procedure_category of the linked line (as stored):")
print(j.group_by("procedure_category").len().sort("len", descending=True))
print("\n[b] totals:", j.select(
    pl.col("incompatible").sum().alias("line_incompatible"),
    (~pl.col("claim_has_fitting_proc")).sum().alias("no_fitting_proc_anywhere_on_claim"),
    (pl.col("incompatible") & pl.col("claim_has_fitting_proc")).sum().alias("wrong_line_but_claim_has_fit"),
    pl.col("compatible").sum().alias("line_compatible")).to_dicts()[0])
print("\n[b] all pairs (material -> linked procedure):")
print(j.select(pl.col("material_line_id").str.replace("MLZ-F-SENTETIK-HASTA-", ""), "family", "material_code",
               pl.col("material_name").str.slice(0, 38), "procedure_code", pl.col("procedure_name").str.slice(0, 44),
               "link_class", "claim_has_fitting_proc").sort("material_line_id"))
print("\n[b] lines whose claim DOES contain a fitting procedure:")
print(j.filter(pl.col("claim_has_fitting_proc")).select(
    pl.col("material_line_id").str.replace("MLZ-F-SENTETIK-HASTA-", ""), "material_code", "procedure_name", "fitting_procs_on_claim"))
