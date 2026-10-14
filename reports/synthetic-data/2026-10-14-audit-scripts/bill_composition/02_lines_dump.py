import polars as pl
R = "/home/safa/Documents/Bilun/data/synthetic/sut"
h = pl.read_parquet(f"{R}/claims/claim_headers.parquet")
p = pl.read_parquet(f"{R}/claims/procedure_claim_lines.parquet")
j = p.join(h.select("claim_id","claim_type","department","primary_icd10"), on="claim_id", how="left")
out = j.select(
    pl.col("procedure_line_id").str.replace("ISL-F-SENTETIK-HASTA-","").alias("line"),
    pl.col("claim_type").alias("ctype"),
    "procedure_date","procedure_code","procedure_name","procedure_category","quantity","unit_price_try","billed_amount_try","expected_payable_try",
    "is_package_included","package_code","surcharge_applicable","surcharge_rate","copay_rate_applicable","copay_rate","denial_reason_expected","rule_trace_expected","sag_sol","procedure_specialty_code")
out.write_csv("out_lines.csv", separator="|")
print(p["procedure_category"].value_counts().to_dicts())
print(p["sag_sol"].value_counts().to_dicts())
print(p["denial_reason_expected"].value_counts().to_dicts())
print(p["quantity"].value_counts().sort("quantity").to_dicts())
print(p["procedure_specialty_code"].value_counts().to_dicts())
