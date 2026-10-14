"""Header primary_icd10 vs claim_diagnoses primary; names of P-codes priced as packages."""
from common import *
h = claims("claim_headers"); dx = claims("claim_diagnoses")
prim = dx.filter(pl.col("is_primary")).group_by("claim_id").agg(pl.col("icd10_code").alias("dx_primary"), pl.len().alias("n_primary"))
j = h.select("claim_id", "primary_icd10", "scenario_tag").join(prim, on="claim_id", how="left")
j = j.with_columns(pl.col("dx_primary").list.contains(pl.col("primary_icd10")).fill_null(False).alias("match"))
print("claims:", j.height, "| header primary_icd10 found among claim_diagnoses primaries:", j.filter(pl.col("match")).height,
      "| mismatch:", j.filter(~pl.col("match")).height, "| claims with no primary dx row:", j.filter(pl.col("dx_primary").is_null()).height,
      "| claims with >1 primary:", j.filter(pl.col("n_primary") > 1).height)
print(j.filter(~pl.col("match")).select("claim_id", "primary_icd10", "dx_primary", "scenario_tag").head(10))
cat = catalog_versions().filter(pl.col("valid_to").is_null())
print(cat.filter(pl.col("code").is_in(["P615440", "L116470"])).select("code", "name", "annex", "price_try").rows())
