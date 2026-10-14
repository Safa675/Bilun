"""(d) Quantities, unit prices, sentinel / round prices, arithmetic, payable vs billed, cohort share.

Needs identity.parquet (20_identity.py) for as-of / latest / curated prices.
"""
import os

import polars as pl

from common import B, HERE, load

pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_rows(60)
pl.Config.set_fmt_str_lengths(50)
pl.Config.set_tbl_width_chars(240)

m, p, h, a, cp = load()
d = pl.read_parquet(B + "drug_claim_lines.parquet")
idn = pl.read_parquet(os.path.join(HERE, "identity.parquet")).select(
    "material_line_id", "asof_date", "asof_price", "latest_price", "cur_price", "ratio_vs_asof", "identity_class")
x = m.select("material_line_id", "claim_id", "material_code", "material_name", "quantity", "unit_price_try",
             "billed_amount_try", "expected_payable_try", "is_bundled").join(idn, on="material_line_id", how="left")

print("[d] quantity distribution:", x.group_by("quantity").len().rows())
print("[d] billed == unit*qty (±0.005):", (x["billed_amount_try"] - x["unit_price_try"] * x["quantity"]).abs().lt(0.005).sum(), "/", x.height)
x = x.with_columns(
    pl.when(pl.col("expected_payable_try").abs() < 0.005).then(pl.lit("0"))
    .when((pl.col("expected_payable_try") - pl.col("billed_amount_try")).abs() < 0.005).then(pl.lit("=billed"))
    .otherwise(pl.lit("partial")).alias("payable_vs_billed"))
print("[d] payable vs billed:", x.group_by("payable_vs_billed", "is_bundled").len().sort("payable_vs_billed").rows())

# round / sentinel prices that do NOT equal a catalogue price
cat_eq = pl.any_horizontal([(pl.col("unit_price_try") - pl.col(c).round(2)).abs() < 0.006
                            for c in ("asof_price", "latest_price", "cur_price")]).fill_null(False)
x = x.with_columns(
    (pl.col("unit_price_try") % 1 == 0).alias("integer_price"),
    (pl.col("unit_price_try") % 100 == 0).alias("multiple_of_100"),
    # rust regex has no back-references: alternation over the ten digits (>=4 identical digits)
    pl.col("unit_price_try").cast(pl.Int64).cast(pl.Utf8).str.contains(
        "^(" + "|".join(f"{d}{{4,}}" for d in range(10)) + ")$").alias("repdigit"),
    cat_eq.alias("equals_some_catalog_price"))
sus = x.filter((pl.col("integer_price") | pl.col("repdigit")) & ~pl.col("equals_some_catalog_price"))
print("\n[d] integer-valued unit prices:", x["integer_price"].sum(), "| of which equal no EK-3 catalogue price:", sus.height)
print(sus.select(pl.col("material_line_id").str.replace("MLZ-F-SENTETIK-HASTA-", ""), "material_code", "material_name",
                 "unit_price_try", "asof_price", "latest_price", "identity_class"))

mat_total = m["billed_amount_try"].sum()
proc_total = p["billed_amount_try"].sum()
drug_total = d["billed_amount_try"].sum()
hdr_total = h["expected_total_billed_try"].sum()
s = m.filter(pl.col("unit_price_try") == 999999.0)
print(f"\n[d] 999,999 TRY sentinel lines: {s.height} -> {s['material_line_id'].to_list()}")
print(f"    material billed total {mat_total:,.2f} | procedures {proc_total:,.2f} | drugs {drug_total:,.2f} | "
      f"sum of lines {mat_total + proc_total + drug_total:,.2f} | sum of claim headers {hdr_total:,.2f}")
print(f"    sentinel share of material billed: {999999 / mat_total:.1%} | of claim-header billed total: {999999 / hdr_total:.1%}")
cl = h.filter(pl.col("claim_id") == "F-SENTETIK-HASTA-0023-037").select("claim_id", "claim_type", "department",
                                                                        "expected_total_billed_try", "expected_total_payable_try")
print("    claim 0023-037 header:", cl.rows())
print(f"    real ICD list prices (EK-3H KR1000-KR1012, as-of 2023-08-30 snapshot, see 20_identity notes): 48,510.00 - 90,956.25 TRY;"
      f" sentinel = {999999 / 90956.25:.1f}x the dearest ICD; OP1592 as-of (EK-3C-2 2024-08-23) price = 83,300 TRY")
top = m.sort("billed_amount_try", descending=True).head(5).select(
    pl.col("material_line_id").str.replace("MLZ-F-SENTETIK-HASTA-", ""), "material_code", "billed_amount_try")
print("    top-5 material lines by billed:", top.rows())
print(f"    material billed excl. sentinel: {mat_total - 999999:,.2f}")

# as-of excess (catalogue price in force on material_date vs billed)
ex = x.filter(pl.col("asof_price").is_not_null())
print(f"\n[d] lines with an as-of EK-3 price: {ex.height}; billed above it: {(ex['ratio_vs_asof'] > 1.0001).sum()}; "
      f"below: {(ex['ratio_vs_asof'] < 0.9999).sum()}")
print("    ratio unit/as-of by as-of snapshot:", ex.group_by("asof_date").agg(
    pl.len(), pl.col("ratio_vs_asof").min().alias("min"), pl.col("ratio_vs_asof").median().alias("med"),
    pl.col("ratio_vs_asof").max().alias("max")).sort("asof_date").rows())
nos = ex.filter(pl.col("unit_price_try") != 999999.0)
print(f"    excess over as-of price, excl. sentinel: {(nos['unit_price_try'] - nos['asof_price']).sum():,.2f} TRY "
      f"on {nos.height} lines ({(nos['unit_price_try'] - nos['asof_price']).sum() / nos['asof_price'].sum():.1%} above as-of)")
print("    unit price == latest curated (2025-12/2026-01) price:", x.filter(
    (pl.col("unit_price_try") - pl.col("cur_price").round(2)).abs() < 0.006).height, "/", x.height,
      "| == as-of price:", x.filter((pl.col("unit_price_try") - pl.col("asof_price").round(2)).abs() < 0.006).height)
lat = x.filter((pl.col("unit_price_try") - pl.col("latest_price")).abs() <= 0.0051)  # half-cent rounding tolerance
print("    unit price == latest dated raw snapshot price (2025-12-13 / 2026-01-24):", lat.height, "/", x.height,
      "| exceptions:", x.join(lat.select("material_line_id"), on="material_line_id", how="anti")
      .select("material_line_id", "material_code", "unit_price_try", "latest_price").rows())
