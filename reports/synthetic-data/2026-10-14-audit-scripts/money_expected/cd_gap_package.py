"""(c) billed - payable gap by claim / claim type / tier / provider; denial share.
(d) 'Kismi paket ici satir reddi' header reason vs actual package evidence and
    which lines carry the reduction.
"""
from common import *

h = claims("claim_headers")
p = claims("procedure_claim_lines")
d = claims("drug_claim_lines")
m = claims("material_claim_lines")

# ---------- unified line table ----------
lines = pl.concat([
    p.select(pl.lit("procedure").alias("kind"), pl.col("procedure_line_id").alias("line_id"), "claim_id",
             pl.col("procedure_code").alias("code"), "procedure_category", "billed_amount_try",
             "expected_payable_try", "denial_reason_expected", "package_code", "is_package_included"),
    d.select(pl.lit("drug").alias("kind"), pl.col("drug_claim_line_id").alias("line_id"), "claim_id",
             pl.col("drug_code").alias("code"), pl.lit(None, pl.String).alias("procedure_category"),
             "billed_amount_try", "expected_payable_try", "denial_reason_expected",
             pl.lit(None, pl.String).alias("package_code"), pl.lit(None, pl.Boolean).alias("is_package_included")),
    m.select(pl.lit("material").alias("kind"), pl.col("material_line_id").alias("line_id"), "claim_id",
             pl.col("material_code").alias("code"), pl.lit(None, pl.String).alias("procedure_category"),
             "billed_amount_try", "expected_payable_try", "denial_reason_expected",
             pl.lit(None, pl.String).alias("package_code"), pl.col("is_bundled").alias("is_package_included")),
]).with_columns((pl.col("billed_amount_try") - pl.col("expected_payable_try")).alias("gap"))

print("lines:", lines.height)
print("\nlines with gap>0.01:", lines.filter(pl.col("gap") > 0.01).height,
      "| gap<-0.01 (payable>billed):", lines.filter(pl.col("gap") < -0.01).height,
      "| gap==0:", lines.filter(pl.col("gap").abs() <= 0.01).height)
print("\nby kind: n, n_gap>0, n_with_reason, n_gap>0_without_reason, gap sum")
print(lines.group_by("kind").agg(
    pl.len().alias("n"),
    (pl.col("gap") > 0.01).sum().alias("n_gap_pos"),
    (pl.col("denial_reason_expected").fill_null("") != "").sum().alias("n_reason"),
    ((pl.col("gap") > 0.01) & (pl.col("denial_reason_expected").fill_null("") == "")).sum().alias("n_gap_no_reason"),
    pl.col("gap").sum().round(2).alias("gap_sum"),
    pl.col("gap").filter(pl.col("denial_reason_expected").fill_null("") != "").sum().round(2).alias("gap_sum_reasoned"),
))
tot_gap = lines["gap"].sum()
reasoned_gap = lines.filter(pl.col("denial_reason_expected").fill_null("") != "")["gap"].sum()
print(f"total gap {tot_gap:,.2f}; gap on lines that carry a denial reason {reasoned_gap:,.2f} "
      f"({reasoned_gap / tot_gap:.1%}); unexplained {tot_gap - reasoned_gap:,.2f} ({1 - reasoned_gap / tot_gap:.1%})")
print("\nprocedure gap by category (lines without any denial reason):")
print(lines.filter((pl.col("kind") == "procedure") & (pl.col("denial_reason_expected").fill_null("") == ""))
      .group_by("procedure_category").agg(pl.len(), (pl.col("gap") > 0.01).sum().alias("n_gap_pos"),
                                          pl.col("gap").sum().round(2).alias("gap_sum"),
                                          (pl.col("expected_payable_try") / pl.col("billed_amount_try")).median().alias("med_pay_over_billed")))
print("\ndrug payable/billed distribution:",
      d.select((pl.col("expected_payable_try") / pl.col("billed_amount_try")).alias("r"))["r"].describe())
print("drug copay_rate vs 1-payable/billed equality:",
      d.filter(((1 - pl.col("expected_payable_try") / pl.col("billed_amount_try")) - pl.col("copay_rate")).abs() < 0.005).height,
      "/", d.height)

# ---------- claim level ----------
hc = h.with_columns((pl.col("expected_total_billed_try") - pl.col("expected_total_payable_try")).alias("gap"),
                    (1 - pl.col("expected_total_payable_try") / pl.col("expected_total_billed_try")).alias("gap_pct"))
print("\nclaims with gap > 0.01:", hc.filter(pl.col("gap") > 0.01).height, "/", hc.height,
      "| gap<0 (payable>billed):", hc.filter(pl.col("gap") < -0.01).select("claim_id", "expected_total_billed_try",
                                                                          "expected_total_payable_try").rows())
