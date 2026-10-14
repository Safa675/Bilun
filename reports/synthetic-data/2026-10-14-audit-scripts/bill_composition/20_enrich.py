"""Enrich every synthetic procedure line with: header fields, SUT chapter (raw EK-2B headings),
catalog name/description at the line date, EK-2C surgical group, puan-derived surgical group,
patient age/sex (anadata_clean via episode_id).  Read-only on the repo; writes to scratch only."""
import polars as pl

R = "/home/safa/Documents/Bilun/data/synthetic/sut"
G = "/home/safa/Documents/Bilun/data/gazette/curated"
OUT = "/tmp/claude-1000/-home-safa-Documents-Bilun/a9cf6beb-cd1a-4613-ab9e-bddecbe1db1a/scratchpad/audit/bill_composition"

h = pl.read_parquet(f"{R}/claims/claim_headers.parquet")
p = pl.read_parquet(f"{R}/claims/procedure_claim_lines.parquet")
a = pl.read_parquet(f"{R}/clean/anadata_clean.parquet").select(
    pl.col("SQ_EPISODE").alias("episode_id"), pl.col("TANI_YASI").alias("age"), pl.col("CINSIYET").alias("sex"))
chap = pl.read_parquet(f"{OUT}/ref_ek2b_code_chapter.parquet").select("code", "chapter", "chapter_title")
allsnap = pl.read_parquet(f"{OUT}/ref_ek2b_code_chapter_all_snapshots.parquet")
ek2b = pl.read_parquet(f"{G}/ek2b_catalog_history.parquet")
ek2c = pl.read_parquet(f"{G}/ek2c_catalog_history.parquet")

# ---- header-derived fields
hd = h.with_columns(
    pl.col("admission_date").str.to_date(strict=False).alias("adm"),
    pl.col("discharge_date").str.to_date(strict=False).alias("dis"),
    pl.col("claim_start_date").str.to_date().alias("cstart"),
    pl.col("claim_end_date").str.to_date().alias("cend"),
).with_columns(
    (pl.col("dis") - pl.col("adm")).dt.total_days().alias("los_nights"),
).join(a, on="episode_id", how="left")

# ---- line base
L = p.with_columns(
    pl.col("procedure_date").str.to_date().alias("pdate"),
    pl.col("procedure_code").str.slice(0, 1).alias("prefix1"),
).with_columns(
    pl.when(pl.col("procedure_code").str.contains(r"^P\d{6}$")).then(pl.lit("EK-2C_P"))
      .when(pl.col("procedure_code").str.contains(r"^L\d{6}$")).then(pl.lit("L_lab"))
      .when(pl.col("procedure_code").str.contains(r"^G\d{6}$")).then(pl.lit("G_genetic"))
      .when(pl.col("procedure_code").str.contains(r"^R\d{6}$")).then(pl.lit("R_radiology"))
      .when(pl.col("procedure_code").str.contains(r"^\d{6}$")).then(pl.lit("numeric6"))
      .otherwise(pl.lit("other")).alias("code_kind"),
    # base EK-2B code: P-packages map to the EK-2B operation with the same digits
    pl.when(pl.col("procedure_code").str.contains(r"^P\d{6}$")).then(pl.col("procedure_code").str.slice(1))
      .otherwise(pl.col("procedure_code")).alias("base_code"),
)
L = L.join(hd.select("claim_id", "claim_type", "facility_tier", "provider_type", "department", "primary_icd10",
                     "adm", "dis", "cstart", "cend", "los_nights", "age", "sex", "package_candidate", "scenario_tag"),
           on="claim_id", how="left")
L = L.join(chap.rename({"code": "base_code"}), on="base_code", how="left")
L = L.with_columns(
    pl.col("chapter").str.starts_with("6.").fill_null(False).alias("is_surgical"),
)

# ---- EK-2B catalog row valid at the line date (puan, catalog name)
ek2b_d = ek2b.with_columns(pl.col("valid_from").str.to_date(), pl.col("valid_to").str.to_date())
cand = L.select("procedure_line_id", "base_code", "pdate").join(
    ek2b_d.select(pl.col("code").alias("base_code"), pl.col("name").alias("ek2b_name"), pl.col("puan").alias("ek2b_puan"),
                  "valid_from", "valid_to"), on="base_code", how="left")
cand = cand.filter((pl.col("valid_from") <= pl.col("pdate")) & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= pl.col("pdate"))))
cand = cand.sort("valid_from").group_by("procedure_line_id").last().select("procedure_line_id", "ek2b_name", "ek2b_puan")
L = L.join(cand, on="procedure_line_id", how="left")
# any-date EK-2B presence
L = L.with_columns(pl.col("base_code").is_in(ek2b["code"].unique().implode()).alias("in_ek2b_any_date"))

