"""(b) Arithmetic consistency: billed = unit x qty; header totals = sum of lines;
payable <= billed; zero/negative values; package-included lines priced 0.
"""
from common import *

h = claims("claim_headers")
p = claims("procedure_claim_lines")
d = claims("drug_claim_lines")
m = claims("material_claim_lines")

TOL = 0.011  # 1 kurus rounding + float noise


def line_checks(df: pl.DataFrame, kind: str, id_col: str) -> pl.DataFrame:
    df = df.with_columns(
        (pl.col("unit_price_try") * pl.col("quantity")).round(2).alias("unit_x_qty"),
    ).with_columns(
        (pl.col("billed_amount_try") - pl.col("unit_x_qty")).alias("billed_minus_uxq"),
        (pl.col("billed_amount_try") / pl.col("unit_x_qty")).alias("billed_over_uxq"),
        (pl.col("expected_payable_try") / pl.col("unit_x_qty")).alias("payable_over_uxq"),
    )
    n = df.height
    eq = df.filter(pl.col("billed_minus_uxq").abs() <= TOL).height
    hi = df.filter(pl.col("billed_minus_uxq") > TOL).height
    lo = df.filter(pl.col("billed_minus_uxq") < -TOL).height
    pay_gt = df.filter(pl.col("expected_payable_try") > pl.col("billed_amount_try") + TOL)
    pay_eq_uxq = df.filter((pl.col("expected_payable_try") - pl.col("unit_x_qty")).abs() <= TOL).height
    print(f"\n=== {kind}: {n} lines")
    print(f"billed == unit*qty (+-0.01): {eq}; billed > unit*qty: {hi}; billed < unit*qty: {lo}")
    print(f"payable == unit*qty: {pay_eq_uxq}")
    r = df["billed_over_uxq"]
    print(f"billed/(unit*qty): min={r.min():.3f} p10={r.quantile(.1):.3f} median={r.median():.3f} "
          f"p90={r.quantile(.9):.3f} max={r.max():.3f}")
    print(f"payable > billed: {pay_gt.height}")
    if pay_gt.height:
        print(pay_gt.select(id_col, "claim_id", "quantity", "unit_price_try", "billed_amount_try",
                            "expected_payable_try").sort("expected_payable_try", descending=True).head(12))
    for c in ["unit_price_try", "billed_amount_try", "expected_payable_try", "quantity"]:
        print(f"  {c}: null={df[c].null_count()} <0={df.filter(pl.col(c) < 0).height} "
              f"==0={df.filter(pl.col(c) == 0).height}")
    return df


pc = line_checks(p, "procedure", "procedure_line_id")
print("\nprocedure billed/(unit*qty) by category (median, n, n_eq):")
print(pc.group_by("procedure_category").agg(
    pl.len().alias("n"), pl.col("billed_over_uxq").median().alias("med_b_over_uxq"),
    (pl.col("billed_minus_uxq").abs() <= TOL).sum().alias("n_eq"),
    pl.col("payable_over_uxq").median().alias("med_pay_over_uxq"),
).sort("procedure_category"))
print("\nExamples billed < unit*qty (procedure):")
print(pc.filter(pl.col("billed_minus_uxq") < -TOL).select(
    "procedure_line_id", "procedure_code", "quantity", "unit_price_try", "unit_x_qty",
    "billed_amount_try", "expected_payable_try").head(6))
print("\nExamples billed > unit*qty (procedure):")
print(pc.filter(pl.col("billed_minus_uxq") > TOL).sort("billed_over_uxq", descending=True).select(
    "procedure_line_id", "procedure_code", "quantity", "unit_price_try", "unit_x_qty",
    "billed_amount_try", "expected_payable_try").head(6))

dc = line_checks(d, "drug", "drug_claim_line_id")
mc = line_checks(m, "material", "material_line_id")

# package-included procedure lines
inc = p.filter(pl.col("is_package_included"))
print(f"\nis_package_included lines: {inc.height}; billed>0: {inc.filter(pl.col('billed_amount_try') > 0).height}; "
      f"payable>0: {inc.filter(pl.col('expected_payable_try') > 0).height}; unit>0: {inc.filter(pl.col('unit_price_try') > 0).height}")
print(inc.select("procedure_line_id", "procedure_code", "procedure_category", "package_code", "unit_price_try",
                 "billed_amount_try", "expected_payable_try", "denial_reason_expected").head(10))
print("material is_bundled:", m.filter(pl.col("is_bundled")).height,
      " of which payable>0:", m.filter(pl.col("is_bundled") & (pl.col("expected_payable_try") > 0)).height)

# --- header totals vs line sums ---
sums = []
for df, kind in [(p, "proc"), (d, "drug"), (m, "mat")]:
    sums.append(df.group_by("claim_id").agg(
        pl.col("billed_amount_try").sum().alias(f"b_{kind}"),
        pl.col("expected_payable_try").sum().alias(f"p_{kind}"),
        pl.len().alias(f"n_{kind}")))
hh = h.select("claim_id", "claim_type", "facility_tier", "provider_type",
              "expected_total_billed_try", "expected_total_payable_try")
for s in sums:
    hh = hh.join(s, on="claim_id", how="left")
