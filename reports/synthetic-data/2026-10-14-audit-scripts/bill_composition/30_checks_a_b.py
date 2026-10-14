"""(a) department/specialty vs SUT chapter, chapter mixing; (b) care setting vs content."""
import polars as pl
OUT = "/tmp/claude-1000/-home-safa-Documents-Bilun/a9cf6beb-cd1a-4613-ab9e-bddecbe1db1a/scratchpad/audit/bill_composition"
pl.Config.set_tbl_rows(80); pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(230); pl.Config.set_fmt_str_lengths(70)
L = pl.read_parquet(f"{OUT}/enriched_lines.parquet")
C = pl.read_parquet(f"{OUT}/enriched_claims.parquet")
sid = lambda c: pl.col(c).str.replace("ISL-F-SENTETIK-HASTA-", "").str.replace("F-SENTETIK-HASTA-", "")
NC = C.height

print("=" * 30, "(a) DEPARTMENT / SPECIALTY")
spec = L.with_columns(
    pl.when(pl.col("procedure_specialty_code").is_null()).then(pl.lit("null"))
      .when(pl.col("procedure_specialty_code") == pl.col("department")).then(pl.lit("== header department"))
      .otherwise(pl.lit("differs")).alias("spec_vs_dept"))
print(spec["spec_vs_dept"].value_counts().to_dicts())
print("null-specialty lines:", spec.filter(pl.col("spec_vs_dept") == "null").select(sid("procedure_line_id").alias("line"), "procedure_code", "scenario_tag").to_dicts())
nspec = L.group_by("claim_id").agg(pl.col("procedure_specialty_code").drop_nulls().n_unique().alias("n"))
print("claims by #distinct non-null specialty values:", nspec["n"].value_counts().sort("n").to_dicts())

SURG_DEPTS = ["Ortopedi ve Travmatoloji", "ortopedi", "genel_cerrahi"]
# judgment: chapters a department could plausibly perform itself
DEPT_OK = {
    "Ortopedi ve Travmatoloji": ["6.7", "6.1", "6.8"], "ortopedi": ["6.7", "6.1", "6.8"],
    "genel_cerrahi": ["6.1", "6.3", "6.6", "6.11", "6.4"],
}
surg = L.filter("is_surgical")
print("\nsurgical (6.x incl. P-packages) lines:", surg.height, "on", surg["claim_id"].n_unique(), "claims")
print("surgical lines by department type:",
      surg.with_columns(pl.col("department").is_in(SURG_DEPTS).alias("surgical_dept")).group_by("surgical_dept")
          .agg(pl.len().alias("lines"), pl.col("claim_id").n_unique().alias("claims")).to_dicts())
print("surgical lines under NON-surgical departments, by department:")
print(surg.filter(~pl.col("department").is_in(SURG_DEPTS)).group_by("department").agg(
    pl.len().alias("lines"), pl.col("claim_id").n_unique().alias("claims"),
    pl.col("chapter").unique().sort().alias("chapters")).sort("lines", descending=True))
ok_tbl = pl.DataFrame({"department": list(DEPT_OK), "ok": list(DEPT_OK.values())})
sd = surg.filter(pl.col("department").is_in(SURG_DEPTS)).join(ok_tbl, on="department").with_columns(
    pl.col("chapter").is_in(pl.col("ok")).alias("in_own_field"))
print("surgical-department lines inside own field (judgment table", DEPT_OK, "):",
      sd["in_own_field"].value_counts().to_dicts())
print(sd.filter(~pl.col("in_own_field")).select(sid("procedure_line_id").alias("line"), "department", "chapter", "procedure_name").head(40))

print("\n-- chapter mixing per claim")
per = L.group_by("claim_id").agg(
    pl.col("chapter").filter(pl.col("is_surgical")).n_unique().alias("n_surg_ch"),
    pl.col("chapter").filter(pl.col("chapter").str.contains(r"^(6|7)\.")).n_unique().alias("n_clin_ch"),
    pl.col("chapter").n_unique().alias("n_all_ch"),
    pl.len().alias("n_lines"))
per = C.select("claim_id", "claim_type", "department").join(per, on="claim_id", how="left").fill_null(0)
print("claims with >=1 surgical line:", per.filter(pl.col("n_surg_ch") >= 1).height, "/", NC)
print("claims with >=2 surgical chapters:", per.filter(pl.col("n_surg_ch") >= 2).height, "/", NC)
print("claims with >=3 surgical chapters:", per.filter(pl.col("n_surg_ch") >= 3).height, "/", NC)
print("claims with >=2 clinical chapters (6.x+7.x):", per.filter(pl.col("n_clin_ch") >= 2).height, "/", NC)
print("claims with >=2 chapters overall:", per.filter(pl.col("n_all_ch") >= 2).height, "/", NC,
      "| exactly one chapter overall:", per.filter(pl.col("n_all_ch") == 1).height)
