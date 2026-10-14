"""(h) Magnitudes: claim totals by claim type vs the as-of SUT value of the same
lines; composition of outpatient claims; ICU presence (anchor: ICU tiering ~81%
of real deductions); gap vs the TUSEB anchor (1.72% / 0.13%).
"""
from common import *

h = claims("claim_headers")
p = pl.read_parquet(OUT / "a_price_lines.parquet")  # has list_price_try (as-of) per procedure line
d = claims("drug_claim_lines")
m = claims("material_claim_lines")

p = p.with_columns(
    (pl.col("list_price_try") * pl.col("quantity")).alias("asof_value"),
    pl.col("procedure_code").str.slice(0, 6).alias("c6"),
)
# surgical EK-2B range 600000-619999 (catalog's own _categorize_code: 'surgery')
p = p.with_columns(
    (pl.col("procedure_code").str.contains(r"^6[01]\d{4}$")).alias("is_surgery_code"),
)
proc = p.group_by("claim_id").agg(
    pl.len().alias("n_proc"),
    pl.col("billed_amount_try").sum().alias("proc_billed"),
    pl.col("asof_value").sum().alias("proc_asof_value"),
    pl.col("list_price_try").is_null().sum().alias("n_no_asof"),
    pl.col("is_surgery_code").sum().alias("n_surgery"),
    (pl.col("procedure_category") == "laboratuvar").sum().alias("n_lab"),
    (pl.col("procedure_category") == "muayene").sum().alias("n_muayene"),
)
drug = d.group_by("claim_id").agg(pl.len().alias("n_drug"), pl.col("billed_amount_try").sum().alias("drug_billed"))
mat = m.group_by("claim_id").agg(pl.len().alias("n_mat"), pl.col("billed_amount_try").sum().alias("mat_billed"))
c = h.select("claim_id", "claim_type", "provider_type", "scenario_tag", "expected_total_billed_try",
             "expected_total_payable_try", "claim_start_date", "claim_end_date") \
    .join(proc, on="claim_id", how="left").join(drug, on="claim_id", how="left").join(mat, on="claim_id", how="left") \
    .fill_null(0)
c = c.with_columns((pl.col("proc_billed") / pl.col("proc_asof_value")).alias("proc_billed_over_asof"))
print("procedure billed vs as-of SUT value of the same lines (claim level):")
print(c.group_by("claim_type").agg(
    pl.len().alias("n"),
    pl.col("proc_billed").sum().round(0).alias("proc_billed"),
    pl.col("proc_asof_value").sum().round(0).alias("proc_asof"),
    pl.col("proc_billed_over_asof").median().round(2).alias("median_ratio"),
    pl.col("expected_total_billed_try").median().round(0).alias("median_claim_billed"),
    pl.col("n_proc").median().alias("med_proc_lines"),
    pl.col("n_drug").median().alias("med_drug_lines"),
    pl.col("n_mat").median().alias("med_mat_lines"),
    pl.col("n_surgery").sum().alias("surgery_lines"),
    (pl.col("n_surgery") > 0).sum().alias("claims_with_surgery"),
    (pl.col("n_mat") > 0).sum().alias("claims_with_material"),
).sort("n", descending=True))
tot_b = p["billed_amount_try"].sum()
tot_v = p["asof_value"].sum()
print(f"cohort procedure billed {tot_b:,.2f} vs as-of SUT value {tot_v:,.2f} (ratio {tot_b / tot_v:.2f})")

# outpatient (poliklinik) composition
po = c.filter(pl.col("claim_type") == "poliklinik")
print("\npoliklinik claims:", po.height, " median lines (proc/drug/mat):",
      po["n_proc"].median(), po["n_drug"].median(), po["n_mat"].median(),
      " with >=1 surgical (60xxxx/61xxxx) line:", po.filter(pl.col("n_surgery") > 0).height,
      " with >=1 material line:", po.filter(pl.col("n_mat") > 0).height)
print("poliklinik billed quantiles:", [round(po["expected_total_billed_try"].quantile(q), 0) for q in (0.1, 0.25, 0.5, 0.75, 0.9)])
print("poliklinik as-of value of procedure lines quantiles:", [round(po["proc_asof_value"].quantile(q), 0) for q in (0.1, 0.25, 0.5, 0.75, 0.9)])
surg_po = p.join(po.select("claim_id"), on="claim_id", how="semi").filter(pl.col("is_surgery_code"))
print("examples of surgical codes on poliklinik claims:")
print(surg_po.select("procedure_line_id", "procedure_code", "procedure_name", "billed_amount_try").head(10))

# as-of anchors for common lines
cat = catalog_versions()
anchors = ["520030", "520080", "520010", "520021", "510010", "510120", "510090"]
print("\nas-of list prices of anchor codes in the cohort window:")
print(cat.filter(pl.col("code").is_in(anchors) & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= "2023-01-01"))
                 & (pl.col("valid_from") <= "2024-12-31")).select("code", "name", "price_try", "valid_from", "valid_to")
      .sort("code", "valid_from"))
print("cohort unit prices of the same anchor codes:")
print(p.filter(pl.col("procedure_code").is_in(anchors)).group_by("procedure_code").agg(
    pl.len(), pl.col("unit_price_try").unique().alias("unit_prices"), pl.col("procedure_date").min().alias("first"),
    pl.col("procedure_date").max().alias("last")))

# ICU presence: anchor says ICU tiering ~81% of real deducted amounts
icu = p.filter(pl.col("procedure_code").is_in(["510090"]) | pl.col("procedure_code").str.contains(r"^P?55200\d$")
               | pl.col("procedure_name").str.to_lowercase().str.contains("yoğun bakım"))
print("\nICU lines (510090 / 55200x / name contains 'yoğun bakım'):", icu.height)
icu_cat = cat.filter(pl.col("name").str.to_lowercase().str.contains("yoğun bakım")).select("code").unique()
print("catalog codes with 'yoğun bakım' in name:", icu_cat.height,
      "| cohort lines using any of them:", p.join(icu_cat, left_on="procedure_code", right_on="code", how="semi").height)

# gap vs anchor
tb = h["expected_total_billed_try"].sum()
tp = h["expected_total_payable_try"].sum()
gap = (tb - tp) / tb
print(f"\ncohort gap {gap:.2%} vs TUSEB anchor 1.72% -> {gap / 0.0172:.1f}x ; vs 0.13% -> {gap / 0.0013:.0f}x")
x = h.with_columns(((pl.col("expected_total_billed_try") - pl.col("expected_total_payable_try")) / pl.col("expected_total_billed_try")).alias("g"))
print("claims with gap share > 1.72%:", x.filter(pl.col("g") > 0.0172).height, "/", x.height,
      "| > 10%:", x.filter(pl.col("g") > 0.10).height, "| > 50%:", x.filter(pl.col("g") > 0.50).height)
ex = h.filter(pl.col("claim_id") != "F-SENTETIK-HASTA-0023-037")
gb = ex["expected_total_billed_try"].sum()
gp = ex["expected_total_payable_try"].sum()
print(f"gap excluding claim 0023-037 (999,999 line): {(gb - gp) / gb:.2%}; billed {gb:,.0f}")
big = m.filter(pl.col("unit_price_try") == 999999.0)
print(f"999,999 line = {big['billed_amount_try'].sum() / tb:.2%} of cohort billed; claim 0023-037 = "
      f"{h.filter(pl.col('claim_id') == 'F-SENTETIK-HASTA-0023-037')['expected_total_billed_try'].sum() / tb:.2%}")
c.write_parquet(OUT / "h_claims.parquet")
