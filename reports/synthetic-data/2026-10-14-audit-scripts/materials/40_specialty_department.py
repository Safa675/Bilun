"""(c) specialty_category / material_type content, per-claim mix, and fit with claim_headers.department.

Branch of a material = branch that owns its EK-3 sub-annex (annex titles in the raw files, e.g.
EK-3O 'HEMATOLOJİ-ONKOLOJİ BRANŞINA AİT', EK-3S 'GÖĞÜS HASTALIKLARI VE GÖĞÜS CERRAHİSİ BRANŞLARINA AİT').
Department compatibility table is JUDGMENT (generous).
"""
import os

import polars as pl

from common import HERE, load, norm_expr

pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_rows(80)
pl.Config.set_fmt_str_lengths(60)
pl.Config.set_tbl_width_chars(240)

m, p, h, a, cp = load()
idn = pl.read_parquet(os.path.join(HERE, "identity.parquet")).select("material_line_id", "annex")
x = (m.select("material_line_id", "claim_id", "material_code", "material_name", "material_type", "specialty_category")
     .join(idn, on="material_line_id", how="left")
     .join(h.select("claim_id", "department", "claim_type"), on="claim_id", how="left"))

sc = x["specialty_category"]
print("[c] specialty_category distinct values (incl. empty):", sc.n_unique(),
      "| empty:", (sc == "").sum(), "| identical to material_type:", (x["specialty_category"] == x["material_type"]).sum(), "/", x.height)
print("    values:", sorted(sc.unique().to_list(), key=lambda s: (len(s), s))[:40])
# which values are actual medical branches?
BRANCH_WORDS = r"KARDIYOLOJI|ORTOPEDI|NEFROLOJI|HEMATOLOJI|ONKOLOJI|GOGUS|GASTRO|UROLOJI|NOROLOJI|CERRAHI|DAHILIYE|IC HASTALIK|FIZIK TEDAVI|KBB|GOZ"
x = x.with_columns(norm_expr("specialty_category").alias("k_sc"))
print("    values naming a medical branch:", x.filter(pl.col("k_sc").str.contains(BRANCH_WORDS))["specialty_category"].unique().to_list())
print("    values that are EK-3 section headings (all caps, not a branch):",
      x.filter(~pl.col("k_sc").str.contains(BRANCH_WORDS) & (pl.col("specialty_category") != ""))["specialty_category"].n_unique())

ANNEX_BRANCH = {"EK-3O": "Hematoloji-Onkoloji", "EK-3P": "Nefroloji", "EK-3S": "Göğüs Hast./Göğüs Cerr.",
                "EK-3R": "Gastroenteroloji", "EK-3F-1": "Ortopedi (artroplasti)", "EK-3C-2": "Ortez-protez (FTR/Ortopedi)"}
DEPT_OK = {  # department (normalised) regex allowed per annex - JUDGMENT, generous
    "EK-3O": r"HEMATOLOJI|ONKOLOJI|IC HASTALIK|NEFROLOJI|NOROLOJI",
    "EK-3P": r"NEFROLOJI|IC HASTALIK|YOGUN BAKIM",
    "EK-3S": r"GOGUS",
    "EK-3R": r"GASTRO|GENEL CERRAHI|IC HASTALIK",
    "EK-3F-1": r"ORTOPEDI",
    "EK-3C-2": r"ORTOPEDI|FIZIK|FTR|REHAB",
}
x = x.with_columns(pl.col("annex").replace_strict(ANNEX_BRANCH, default=None).alias("annex_branch"),
                   norm_expr("department").alias("k_dept"))
ok = pl.lit(None, pl.Boolean)
for ax, rx in DEPT_OK.items():
    ok = pl.when(pl.col("annex") == ax).then(pl.col("k_dept").str.contains(rx)).otherwise(ok)
x = x.with_columns(ok.alias("dept_fits_annex"))
print("\n[c] annex-branch vs claim department:")
print(x.group_by("annex", "department").agg(pl.len(), pl.col("dept_fits_annex").first()).sort("annex", "department"))
print("    lines whose department does not fit the annex branch:", (x["dept_fits_annex"] == False).sum(),
      "| not evaluable (demo/unknown code):", x["dept_fits_annex"].is_null().sum())
print(x.filter(pl.col("dept_fits_annex") == False).select("material_line_id", "material_code", "annex", "department"))

per_claim = x.group_by("claim_id").agg(pl.col("specialty_category").n_unique().alias("n_cat"),
                                        pl.col("annex").drop_nulls().n_unique().alias("n_annex"),
                                        pl.col("annex").drop_nulls().unique().sort().alias("annexes"),
                                        pl.len().alias("n_lines"), pl.col("department").first())
print("\n[c] claims with materials:", per_claim.height, "| >=2 specialty_category values:", (per_claim["n_cat"] >= 2).sum(),
      "| >=2 EK-3 annexes (branches):", (per_claim["n_annex"] >= 2).sum())
print(per_claim.filter(pl.col("n_annex") >= 2).sort("claim_id"))
print("\n[c] department value spelling (claim_headers, all 94 claims):", sorted(h["department"].unique().to_list()))
