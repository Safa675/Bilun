import polars as pl
R = "/home/safa/Documents/Bilun/data/synthetic/sut"
h = pl.read_parquet(f"{R}/claims/claim_headers.parquet")
out = h.select(pl.col("claim_id").str.replace("F-SENTETIK-HASTA-",""), "claim_type","occupational_context","facility_tier","provider_type","department","admission_date","discharge_date","claim_start_date","claim_end_date","primary_icd10","package_candidate","expected_total_billed_try","expected_denial_reason","scenario_tag")
out.write_csv("out_headers.csv", separator="|")
for c in ["claim_type","occupational_context","facility_tier","provider_type","department","package_candidate","expected_denial_reason"]:
    print(h[c].value_counts().sort("count", descending=True).to_dicts())
print(h.group_by(["facility_tier","provider_type"]).len().sort("len",descending=True).to_dicts())
