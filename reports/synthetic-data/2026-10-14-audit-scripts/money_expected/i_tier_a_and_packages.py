"""Tier A (showcase) money spot-checks + package claims: are in-package services
still billed and paid alongside the package?
"""
import json

from common import *

h = claims("claim_headers")
dx = claims("claim_diagnoses")
a = pl.read_parquet(OUT / "a_price_lines.parquet")
m = claims("material_claim_lines")
man = json.loads((REPO / "data/synthetic/demo_manifest.json").read_text())
tier_a = [f"SENTETIK-HASTA-{i}" for i in man["tier_a_patient_indices"]]
tier_b = [f"SENTETIK-HASTA-{i}" for i in man["tier_b_patient_indices"]]

ha = h.filter(pl.col("patient_id").is_in(tier_a))
print("Tier A claims:", ha.height)
print(ha.select("claim_id", "claim_type", "department", "primary_icd10", "scenario_tag", "expected_total_billed_try",
                "expected_total_payable_try", "expected_denial_reason"))
la = a.join(ha.select("claim_id"), on="claim_id", how="semi").with_columns(pl.col("ratio_asof").round(2))
print("\nTier A procedure lines priced off the as-of list (ratio outside +-1%):",
      la.filter((pl.col("ratio_asof") - 1).abs() > 0.01).height, "/", la.height,
      "| no as-of price:", la.filter(pl.col("list_price_try").is_null()).height)
print(la.filter(pl.col("claim_id").is_in(["F-SENTETIK-HASTA-0002-006", "F-SENTETIK-HASTA-0003-011", "F-SENTETIK-HASTA-0038-053"]))
      .select("procedure_line_id", "procedure_date", "procedure_code", "procedure_name", "procedure_category", "quantity",
              "unit_price_try", "list_price_try", "ratio_asof", "billed_amount_try", "expected_payable_try"))
print("diagnoses for 0002-006 / 0003-011:")
print(dx.filter(pl.col("claim_id").is_in(["F-SENTETIK-HASTA-0002-006", "F-SENTETIK-HASTA-0003-011"]))
      .select("claim_id", "icd10_code", "diagnosis_role", "is_primary"))
print("catalog names: 609270 / 609300 / P-codes used as packages:")
cat = catalog_versions().filter(pl.col("valid_to").is_null())
print(cat.filter(pl.col("code").is_in(["609270", "609300"])).select("code", "name", "annex", "price_try"))

# ---- package claims: in-package services paid alongside the package ----
pk_claims = a.filter((pl.col("procedure_category") == "paket") | pl.col("package_code").is_not_null()).select("claim_id").unique()
on = a.join(pk_claims, on="claim_id", how="semi").join(h.select("claim_id", "claim_type"), on="claim_id")
others = on.filter(pl.col("procedure_category") != "paket")
print(f"\nclaims with a package line/code: {pk_claims.height}; non-package procedure lines on them: {others.height}")
print(others.group_by("procedure_category").agg(
    pl.len().alias("n"),
    (pl.col("expected_payable_try") > 0).sum().alias("n_paid"),
    pl.col("is_package_included").sum().alias("n_flagged_included"),
    pl.col("expected_payable_try").sum().round(2).alias("paid_sum")).sort("n", descending=True))
pk_lines = on.filter(pl.col("procedure_category") == "paket")
print("package lines: n", pk_lines.height, "| payable == billed:",
      pk_lines.filter((pl.col("expected_payable_try") - pl.col("billed_amount_try")).abs() <= 0.01).height,
      "| package lines per claim max:", pk_lines.group_by("claim_id").len()["len"].max())
print("package lines by claim_type:", pk_lines.join(h.select("claim_id", "claim_type"), on="claim_id", how="left")
      .group_by("claim_type").len().rows())
# bed days paid alongside a surgical package on the same claim
beds_paid = others.filter((pl.col("procedure_code").str.starts_with("51")) & (pl.col("expected_payable_try") > 0))
print("bed-day (51xxxx) lines paid on package claims:", beds_paid.height,
      beds_paid.select("procedure_line_id", "procedure_code", "quantity", "expected_payable_try").head(5).rows())
mat_on = m.join(pk_claims, on="claim_id", how="semi")
print("material lines on package claims:", mat_on.height, "| paid (>0):", mat_on.filter(pl.col("expected_payable_try") > 0).height,
      "| flagged bundled:", mat_on.filter(pl.col("is_bundled")).height)
mat_off = m.join(pk_claims, on="claim_id", how="anti")
print("material lines flagged bundled on claims WITHOUT any package:", mat_off.filter(pl.col("is_bundled")).height,
      mat_off.filter(pl.col("is_bundled")).select("material_line_id", "material_name", "billed_amount_try").head(5).rows())

# ---- payable > billed lines and their tiers ----
pb = a.filter(pl.col("expected_payable_try") > pl.col("billed_amount_try") + 0.01)
print("\nprocedure lines with payable > billed:", pb.height, "| patients:", pb["patient_id"].unique().to_list(),
      "| tier A:", pb.filter(pl.col("patient_id").is_in(tier_a)).height, "| tier B:", pb.filter(pl.col("patient_id").is_in(tier_b)).height)
# ---- placeholder / fault-describing names ----
print("procedure_name == procedure_code:", a.filter(pl.col("procedure_name") == pl.col("procedure_code"))
      .select("procedure_line_id", "procedure_code", "unit_price_try").rows())
print("material names that describe the fault:", m.filter(pl.col("material_name").str.to_lowercase().str.contains("eksik"))
      .select("material_line_id", "material_code", "material_name", "unit_price_try").rows())
# ---- provider_type vs facility_tier contradictions ----
bad = h.filter(((pl.col("provider_type") == "Kamu") & (pl.col("facility_tier") == "2_3_basamak_ozel")) |
               ((pl.col("provider_type") == "Ozel") & (pl.col("facility_tier") == "2_basamak_kamu")))
print("\nclaims whose provider_type contradicts facility_tier:", bad.height, "/", h.height,
      bad.select("claim_id", "provider_type", "facility_tier").head(3).rows())
# same patient, different provider types across claims
pp = h.group_by("patient_id").agg(pl.col("provider_type").n_unique().alias("n_pt"), pl.len().alias("n_claims"))
print("patients with >1 claim:", pp.filter(pl.col("n_claims") > 1).height,
      "| of which seen at >1 provider_type:", pp.filter((pl.col("n_claims") > 1) & (pl.col("n_pt") > 1)).height)