print("one-chapter claims:", per.filter(pl.col("n_all_ch") == 1).join(L.group_by("claim_id").agg(pl.col("chapter").first()), on="claim_id").select(sid("claim_id"), "claim_type", "n_lines", "chapter").to_dicts())
print("distribution n_surg_ch:", per["n_surg_ch"].value_counts().sort("n_surg_ch").to_dicts())
worst = per.sort(["n_surg_ch", "n_clin_ch"], descending=True).head(6)
for cid in worst["claim_id"]:
    x = L.filter(pl.col("claim_id") == cid)
    print("  ", cid.replace("F-SENTETIK-HASTA-", ""), x["claim_type"][0], x["department"][0], x["primary_icd10"][0], "|",
          "; ".join(f"{r['chapter']}:{r['procedure_name'][:45]}" for r in x.filter("is_surgical").iter_rows(named=True)))
print("\nunmapped lines (no chapter):", L.filter(pl.col("chapter").is_null()).height)
nv = L.filter(pl.col("ek2b_puan").is_null())
print("lines whose code has no EK-2B row valid on the line date:", nv.height,
      nv.select(sid("procedure_line_id").alias("line"), "procedure_code", "pdate", "procedure_name").to_dicts())

print("\n" + "=" * 30, "(b) CARE SETTING vs CONTENT")
print("surgical-group basis:", L.filter("is_surgical").with_columns(
    pl.when(pl.col("ek2c_group").is_not_null()).then(pl.lit("EK-2C group of P+code")).otherwise(pl.lit("EK-2B puan threshold")).alias("basis")
)["basis"].value_counts().to_dicts())
print("surgical lines by group:", L.filter("is_surgical")["surg_group"].value_counts().sort("surg_group").to_dicts())
NONINP = ["poliklinik", "acil", "koruyucu", "meslek_hastaligi"]
ms = L.filter(pl.col("is_major_surgery"))
print("major surgery (6.x, group A1-B) lines by claim_type:",
      ms.group_by("claim_type").agg(pl.len().alias("lines"), pl.col("claim_id").n_unique().alias("claims")).sort("claim_type").to_dicts())
print("claims per type for reference:", C["claim_type"].value_counts().sort("claim_type").to_dicts())
mo = ms.filter(pl.col("claim_type").is_in(NONINP))
print(f"major surgery on poliklinik/acil/koruyucu/meslek: {mo.height} lines on {mo['claim_id'].n_unique()} claims "
      f"(of {C.filter(pl.col('claim_type').is_in(NONINP)).height} such claims)")
print(mo.select(sid("procedure_line_id").alias("line"), "claim_type", "department", "surg_group", "chapter", "procedure_name", "billed_amount_try").sort("surg_group"))
anys = L.filter(pl.col("is_surgical") & pl.col("claim_type").is_in(NONINP))
print("ANY 6.x surgery on those claim types:", anys.height, "lines,", anys["claim_id"].n_unique(), "claims")
kor = L.filter(pl.col("claim_type") == "koruyucu")
print("koruyucu claims content:", kor.group_by("claim_id").agg(pl.col("procedure_name")).with_columns(sid("claim_id")).to_dicts())

print("\n-- bed lines")
bed = L.filter(pl.col("procedure_category") == "yatak")
print("yatak lines by code/name/chapter/claim_type:")
print(bed.group_by("procedure_code", "procedure_name", "chapter", "claim_type").agg(pl.len().alias("lines"), pl.col("quantity").sum().alias("qty")).sort("lines", descending=True))
print("yatak lines whose code is NOT in SUT ch.1 (bed tariffs):", bed.filter(pl.col("chapter") != "1").height, "/", bed.height)
print("bed codes from ch.1 billed as non-yatak category:", L.filter((pl.col("chapter") == "1") & (pl.col("procedure_category") != "yatak")).height)
yat = C.filter(pl.col("claim_type") == "yatis")
bq = bed.group_by("claim_id").agg(pl.col("quantity").sum().alias("bed_qty"), pl.col("procedure_code").unique().alias("bed_codes"))
yb = yat.select("claim_id", "los_nights", "department", "primary_icd10").join(bq, on="claim_id", how="left")
print("yatis claims:", yat.height, "| with any yatak line:", yb.filter(pl.col("bed_qty").is_not_null()).height,
      "| without:", yb.filter(pl.col("bed_qty").is_null()).height, yb.filter(pl.col("bed_qty").is_null()).select(sid("claim_id"), "los_nights").to_dicts())