# ---- EK-2C row valid at the line date for P + base_code (surgical group of the operation)
ek2c_d = ek2c.with_columns(pl.col("valid_from").str.to_date(), pl.col("valid_to").str.to_date())
L = L.with_columns(("P" + pl.col("base_code")).alias("p_equiv"))
cc = L.select("procedure_line_id", "p_equiv", "pdate").join(
    ek2c_d.select(pl.col("package_code").alias("p_equiv"), pl.col("name").alias("ek2c_name"), pl.col("group").alias("ek2c_group"),
                  pl.col("price_try").alias("ek2c_price"), "valid_from", "valid_to"), on="p_equiv", how="left")
cc_valid = cc.filter((pl.col("valid_from") <= pl.col("pdate")) & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= pl.col("pdate"))))
cc_valid = cc_valid.sort("valid_from").group_by("procedure_line_id").last().select("procedure_line_id", "ek2c_name", "ek2c_group", "ek2c_price")
L = L.join(cc_valid, on="procedure_line_id", how="left")
L = L.with_columns(pl.col("p_equiv").is_in(ek2c["package_code"].unique().implode()).alias("p_equiv_in_ek2c_any_date"))

# ---- puan-derived surgical group (EK-2B chapter 4 thresholds; changed by RG 05/08/2024, in force 07/08/2024)
pre = [(12001, "A1"), (5201, "A2"), (2351, "A3"), (1451, "B"), (751, "C"), (301, "D"), (0, "E")]
post = [(32561, "A1"), (15401, "A2"), (7584, "A3"), (5001, "B"), (2501, "C"), (943, "D"), (0, "E")]
def grp(th):
    e = pl.lit(None, dtype=pl.Utf8)
    for lo, g in reversed(th):
        e = pl.when(pl.col("ek2b_puan") >= lo).then(pl.lit(g)).otherwise(e)
    return e
cut = pl.date(2024, 8, 7)
L = L.with_columns(
    pl.when(~pl.col("is_surgical") | pl.col("ek2b_puan").is_null()).then(None)
      .when(pl.col("pdate") >= cut).then(grp(post)).otherwise(grp(pre)).alias("puan_group"))
L = L.with_columns(pl.coalesce("ek2c_group", "puan_group").alias("surg_group"))
L = L.with_columns(
    (pl.col("is_surgical") & pl.col("surg_group").is_in(["A1", "A2", "A3", "B"])).alias("is_major_surgery"))

# ---- raw description at the line date (latest snapshot <= date; non-MULGA preferred on ties)
snap = allsnap.filter(pl.col("snapshot") != "unknown").with_columns(pl.col("snapshot").str.to_date().alias("sdate"))
dd = L.select("procedure_line_id", "base_code", "pdate").join(
    snap.select(pl.col("code").alias("base_code"), "sdate", "mulga", "raw_desc", "raw_name"), on="base_code", how="left"
).filter(pl.col("sdate") <= pl.col("pdate")).sort(["sdate", "mulga"], descending=[False, True]).group_by("procedure_line_id").last()
L = L.join(dd.select("procedure_line_id", pl.col("raw_desc").alias("cat_desc"), pl.col("raw_name").alias("raw_name_at_date")),
           on="procedure_line_id", how="left")

L.write_parquet(f"{OUT}/enriched_lines.parquet")
hd.write_parquet(f"{OUT}/enriched_claims.parquet")

print("lines", L.height, "claims", L["claim_id"].n_unique())
print("code_kind:", L["code_kind"].value_counts().sort("count", descending=True).to_dicts())
print("unmapped chapter lines:", L.filter(pl.col("chapter").is_null()).height)
print(L.filter(pl.col("chapter").is_null()).select("procedure_line_id", "procedure_code", "procedure_name", "procedure_category").to_dicts())
print("no EK-2B row valid at date:", L.filter(pl.col("ek2b_puan").is_null()).height,
      L.filter(pl.col("ek2b_puan").is_null()).group_by("code_kind").len().to_dicts())
print("surgical lines:", L.filter("is_surgical").height, " major (A1-B):", L.filter("is_major_surgery").height)
agree = L.filter(pl.col("is_surgical") & pl.col("ek2c_group").is_not_null() & pl.col("puan_group").is_not_null())
print("EK-2C group vs puan-derived group agreement on surgical lines:",
      agree.filter(pl.col("ek2c_group") == pl.col("puan_group")).height, "/", agree.height)
print(agree.filter(pl.col("ek2c_group") != pl.col("puan_group")).select("procedure_code", "ek2b_puan", "pdate", "ek2c_group", "puan_group").to_dicts())
