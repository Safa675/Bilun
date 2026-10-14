"""(e) surcharge_applicable / surcharge_rate / copay_rate_applicable / copay_rate on
procedure lines vs claim type and provider type; are payable amounts explained
by these fields?
"""
from common import *

h = claims("claim_headers")
p = claims("procedure_claim_lines")
x = p.join(h.select("claim_id", "claim_type", "provider_type", "facility_tier"), on="claim_id")

print("surcharge_applicable x provider_type:")
print(x.group_by("provider_type", "surcharge_applicable").len().sort("provider_type", "surcharge_applicable"))
print("\nsurcharge_rate distribution:", x["surcharge_rate"].value_counts().sort("count", descending=True).rows())
print("surcharge_rate by provider_type (min/median/max):")
print(x.group_by("provider_type").agg(pl.col("surcharge_rate").min().alias("min"), pl.col("surcharge_rate").median().alias("med"),
                                      pl.col("surcharge_rate").max().alias("max"), pl.col("surcharge_rate").n_unique().alias("n_unique")))
print("\nlines with surcharge_applicable=True at Kamu/Universite:",
      x.filter(pl.col("surcharge_applicable") & pl.col("provider_type").is_in(["Kamu", "Universite"])).height)
print("lines with surcharge_rate>0 but applicable=False:",
      x.filter((~pl.col("surcharge_applicable")) & (pl.col("surcharge_rate") > 0)).height)
print("\ncopay_rate_applicable x claim_type:")
print(x.group_by("claim_type", "copay_rate_applicable").len().sort("claim_type"))
print("\ncopay_rate values:", x["copay_rate"].value_counts().sort("count", descending=True).rows())
print("copay_rate by claim_type x category (n_unique, min, max):")
print(x.group_by("claim_type", "procedure_category").agg(pl.len(), pl.col("copay_rate").n_unique().alias("nu"),
                                                         pl.col("copay_rate").min().alias("min"), pl.col("copay_rate").max().alias("max"))
      .sort("claim_type", "procedure_category"))
print("\ncopay_rate>0 on yatis lines:", x.filter((pl.col("claim_type") == "yatis") & (pl.col("copay_rate") > 0)).height,
      "/", x.filter(pl.col("claim_type") == "yatis").height)
print("copay_rate>0 on lab/radiology (islem R/L/8xx/9xx) lines:",
      x.filter((pl.col("copay_rate") > 0) & pl.col("procedure_category").is_in(["laboratuvar"])).height)

# Do these fields explain payable?  Try payable == billed*(1-copay) , == unit*qty*(1-copay), == billed/(1+surch)
x = x.with_columns((pl.col("unit_price_try") * pl.col("quantity")).alias("uxq"))
tests = {
    "payable==billed": (pl.col("expected_payable_try") - pl.col("billed_amount_try")).abs() <= 0.02,
    "payable==uxq": (pl.col("expected_payable_try") - pl.col("uxq")).abs() <= 0.02,
    "payable==billed*(1-copay)": (pl.col("expected_payable_try") - pl.col("billed_amount_try") * (1 - pl.col("copay_rate"))).abs() <= 0.02,
    "payable==uxq*(1-copay)": (pl.col("expected_payable_try") - pl.col("uxq") * (1 - pl.col("copay_rate"))).abs() <= 0.02,
    "billed==uxq*(1+surch)": (pl.col("billed_amount_try") - pl.col("uxq") * (1 + pl.col("surcharge_rate"))).abs() <= 0.02,
    "payable==billed/(1+surch)": (pl.col("expected_payable_try") - pl.col("billed_amount_try") / (1 + pl.col("surcharge_rate"))).abs() <= 0.02,
    "payable==0": pl.col("expected_payable_try") == 0,
}
print("\nformula hit counts over", x.height, "procedure lines:")
for k, e in tests.items():
    print(f"  {k}: {x.filter(e).height}")
expl = pl.any_horizontal(list(tests.values()))
print("  explained by at least one:", x.filter(expl).height)
x = x.with_columns((pl.col("expected_payable_try") / pl.col("uxq")).round(3).alias("pay_frac"),
                   (pl.col("billed_amount_try") / pl.col("uxq")).round(3).alias("bill_frac"))
print("\nmost common payable/(unit*qty) fractions:", x["pay_frac"].value_counts().sort("count", descending=True).head(12).rows())
print("most common billed/(unit*qty) fractions:", x["bill_frac"].value_counts().sort("count", descending=True).head(12).rows())
print("distinct payable fractions:", x["pay_frac"].n_unique(), " distinct billed fractions:", x["bill_frac"].n_unique())
print("\nunexplained examples:")
print(x.filter(~expl).select("procedure_line_id", "claim_type", "provider_type", "procedure_category", "quantity", "unit_price_try",
                             "billed_amount_try", "expected_payable_try", "surcharge_rate", "copay_rate", "bill_frac", "pay_frac").head(12))
