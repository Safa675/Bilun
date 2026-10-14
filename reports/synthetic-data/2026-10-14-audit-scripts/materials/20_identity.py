"""(a) Material identity vs EK-3 snapshots + (d) price vs as-of list price.

Needs ek3_index.parquet from 10_build_ek3_index.py. Writes identity.parquet (scratchpad).
As-of rule: for each annex that ever lists the code, take the latest dated snapshot whose
effective_date <= material_date ('unknown'-dated files are excluded from as-of, kept for 'ever listed').
"""
import glob
import os

import polars as pl

from common import CUR, HERE, load, norm_expr

pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_rows(100)
pl.Config.set_fmt_str_lengths(70)
pl.Config.set_tbl_width_chars(260)

m, p, h, a, cp = load()
idx = pl.read_parquet(os.path.join(HERE, "ek3_index.parquet"))
lines = m.select("material_line_id", "claim_id", "material_date", "material_code", "material_name",
                 "material_type", "specialty_category", "unit_price_try", "quantity")

# ---- every annex that ever lists the code (any snapshot, incl. MÜLGA / unknown-dated)
ever = idx.group_by("code").agg(pl.col("annex").unique().sort().alias("annexes_ever"),
                                pl.col("effective_date").min().alias("first_seen"),
                                pl.col("effective_date").filter(pl.col("effective_date") != "unknown").max().alias("last_seen"))

# ---- as-of snapshot per (line, annex)
c1 = idx.filter(pl.col("annex") == "EK-3C-1")          # 'tıbbi uygunluk aranacak' list: codes, no prices
idx = idx.filter(pl.col("annex") != "EK-3C-1")         # priced / descriptive annexes only
snaps = idx.filter(pl.col("effective_date") != "unknown").select("annex", "effective_date").unique()
code_annex = idx.select("code", "annex").unique()
asof_date = (
    lines.join(code_annex, left_on="material_code", right_on="code", how="inner")
    .join(snaps, on="annex")
    .filter(pl.col("effective_date") <= pl.col("material_date"))
    .group_by("material_line_id", "annex").agg(pl.col("effective_date").max().alias("asof_date"))
)
idx_agg = idx.group_by("code", "annex", "effective_date").agg(
    pl.col("primary_name").drop_nulls().first(), pl.col("full_name").drop_nulls().first(),
    pl.col("price").drop_nulls().first().alias("price"), pl.col("price").drop_nulls().n_unique().alias("n_prices"),
)
asof = (
    asof_date.join(lines.select("material_line_id", "material_code"), on="material_line_id")
    .join(idx_agg, left_on=["material_code", "annex", "asof_date"], right_on=["code", "annex", "effective_date"], how="left")
    .rename({"primary_name": "asof_primary", "full_name": "asof_full", "price": "asof_price"})
    .with_columns(pl.col("asof_primary").is_not_null().alias("listed_asof"))
    .sort("material_line_id", "listed_asof", descending=[False, True])
    .unique("material_line_id", keep="first")
    .drop("material_code")
)
latest_date = snaps.group_by("annex").agg(pl.col("effective_date").max().alias("latest_date"))
latest = (
    code_annex.join(latest_date, on="annex")
    .join(idx_agg, left_on=["code", "annex", "latest_date"], right_on=["code", "annex", "effective_date"], how="inner")
    .select("code", pl.col("annex").alias("latest_annex"), "latest_date",
            pl.col("primary_name").alias("latest_primary"), pl.col("full_name").alias("latest_full"),
            pl.col("price").alias("latest_price"))
    .unique("code")
)
# ---- curated parquet = the generator's source (scripts/synthetic/gen/orchestrate.py:76)
cur = pl.concat([
    pl.read_parquet(f).select(pl.col("sut_code").cast(pl.Utf8).str.strip_chars().alias("code"),
                              pl.col("material_name").cast(pl.Utf8).alias("cur_name"),
                              (pl.col("price_try").cast(pl.Float64) if "price_try" in pl.read_parquet_schema(f) else pl.lit(None, pl.Float64)).alias("cur_price"),
                              pl.lit(os.path.basename(f)).alias("cur_file"))
    for f in sorted(glob.glob(CUR + "ek3*_materials.parquet"))
]).unique("code", keep="first")