yb2 = yb.filter(pl.col("bed_qty").is_not_null()).with_columns((pl.col("bed_qty") - pl.col("los_nights")).alias("qty_minus_los"))
print("bed qty == LOS nights:", yb2.filter(pl.col("qty_minus_los") == 0).height, "| == LOS+1:", yb2.filter(pl.col("qty_minus_los") == 1).height,
      "| qty > LOS+1:", yb2.filter(pl.col("qty_minus_los") > 1).height, "| qty < LOS:", yb2.filter(pl.col("qty_minus_los") < 0).height, "of", yb2.height)
print(yb2.select(sid("claim_id"), "los_nights", "bed_qty", "qty_minus_los", "bed_codes").sort("qty_minus_los"))
gd = bed.filter((pl.col("procedure_code") == "510120") & (pl.col("los_nights") >= 1))
print("510120 'Gündüz yatak' (catalog: day-case/<24h only) on stays >=1 night:", gd.height, "lines; LOS:", gd["los_nights"].to_list())
nb = bed.filter(pl.col("procedure_code") == "612070")
print("612070 'Tırnak yatak revizyonu, her biri' (catalog ch.", nb["chapter"].unique().to_list(), ") used as bed-day:", nb.height, "lines, qty sum", nb["quantity"].sum(), "billed", round(nb["billed_amount_try"].sum(), 2))
er = bed.filter(pl.col("procedure_code") == "530000")
print("530000 'Acil serviste kritik hasta yatak' on yatis claims:", er.select(sid("claim_id"), "department", "quantity").to_dicts())

print("\n-- ICU")
icu_codes = ["510090", "P552001", "P552002", "P552003", "P552006", "P552007", "P552008"]
print("ICU lines (510090, P552001-3, P552006-8):", L.filter(pl.col("procedure_code").is_in(icu_codes)).height)
crit = L.filter(pl.col("procedure_code").is_in(["605975", "605968"]))
print("ECMO/VAD lines (need ICU):", crit.select(sid("procedure_line_id").alias("line"), "claim_type", "department", "procedure_name").to_dicts())
crit_dx = C.filter(pl.col("primary_icd10").is_in(["J96.0", "I21.4", "C92.0", "I63.9"]))
print("claims with primary J96.0/I21.4/C92.0/I63.9 by type:", crit_dx.group_by("primary_icd10", "claim_type").len().sort("primary_icd10").to_dicts())

print("\n-- anaesthesia")
an = L.filter((pl.col("chapter") == "5") | (pl.col("procedure_code") == "520070"))
print("anaesthesia-type lines (ch.5 + 520070):", an.group_by("procedure_code", "procedure_name", "procedure_category").len().sort("len", descending=True).to_dicts())
has_surg = L.group_by("claim_id").agg(pl.col("is_surgical").any().alias("has_surg"),
                                      (pl.col("is_surgical") & (pl.col("code_kind") != "EK-2C_P") & ~pl.col("is_package_included")).any().alias("has_ffs_surg"),
                                      pl.col("procedure_code").is_in(["550130","550140","550150","550160","550170","550180","550190","550200","550210","550220","550230","550240","550250","550260"]).any().alias("has_anaes_group"))
an_claims = an.select("claim_id").unique().join(has_surg, on="claim_id")
print("claims with anaesthesia-type line:", an_claims.height, "| of which no surgery at all:", an_claims.filter(~pl.col("has_surg")).height,
      an_claims.filter(~pl.col("has_surg")).select(sid("claim_id")).to_series().to_list())
fs = has_surg.filter("has_ffs_surg")
print("claims with fee-for-service 6.x surgery:", fs.height, "| with an anaesthesia group line (550130-550260):", fs.filter("has_anaes_group").height)

print("\n-- günübirlik with major surgery")
gb = L.filter((pl.col("claim_type") == "gunubirlik") & pl.col("is_surgical") & pl.col("surg_group").is_in(["A1", "A2", "A3"]))
print("gunubirlik claims with A1-A3 operation:", gb["claim_id"].n_unique(), "/", C.filter(pl.col("claim_type") == "gunubirlik").height)
print(gb.select(sid("procedure_line_id").alias("line"), "department", "primary_icd10", "surg_group", "procedure_name"))
per.write_parquet(f"{OUT}/per_claim_chapters.parquet")
