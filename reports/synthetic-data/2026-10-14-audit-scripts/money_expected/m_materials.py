"""Material lines vs the EK-3 snapshot catalogs (single, un-versioned snapshot).
Also: drug copay_rate vs EK-4A kamu iskontosu tiers.
"""
import glob

from common import *

m = claims("material_claim_lines")
h = claims("claim_headers")

frames = []
for f in sorted(glob.glob(str(GAZ / "ek3*.parquet"))):
    df = pl.read_parquet(f)
    if "sut_code" not in df.columns:
        continue
    cols = {"sut_code": pl.col("sut_code").cast(pl.String),
            "material_name": pl.col("material_name").cast(pl.String)}
    sel = [cols["sut_code"], cols["material_name"]]
    sel.append(pl.col("price_try").cast(pl.Float64) if "price_try" in df.columns else pl.lit(None, pl.Float64).alias("price_try"))
    frames.append(df.select(sel).with_columns(pl.lit(f.split("/")[-1].replace(".parquet", "")).alias("ek3_file")))
ek3 = pl.concat(frames).with_columns(pl.col("sut_code").str.strip_chars())
print("EK-3 rows:", ek3.height, " distinct codes:", ek3["sut_code"].n_unique())

mm = m.select("material_line_id", "claim_id", "procedure_line_id", "material_code", "material_name", "material_type",
              "quantity", "unit_price_try", "billed_amount_try", "expected_payable_try", "is_bundled",
              "denial_reason_expected", "uts_registered", "titubb_registered")
j = mm.join(ek3.group_by("sut_code").agg(pl.col("material_name").first().alias("ek3_name"),
                                         pl.col("price_try").max().alias("ek3_price"),
                                         pl.col("ek3_file").first()),
            left_on="material_code", right_on="sut_code", how="left")
print("material lines:", j.height, " code found in EK-3:", j.filter(pl.col("ek3_name").is_not_null()).height)
j = j.with_columns(
    (pl.col("material_name").str.to_uppercase().str.slice(0, 20) == pl.col("ek3_name").str.to_uppercase().str.slice(0, 20)).alias("name_match"),
    (pl.col("unit_price_try") / pl.col("ek3_price")).alias("ratio_vs_ek3"),
)
print("name prefix match (20 chars, uppercase):", j.filter(pl.col("name_match")).height,
      "| mismatch:", j.filter(pl.col("ek3_name").is_not_null() & ~pl.col("name_match")).height)
print("lines with EK-3 price available:", j.filter(pl.col("ek3_price").is_not_null() & (pl.col("ek3_price") > 0)).height)
r = j.filter(pl.col("ek3_price") > 0)["ratio_vs_ek3"]
if r.len():
    print(f"unit/EK-3 snapshot price: min={r.min():.3f} median={r.median():.3f} max={r.max():.3f}; "
          f"at +-1%: {j.filter(((pl.col('ratio_vs_ek3') - 1).abs() <= 0.01)).height}")
print("\nname mismatches:")
print(j.filter(pl.col("ek3_name").is_not_null() & ~pl.col("name_match")).select(
    "material_line_id", "material_code", "material_name", "ek3_name", "unit_price_try", "ek3_price").head(20))
print("\nnot found in EK-3:")
print(j.filter(pl.col("ek3_name").is_null()).select("material_line_id", "material_code", "material_name", "unit_price_try"))
print("\nthe 999,999 line:")
print(j.filter(pl.col("unit_price_try") >= 900000).select("material_line_id", "material_code", "material_name",
                                                           "ek3_name", "ek3_file", "ek3_price", "unit_price_try",
                                                           "expected_payable_try", "denial_reason_expected"))