hh = hh.fill_null(0).with_columns(
    (pl.col("b_proc") + pl.col("b_drug") + pl.col("b_mat")).alias("b_lines"),
    (pl.col("p_proc") + pl.col("p_drug") + pl.col("p_mat")).alias("p_lines"),
).with_columns(
    (pl.col("expected_total_billed_try") - pl.col("b_lines")).alias("d_billed"),
    (pl.col("expected_total_payable_try") - pl.col("p_lines")).alias("d_payable"),
)
print("\nheader total billed == sum(proc+drug+mat) (+-0.05):",
      hh.filter(pl.col("d_billed").abs() <= 0.05).height, "/", hh.height)
print("header total payable == sum(proc+drug+mat) (+-0.05):",
      hh.filter(pl.col("d_payable").abs() <= 0.05).height, "/", hh.height)
bad = hh.filter((pl.col("d_billed").abs() > 0.05) | (pl.col("d_payable").abs() > 0.05))
print(bad.select("claim_id", "expected_total_billed_try", "b_lines", "d_billed",
                 "expected_total_payable_try", "p_lines", "d_payable").head(20))
# Try alternatives: proc only, proc+drug, proc+mat
for combo in [["b_proc"], ["b_proc", "b_drug"], ["b_proc", "b_mat"], ["b_drug", "b_mat"]]:
    s = hh.select(pl.sum_horizontal(combo).alias("s"), "expected_total_billed_try")
    print(combo, "match:", s.filter((pl.col("s") - pl.col("expected_total_billed_try")).abs() <= 0.05).height)
print("header payable > header billed:",
      hh.filter(pl.col("expected_total_payable_try") > pl.col("expected_total_billed_try") + 0.01).height)
print("claims with zero lines of all kinds:", hh.filter((pl.col("n_proc") + pl.col("n_drug") + pl.col("n_mat")) == 0).height)
print("lines whose claim_id is not in headers: proc",
      p.join(h, on="claim_id", how="anti").height, "drug", d.join(h, on="claim_id", how="anti").height,
      "mat", m.join(h, on="claim_id", how="anti").height)
print("header patient_id == line patient_id mismatches (proc):",
      p.join(h.select("claim_id", pl.col("patient_id").alias("hp")), on="claim_id")
      .filter(pl.col("patient_id") != pl.col("hp")).height)

tot_b = hh["expected_total_billed_try"].sum()
tot_p = hh["expected_total_payable_try"].sum()
print(f"\nCOHORT header billed={tot_b:,.2f} payable={tot_p:,.2f} gap={tot_b - tot_p:,.2f} "
      f"({(tot_b - tot_p) / tot_b:.2%})")
print(f"line-sum billed={hh['b_lines'].sum():,.2f} payable={hh['p_lines'].sum():,.2f}")
print("by line kind (billed, payable):",
      {k: (round(hh[f"b_{k}"].sum(), 2), round(hh[f"p_{k}"].sum(), 2)) for k in ["proc", "drug", "mat"]})

# --- dates: line dates within claim window ---
hd = h.select("claim_id", "claim_type", "claim_start_date", "claim_end_date", "admission_date", "discharge_date")
pd_ = p.join(hd, on="claim_id").filter((pl.col("procedure_date") < pl.col("claim_start_date"))
                                       | (pl.col("procedure_date") > pl.col("claim_end_date")))
print("\nprocedure lines dated outside claim window:", pd_.height)
dd_ = d.join(hd, on="claim_id").filter((pl.col("drug_claim_date") < pl.col("claim_start_date"))
                                       | (pl.col("drug_claim_date") > pl.col("claim_end_date")))
print("drug lines dated outside claim window:", dd_.height)
md_ = m.join(hd, on="claim_id").filter((pl.col("material_date") < pl.col("claim_start_date"))
                                       | (pl.col("material_date") > pl.col("claim_end_date")))
print("material lines dated outside claim window:", md_.height)
# inpatient: LOS vs bed-day quantity
hd2 = h.with_columns(
    (pl.col("claim_end_date").str.to_date() - pl.col("claim_start_date").str.to_date()).dt.total_days().alias("span_days"))
print("\nclaim span days by claim_type:")
print(hd2.group_by("claim_type").agg(pl.len(), pl.col("span_days").min().alias("min"),
                                     pl.col("span_days").median().alias("med"), pl.col("span_days").max().alias("max")))
beds = p.filter(pl.col("procedure_code").is_in(["510010", "510120", "510090", "510100", "510070", "530000"])) \
    .join(hd2.select("claim_id", "claim_type", "span_days"), on="claim_id")
print("bed-day lines (51xxxx/530000) vs claim span:")
print(beds.select("procedure_line_id", "claim_type", "procedure_code", "procedure_name", "quantity", "span_days").sort("quantity", descending=True))
yatak = p.filter(pl.col("procedure_category") == "yatak").join(hd2.select("claim_id", "claim_type", "span_days"), on="claim_id")
print("category=='yatak' lines that are NOT 51xxxx bed codes:")
print(yatak.filter(~pl.col("procedure_code").str.starts_with("51")).select(
    "procedure_line_id", "claim_type", "procedure_code", "procedure_name", "quantity", "billed_amount_try", "span_days"))

hh.write_parquet(OUT / "b_header_vs_lines.parquet")
pc.write_parquet(OUT / "b_proc_lines.parquet")