c1_dates = c1.filter(pl.col("effective_date") != "unknown").select("effective_date").unique()
c1_asof = (
    lines.select("material_line_id", "material_code", "material_date").join(c1_dates, how="cross")
    .filter(pl.col("effective_date") <= pl.col("material_date"))
    .group_by("material_line_id", "material_code").agg(pl.col("effective_date").max().alias("c1_asof_date"))
    .join(c1.select("code", pl.col("effective_date").alias("c1_asof_date"), pl.lit(True).alias("in_ek3c1_asof")).unique(),
          left_on=["material_code", "c1_asof_date"], right_on=["code", "c1_asof_date"], how="left")
    .select("material_line_id", "c1_asof_date", pl.col("in_ek3c1_asof").fill_null(False))
)
ident = (
    lines.join(c1_asof, on="material_line_id", how="left").join(ever, left_on="material_code", right_on="code", how="left")
    .join(asof, on="material_line_id", how="left")
    .join(latest, left_on="material_code", right_on="code", how="left")
    .join(cur, left_on="material_code", right_on="code", how="left")
    .with_columns(
        norm_expr("material_name").alias("k_syn"), norm_expr("asof_primary").alias("k_asof_p"),
        norm_expr("asof_full").alias("k_asof_f"), norm_expr("latest_primary").alias("k_lat_p"),
        norm_expr("latest_full").alias("k_lat_f"),
        pl.col("asof_full").fill_null("").str.split(" | ").list.len().alias("asof_name_parts"),
    )
    .with_columns(
        pl.when(pl.col("annexes_ever").is_null()).then(pl.lit("UNKNOWN_CODE"))
        .when(pl.col("listed_asof").not_()).then(pl.lit("NOT_LISTED_ON_DATE"))
        # EK-3F-x tables: first descriptive column is 'UYGULAMA YERİ' (anatomical site), not the product
        .when((pl.col("k_syn") == pl.col("k_asof_p")) & pl.col("annex").str.starts_with("EK-3F")
              & (pl.col("asof_name_parts") >= 3)).then(pl.lit("NAME=SITE_FIELD_ONLY"))
        .when((pl.col("k_syn") == pl.col("k_asof_p")) | (pl.col("k_syn") == pl.col("k_asof_f"))).then(pl.lit("MATCH_ASOF"))
        .when((pl.col("k_syn") == pl.col("k_lat_p")) | (pl.col("k_syn") == pl.col("k_lat_f"))).then(pl.lit("MATCH_LATEST_ONLY(anachronistic name)"))
        .otherwise(pl.lit("NAME_MISMATCH")).alias("identity_class"),
        (pl.col("unit_price_try") / pl.col("asof_price")).round(4).alias("ratio_vs_asof"),
        (pl.col("unit_price_try") - pl.col("cur_price").round(2)).abs().lt(0.006).alias("price_eq_curated"),
        (pl.col("unit_price_try") - pl.col("asof_price").round(2)).abs().lt(0.006).alias("price_eq_asof"),
    )
)
ident.write_parquet(os.path.join(HERE, "identity.parquet"))

print("lines:", ident.height, "| distinct codes:", ident["material_code"].n_unique())
print("\n[a] code -> annex(es) ever listed:")
print(ident.group_by(pl.col("annexes_ever").list.join(",").fill_null("<none>")).agg(
    pl.len().alias("lines"), pl.col("material_code").unique().sort().alias("codes")).sort("lines", descending=True))
print("\n[a] identity class:")
print(ident.group_by("identity_class").agg(pl.len().alias("lines"),
                                           pl.col("material_code").unique().sort().alias("codes")).sort("lines", descending=True))
print("\n[a] detail for non-clean classes:")
print(ident.filter(pl.col("identity_class") != "MATCH_ASOF").select(
    "material_line_id", "material_date", "material_code", "material_name", "identity_class", "annex", "asof_date",
    "asof_primary", "asof_full", "latest_primary", "first_seen", "last_seen"))
print("\n[a] code->name consistency inside the cohort (same code, >1 name):")
print(ident.group_by("material_code").agg(pl.col("material_name").unique()).filter(pl.col("material_name").list.len() > 1))

print("\n[d] price provenance: unit price == curated(latest) price rounded vs == as-of price rounded")
print(ident.group_by("price_eq_curated", "price_eq_asof").len())
print(ident.filter(pl.col("price_eq_asof").not_() | pl.col("price_eq_asof").is_null()).select(
    "material_line_id", "material_date", "material_code", "unit_price_try", "asof_date", "asof_price", "ratio_vs_asof",
    "latest_date", "latest_price", "cur_price").sort("ratio_vs_asof", nulls_last=True))
print("\n[d] ratio unit/as-of distribution (lines with an as-of price):")
print(ident.filter(pl.col("ratio_vs_asof").is_not_null()).select(
    pl.len().alias("n"), (pl.col("ratio_vs_asof") > 1.0001).sum().alias("above_asof"),
    (pl.col("ratio_vs_asof") < 0.9999).sum().alias("below_asof"),
    pl.col("ratio_vs_asof").min().alias("min"), pl.col("ratio_vs_asof").median().alias("median"),
    pl.col("ratio_vs_asof").max().alias("max")))
over = ident.filter(pl.col("ratio_vs_asof") > 1.0001)
print("billed above as-of list price: lines", over.height, "excess TRY",
      round((over["unit_price_try"] - over["asof_price"]).sum(), 2))
