"""(a) Procedure unit prices vs the as-of SUT list price (EK-2B / EK-2C).

Outputs:
  out/a_price_lines.parquet  one row per procedure line with as-of list price,
                             ratio, the version(s) the unit price matches.
Prints the distribution summary used in the report.
"""
from common import *

p = claims("procedure_claim_lines")
cat = catalog_versions()

print("procedure lines:", p.height)
print("unit_price_try null:", p["unit_price_try"].null_count(),
      " <=0:", p.filter(pl.col("unit_price_try") <= 0).height)

# --- code-convention check: does every cohort code exist in the catalog? ---
codes = p.select("procedure_code").unique()
in_b = codes.join(cat.filter(pl.col("annex") == "EK-2B").select("code").unique(),
                  left_on="procedure_code", right_on="code", how="semi")
in_c = codes.join(cat.filter(pl.col("annex") == "EK-2C").select("code").unique(),
                  left_on="procedure_code", right_on="code", how="semi")
print(f"distinct cohort codes: {codes.height}; in EK-2B: {in_b.height}; in EK-2C: {in_c.height}")
missing = codes.join(cat.select("code").unique(), left_on="procedure_code", right_on="code", how="anti")
print("codes absent from both catalogs:", missing["procedure_code"].to_list())

# --- as-of join ---
a = asof_join(p, "procedure_code", "procedure_date")
print("as-of ambiguity (>1 distinct price in force):",
      a.filter(pl.col("n_distinct_asof_prices") > 1).height)
a = a.with_columns(
    (pl.col("unit_price_try") / pl.col("list_price_try")).alias("ratio_asof"),
    # name agreement with catalog (normalised casefold prefix)
    (pl.col("procedure_name").str.to_lowercase().str.slice(0, 25)
     == pl.col("list_name").str.to_lowercase().str.slice(0, 25)).alias("name_prefix_match"),
)
priced = a.filter(pl.col("unit_price_try") > 0)
print("priced lines (unit>0):", priced.height,
      " with as-of list price:", priced.filter(pl.col("list_price_try").is_not_null()).height,
      " no as-of price:", priced.filter(pl.col("list_price_try").is_null()).height)
nl = priced.filter(pl.col("list_price_try").is_null())
if nl.height:
    print(nl.select("procedure_line_id", "procedure_date", "procedure_code", "procedure_name",
                    "procedure_category", "unit_price_try"))

cmp = priced.filter(pl.col("list_price_try").is_not_null() & (pl.col("list_price_try") > 0))
r = cmp["ratio_asof"]
print(f"\nRATIO unit/as-of list over {cmp.height} lines: min={r.min():.3f} "
      f"p10={r.quantile(0.10):.3f} median={r.median():.3f} p90={r.quantile(0.90):.3f} max={r.max():.3f}")
at = cmp.filter((pl.col("ratio_asof") - 1).abs() <= 0.01).height
above = cmp.filter(pl.col("ratio_asof") > 1.01).height
below = cmp.filter(pl.col("ratio_asof") < 0.99).height
print(f"at list (+-1%): {at}; above: {above}; below: {below}")
print("\nby category:")
print(cmp.group_by("procedure_category").agg(
    pl.len().alias("n"),
    pl.col("ratio_asof").min().alias("min"),
    pl.col("ratio_asof").median().alias("median"),
    pl.col("ratio_asof").max().alias("max"),
    ((pl.col("ratio_asof") - 1).abs() <= 0.01).sum().alias("at_list"),
).sort("procedure_category"))
print("\nby year of service:")
print(cmp.group_by(pl.col("procedure_date").str.slice(0, 4).alias("yr")).agg(
    pl.len().alias("n"), pl.col("ratio_asof").median().alias("median"),
    ((pl.col("ratio_asof") - 1).abs() <= 0.01).sum().alias("at_list")).sort("yr"))
print("\nname mismatch vs catalog (first 25 chars) among matched lines:",
      cmp.filter(~pl.col("name_prefix_match")).height)