# Muayene katilim payi is a fixed TL amount, not a percentage; check muayene lines
mu = x.filter(pl.col("procedure_category") == "muayene")
print("\nmuayene lines:", mu.height, " gap (billed-payable) distinct values:",
      (mu["billed_amount_try"] - mu["expected_payable_try"]).round(2).n_unique())
x.write_parquet(OUT / "e_proc_fields.parquet")

# ---- reverse-engineer the generator's billed/payable formula ----
x = x.with_columns(
    (pl.col("billed_amount_try") / (pl.col("uxq") * (1 + pl.col("surcharge_rate").fill_null(0)))).round(3).alias("k_billed"),
    (pl.col("expected_payable_try") / (pl.col("uxq") * (1 - pl.col("copay_rate").fill_null(0)))).round(3).alias("k_payable"),
)
print("\nk_billed = billed/(unit*qty*(1+surcharge)) top values:", x["k_billed"].value_counts().sort("count", descending=True).head(8).rows())
print("k_payable = payable/(unit*qty*(1-copay)) top values:", x["k_payable"].value_counts().sort("count", descending=True).head(8).rows())
both03 = x.filter(((pl.col("k_billed") - 0.3).abs() <= 0.002) & ((pl.col("k_payable") - 0.3).abs() <= 0.002))
print("lines where billed = 0.3*unit*qty*(1+s) AND payable = 0.3*unit*qty*(1-c):", both03.height, "/", x.height)
print(" by category:", both03["procedure_category"].value_counts().sort("count", descending=True).rows())
print(" by claim_type:", both03["claim_type"].value_counts().sort("count", descending=True).rows())
kb = x.filter((pl.col("k_billed") - 0.3).abs() <= 0.002)
print("lines with billed = 0.3*unit*qty*(1+s):", kb.height)
kp = x.filter((pl.col("k_payable") - 0.3).abs() <= 0.002)
print("lines with payable = 0.3*unit*qty*(1-c):", kp.height)
kb1 = x.filter((pl.col("k_billed") - 1.0).abs() <= 0.002)
print("lines with billed = 1.0*unit*qty*(1+s):", kb1.height)

# ---- ilave ucret (surcharge) where it is prohibited ----
g = pl.read_parquet(GAZ / "ek2g_no_surcharge.parquet").select("procedure_code").unique()
sx = x.filter(pl.col("surcharge_applicable") & (pl.col("surcharge_rate").fill_null(0) > 0))
print("\nsurcharged lines (applicable & rate>0):", sx.height)
print(" on EK-2G (no-surcharge list) codes:", sx.join(g, on="procedure_code", how="semi").height,
      sx.join(g, on="procedure_code", how="semi").select("procedure_line_id", "procedure_code", "procedure_name", "surcharge_rate").head(5).rows())
print(" on acil claims:", sx.filter(pl.col("claim_type") == "acil").height, "/", x.filter(pl.col("claim_type") == "acil").height)
print(" at Kamu (MoH public) providers:", sx.filter(pl.col("provider_type") == "Kamu").height, "/", x.filter(pl.col("provider_type") == "Kamu").height)
print(" at Universite providers:", sx.filter(pl.col("provider_type") == "Universite").height, "/", x.filter(pl.col("provider_type") == "Universite").height)
print(" surcharge rate == 1.0 (200% of SUT billed):", sx.filter(pl.col("surcharge_rate") == 1.0).height)
print(" lab lines surcharged:", sx.filter(pl.col("procedure_category") == "laboratuvar").height)
print(" provider_type x facility_tier crosstab:")
print(h.group_by("provider_type", "facility_tier").len().sort("provider_type"))

# ---- percentage copay on procedure lines vs the repo's EK-2C-1 list (procedure-specific copay rates) ----
c1 = pl.read_parquet(GAZ / "ek2c1_copay_rates.parquet").select("procedure_code", "copay_rate_pct")
cp = x.filter(pl.col("copay_rate").fill_null(0) > 0)
print("\nprocedure lines with copay_rate>0:", cp.height, "| by claim_type:", cp["claim_type"].value_counts().sort("count", descending=True).rows())
print(" of which code is on EK-2C-1 list:", cp.join(c1, on="procedure_code", how="semi").height,
      "| rate equals EK-2C-1 pct/100:", cp.join(c1, on="procedure_code").filter((pl.col("copay_rate") - pl.col("copay_rate_pct") / 100).abs() < 1e-6).height)
print(" by category:", cp["procedure_category"].value_counts().sort("count", descending=True).rows())
print(" koruyucu lines with copay>0:", cp.filter(pl.col("claim_type") == "koruyucu").select("procedure_line_id", "copay_rate").rows())