print("claim gap% distribution:", hc["gap_pct"].describe())
for g in ["claim_type", "facility_tier", "provider_type"]:
    print(f"\nby {g}:")
    print(hc.group_by(g).agg(pl.len().alias("n"),
                             pl.col("expected_total_billed_try").sum().round(0).alias("billed"),
                             pl.col("expected_total_payable_try").sum().round(0).alias("payable"),
                             (pl.col("gap").sum() / pl.col("expected_total_billed_try").sum()).round(4).alias("gap_share"),
                             pl.col("gap_pct").median().round(3).alias("median_claim_gap_pct"),
                             pl.col("expected_total_billed_try").median().round(0).alias("median_billed"),
                             ).sort("billed", descending=True))
# excluding the 999,999 line
big = m.filter(pl.col("unit_price_try") >= 100000)
print("\nmaterial lines unit >= 100k:", big.select("material_line_id", "claim_id", "material_code", "material_name",
                                                    "quantity", "unit_price_try", "billed_amount_try",
                                                    "expected_payable_try", "denial_reason_expected").rows())
tb = h["expected_total_billed_try"].sum()
print(f"999,999 line share of cohort billed: {big['billed_amount_try'].sum() / tb:.2%}")
print("top 10 claims by billed (share of cohort):")
print(hc.sort("expected_total_billed_try", descending=True).select(
    "claim_id", "claim_type", "scenario_tag", "expected_total_billed_try", "expected_total_payable_try", "gap_pct")
      .with_columns((pl.col("expected_total_billed_try") / tb).round(4).alias("share")).head(10))

# ---------- (d) package evidence ----------
pk = lines.group_by("claim_id").agg(
    ((pl.col("kind") == "procedure") & (pl.col("procedure_category") == "paket")).sum().alias("n_paket_lines"),
    pl.col("package_code").drop_nulls().n_unique().alias("n_package_codes"),
    (pl.col("is_package_included").fill_null(False) & (pl.col("kind") == "procedure")).sum().alias("n_proc_included"),
    (pl.col("is_package_included").fill_null(False) & (pl.col("kind") == "material")).sum().alias("n_mat_bundled"),
    (pl.col("denial_reason_expected").fill_null("") != "").sum().alias("n_lines_with_reason"),
    (pl.col("gap") > 0.01).sum().alias("n_lines_gap_pos"),
    pl.col("gap").sum().alias("claim_gap"),
    pl.col("gap").filter(pl.col("denial_reason_expected").fill_null("") != "").sum().alias("gap_on_reason_lines"),
)
dd = h.select("claim_id", "claim_type", "scenario_tag", "package_candidate", "expected_denial_reason").join(pk, on="claim_id", how="left")
dd = dd.with_columns(
    ((pl.col("n_paket_lines") > 0) | (pl.col("n_package_codes") > 0)).alias("has_package_line_or_code"),
    (pl.col("package_candidate") == "True").alias("pc_true"),
)
lab = dd.filter(pl.col("expected_denial_reason") == "Kismi paket ici satir reddi")
print(f"\n(d) claims labelled 'Kismi paket ici satir reddi': {lab.height}")
print("  with a paket line or any package_code:", lab.filter(pl.col("has_package_line_or_code")).height)
print("  with package_candidate == True:", lab.filter(pl.col("pc_true")).height)
print("  with any line flagged included/bundled:", lab.filter((pl.col("n_proc_included") + pl.col("n_mat_bundled")) > 0).height)
print("  with any line carrying a denial reason:", lab.filter(pl.col("n_lines_with_reason") > 0).height)
none_ = lab.filter(~pl.col("has_package_line_or_code") & ~pl.col("pc_true") & ((pl.col("n_proc_included") + pl.col("n_mat_bundled")) == 0))
print("  with NO package evidence at all (no paket line, no package_code, candidate!=True, nothing included):", none_.height)
print("  by claim_type of no-evidence claims:", none_["claim_type"].value_counts().sort("count", descending=True).rows())
print(none_.select("claim_id", "claim_type", "scenario_tag", "package_candidate", "n_lines_gap_pos", "claim_gap").head(8))
print("\n  claims WITHOUT the reason (4):")
print(dd.filter(pl.col("expected_denial_reason") != "Kismi paket ici satir reddi").select(
    "claim_id", "claim_type", "scenario_tag", "package_candidate", "has_package_line_or_code", "claim_gap", "n_lines_gap_pos"))
print("  of the 4 without the reason, gap>0:", dd.filter((pl.col("expected_denial_reason") != "Kismi paket ici satir reddi") & (pl.col("claim_gap") > 0.01)).height)
print("\n  package_candidate vs has paket line/code (all 94):")
print(dd.group_by("package_candidate", "has_package_line_or_code").len().sort("len", descending=True))
# outpatient claims with packages
print("\n  claim_type x has_package_line_or_code:")
print(dd.group_by("claim_type", "has_package_line_or_code").len().sort("claim_type"))
lab.write_parquet(OUT / "d_package_label.parquet")
lines.write_parquet(OUT / "c_lines.parquet")