# real ICD-type entries in cardiology annex
icd = ek3.filter(pl.col("material_name").str.to_uppercase().str.contains("DEFİBRİLATÖR|DEFIBRILATOR|KARDİYOVERTER|KARDIYOVERTER"))
print("\nEK-3 rows mentioning defibrillator/cardioverter:", icd.height)
print(icd.sort("price_try", descending=True).head(8))
print("\nmaterial_type values:", m["material_type"].value_counts().sort("count", descending=True).rows())
print("material quantity distribution:", m["quantity"].value_counts().sort("quantity").rows())
print("\nbundled (is_bundled) lines by material_type and claim_type:")
print(m.filter(pl.col("is_bundled")).join(h.select("claim_id", "claim_type"), on="claim_id")
      .group_by("material_type", "claim_type").agg(pl.len(), pl.col("billed_amount_try").sum().round(2)).sort("len", descending=True))
print("\nmaterial line with procedure_line_id that does not exist:",
      m.filter(pl.col("procedure_line_id").is_not_null() & (pl.col("procedure_line_id") != ""))
      .join(claims("procedure_claim_lines").select("procedure_line_id"), on="procedure_line_id", how="anti").height,
      "| null/empty procedure_line_id:", m.filter(pl.col("procedure_line_id").is_null() | (pl.col("procedure_line_id") == "")).height)
j.write_parquet(OUT / "m_material_vs_ek3.parquet")

# ---- drugs: copay_rate vs EK-4A kamu iskontosu ----
d = claims("drug_claim_lines")
e4 = ek4a().select("kamu_no", "barcode", "drug_name", "discount_tier_1", "discount_tier_2", "valid_from", "valid_until")
dj = d.select("drug_claim_line_id", "drug_code", "barkod", "drug_name", "drug_claim_date", "copay_rate", "discount_tier_expected") \
    .join(e4, left_on="drug_code", right_on="kamu_no", how="left") \
    .filter(pl.col("valid_from").is_null() | ((pl.col("valid_from") <= pl.col("drug_claim_date")) &
                                               (pl.col("valid_until").is_null() | (pl.col("drug_claim_date") <= pl.col("valid_until")))))
dj = dj.unique("drug_claim_line_id", keep="first")
print("\ndrug lines:", d.height, " with in-force EK-4A row on drug date:", dj.filter(pl.col("discount_tier_1").is_not_null()).height)
dj = dj.with_columns(pl.col("discount_tier_1").cast(pl.Float64, strict=False).alias("t1"))
print("copay_rate == EK-4A discount_tier_1 (in force):",
      dj.filter((pl.col("t1") - pl.col("copay_rate")).abs() < 1e-6).height)
print("barkod == EK-4A barcode:", dj.filter(pl.col("barkod") == pl.col("barcode")).height)
print(dj.filter((pl.col("t1") - pl.col("copay_rate")).abs() >= 1e-6).select(
    "drug_claim_line_id", "drug_code", "drug_claim_date", "copay_rate", "t1", "discount_tier_2").head(8))

# ---- explicit checks used in the report ----
print("\ndrug copay_rate == discount_tier_expected:", d.filter((pl.col("copay_rate") - pl.col("discount_tier_expected")).abs() < 1e-9).height, "/", d.height)
print("drug copay_rate range:", d["copay_rate"].min(), d["copay_rate"].median(), d["copay_rate"].max())
hh = claims("claim_headers").select("claim_id", "claim_type")
print("drug lines on yatis claims with copay_rate>0:", d.join(hh, on="claim_id").filter((pl.col("claim_type") == "yatis") & (pl.col("copay_rate") > 0)).height)
icd_rows = ek3.filter(pl.col("material_name").str.starts_with("ICD,"))
print("EK-3 'ICD, ...' device rows:", icd_rows.height, "price min/max:", icd_rows["price_try"].min(), icd_rows["price_try"].max(),
      "| codes:", sorted(icd_rows["sut_code"].to_list()))
print("OP1592 in EK-3:", ek3.filter(pl.col("sut_code") == "OP1592").select("ek3_file", "material_name", "price_try").rows())