# --- which catalog version would the unit price match? ---
allv = (
    a.filter(pl.col("unit_price_try") > 0)
    .select("procedure_line_id", "procedure_code", "procedure_date", "unit_price_try")
    .join(cat.select("code", "price_try", "valid_from", "valid_to"),
          left_on="procedure_code", right_on="code", how="inner")
    .with_columns(((pl.col("unit_price_try") / pl.col("price_try") - 1).abs() <= 0.005).alias("hit"))
)
hits = allv.filter(pl.col("hit"))
by_line = hits.group_by("procedure_line_id").agg(
    pl.col("valid_from").min().alias("first_matching_version"),
    pl.col("valid_from").max().alias("last_matching_version"),
    pl.col("valid_to").is_null().any().alias("matches_current_list"),
)
print("\nlines whose unit price equals (+-0.5%) SOME catalog version of that code:",
      by_line.height, "of", cmp.height)
print("of those, matching the open-ended current list (valid_to null):",
      by_line.filter(pl.col("matches_current_list")).height)
print(by_line.group_by("first_matching_version").len().sort("first_matching_version"))

# current-list ratio
cur = cat.filter(pl.col("valid_to").is_null()).select("code", pl.col("price_try").alias("cur_price"),
                                                      pl.col("valid_from").alias("cur_from"))
a = a.join(cur, left_on="procedure_code", right_on="code", how="left").with_columns(
    (pl.col("unit_price_try") / pl.col("cur_price")).alias("ratio_current"))
cc = a.filter((pl.col("unit_price_try") > 0) & pl.col("cur_price").is_not_null())
print(f"\nRATIO unit/CURRENT list (open-ended row) over {cc.height}: "
      f"median={cc['ratio_current'].median():.4f}; at +-1%: "
      f"{cc.filter((pl.col('ratio_current') - 1).abs() <= 0.01).height}")
print("current-list version start dates of matched codes:", cc["cur_from"].value_counts().sort("cur_from").rows())

# lines NOT at current list: what are they?
nc = cc.filter((pl.col("ratio_current") - 1).abs() > 0.01)
print("\nlines not at current list:", nc.height)
print(nc.select("procedure_line_id", "procedure_date", "procedure_code", "procedure_category",
                "unit_price_try", "cur_price", "list_price_try", "ratio_current", "ratio_asof").sort("ratio_current"))

# top inflation examples vs as-of
print("\nTop 10 ratio_asof:")
print(cmp.sort("ratio_asof", descending=True).select(
    "procedure_line_id", "procedure_date", "procedure_code", "procedure_name", "unit_price_try",
    "list_price_try", "list_valid_from", "ratio_asof").head(10))
print("\nLines at as-of list (+-1%):")
print(cmp.filter((pl.col("ratio_asof") - 1).abs() <= 0.01).select(
    "procedure_line_id", "procedure_date", "procedure_code", "procedure_category", "unit_price_try",
    "list_price_try", "list_valid_from"))

a.write_parquet(OUT / "a_price_lines.parquet")

# ratio as a step function of the as-of list version (=> stamped with one later list)
print("\nratio unit/as-of by as-of list version (lines at current list only):")
st = a.filter((pl.col("unit_price_try") > 0) & pl.col("list_price_try").is_not_null()
              & ((pl.col("ratio_current") - 1).abs() <= 0.01))
print(st.group_by("list_valid_from").agg(pl.len().alias("n"), pl.col("ratio_asof").median().round(3).alias("median"),
                                         pl.col("ratio_asof").quantile(0.1).round(3).alias("p10"),
                                         pl.col("ratio_asof").quantile(0.9).round(3).alias("p90")).sort("list_valid_from"))
print("example 510010 lines:", a.filter(pl.col("procedure_code") == "510010").select(
    "procedure_line_id", "procedure_date", "unit_price_try", "list_price_try").sort("procedure_date").head(4).rows())
