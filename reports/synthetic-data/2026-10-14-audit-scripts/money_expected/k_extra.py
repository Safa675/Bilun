"""Extra measured checks: bed-days vs length of stay, day-bed on inpatient stays,
orthosis/prosthesis lines treated as bundled consumables, Tier A golden bands vs
claim lines, at-list matches that are only stale catalog rows.
"""
import json

from common import *

h = claims("claim_headers")
p = claims("procedure_claim_lines")
m = claims("material_claim_lines")
cat = catalog_versions()

hd = h.with_columns((pl.col("claim_end_date").str.to_date() - pl.col("claim_start_date").str.to_date())
                    .dt.total_days().alias("los"))
beds = p.filter(pl.col("procedure_code").str.starts_with("51")).join(
    hd.select("claim_id", "claim_type", "los"), on="claim_id")
print("51xxxx bed lines:", beds.height, "| by code:", beds["procedure_code"].value_counts().rows())
over = beds.filter(pl.col("quantity") > pl.col("los") + 1)
print("bed lines with quantity > LOS+1 (LOS = end-start days):", over.height, "/", beds.height)
print(over.select("procedure_line_id", "procedure_code", "quantity", "los").sort("quantity", descending=True).rows())
day_on_inpt = beds.filter((pl.col("procedure_code") == "510120") & (pl.col("claim_type") == "yatis"))
print("510120 Gunduz yatak on yatis claims:", day_on_inpt.height, "| quantities:", day_on_inpt["quantity"].to_list())
nail = p.filter(pl.col("procedure_code") == "612070")
print("612070 'Tirnak yatak revizyonu' lines categorised as:", nail["procedure_category"].value_counts().rows(),
      "| quantities:", sorted(nail["quantity"].to_list()), "| billed sum:", round(nail["billed_amount_try"].sum(), 2))
print("yatis claims with no 51xxxx bed line:",
      h.filter(pl.col("claim_type") == "yatis").join(beds.select("claim_id").unique(), on="claim_id", how="anti").height,
      "/", h.filter(pl.col("claim_type") == "yatis").height)

# orthosis/prosthesis (EK-3C 'OP' codes) treated as bundled package consumables
op = m.filter(pl.col("material_code").str.starts_with("OP"))
opb = op.filter(pl.col("is_bundled"))
print("\nOP-coded (EK-3C orthosis/prosthesis) lines:", op.height, "| flagged bundled & unpaid:", opb.height,
      "| billed sum of those:", round(opb["billed_amount_try"].sum(), 2),
      "| share of material gap:", round(opb["billed_amount_try"].sum() / (m["billed_amount_try"] - m["expected_payable_try"]).sum(), 3))
print(opb.select("material_line_id", "material_code", "material_name", "billed_amount_try", "denial_reason_expected").rows()[:6])

# Tier A golden bands vs claim lines
v = json.loads((REPO / "data/synthetic/demo_vignettes.json").read_text())["vignettes"]
for idx, cl in [("0002", "F-SENTETIK-HASTA-0002-006"), ("0003", "F-SENTETIK-HASTA-0003-011")]:
    g = v[idx]["golden"]
    lines = p.filter(pl.col("claim_id") == cl)
    itemized = lines.filter(pl.col("procedure_category") != "paket")["billed_amount_try"].sum()
    pkg = lines.filter(pl.col("procedure_category") == "paket")["billed_amount_try"].sum()
    asof = lines.join(cat, left_on="procedure_code", right_on="code").filter(
        (pl.col("valid_from") <= pl.col("procedure_date")) & (pl.col("valid_to").is_null() | (pl.col("procedure_date") <= pl.col("valid_to"))))
    print(f"\nvignette {idx} {cl}: golden itemized={g['itemized_total_try']} package={g['package_total_try']} savings={g['savings_try']} "
          f"| claim lines: itemized billed={itemized} package billed={pkg}")
    print("  lines:", lines.select("procedure_code", "procedure_name", "procedure_category", "billed_amount_try").rows())
    print("  as-of list on service date:", asof.select("procedure_code", "price_try", "valid_from").rows())
    pc = v[idx]["package_code"]
    pa = cat.filter((pl.col("code") == pc) & (pl.col("valid_from") <= lines["procedure_date"][0])
                    & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= lines["procedure_date"][0])))
    print(f"  vignette package {pc} ({cat.filter(pl.col('code') == pc)['name'][0]}) as-of price:", pa["price_try"].to_list(),
          "vs vignette price", v[idx]["package_price_try"])

# at-list matches that are only stale catalog rows
a = pl.read_parquet(OUT / "a_price_lines.parquet")
at = a.filter(((pl.col("unit_price_try") / pl.col("list_price_try")) - 1).abs() <= 0.01)
nver = cat.group_by("code").agg(pl.len().alias("n_versions"), pl.col("valid_from").max().alias("last_from"))
at = at.join(nver, left_on="procedure_code", right_on="code", how="left")
print("\nat-as-of-list lines:", at.height, "| of which code has <=2 catalog rows and last row starts <=2021-06-01:",
      at.filter((pl.col("n_versions") <= 2) & (pl.col("last_from") <= "2021-06-01")).height)
print(at.select("procedure_line_id", "procedure_code", "unit_price_try", "n_versions", "last_from").rows())
stale = nver.filter((pl.col("last_from") <= "2021-06-01"))
print("catalog codes whose newest row starts on/before 2021-06-01 (never re-issued in 2022-2026 lists):", stale.height,
      "of", nver.height)
anach = a.filter(pl.col("list_price_try").is_null()).join(nver, left_on="procedure_code", right_on="code")
print("lines billed before the code's first catalog appearance:")
first = cat.group_by("code").agg(pl.col("valid_from").min().alias("first_from"))
print(a.filter(pl.col("list_price_try").is_null()).join(first, left_on="procedure_code", right_on="code")
      .select("procedure_line_id", "procedure_date", "procedure_code", "first_from").rows())
