import polars as pl
B = "/home/safa/Documents/Bilun/data/"
P = pl.read_parquet(B+"synthetic/sut/claims/procedure_claim_lines.parquet")
H = pl.read_parquet(B+"synthetic/sut/claims/claim_headers.parquet")
R = pl.read_parquet(B+"synthetic/sut/claims/medula_rejection_events.parquet")
h2b = pl.read_parquet(B+"gazette/curated/ek2b_catalog_history.parquet").select("code","price_try","valid_from","valid_to")
h2c = pl.read_parquet(B+"gazette/curated/ek2c_catalog_history.parquet").select(pl.col("package_code").alias("code"),"price_try","valid_from","valid_to")
hist = pl.concat([h2b, h2c])
latest = hist.sort("valid_from").group_by("code").agg(pl.col("price_try").last().alias("p_latest"), pl.col("valid_from").last().alias("latest_from"))
asof = (P.select("procedure_line_id","claim_id","procedure_code","procedure_date","unit_price_try")
        .join(hist, left_on="procedure_code", right_on="code", how="left")
        .filter((pl.col("valid_from") <= pl.col("procedure_date")) & (pl.col("procedure_date") <= pl.col("valid_to")))
        .select("procedure_line_id", pl.col("price_try").alias("p_asof")))
X = P.join(latest, left_on="procedure_code", right_on="code", how="left").join(asof, on="procedure_line_id", how="left")
near = lambda a,b: ((pl.col(a)-pl.col(b)).abs() <= 0.01*pl.col(b))
print("lines:", X.height, "| code found in history:", X["p_latest"].is_not_null().sum(), "| with as-of price:", X["p_asof"].is_not_null().sum())
print("unit == latest(2026) price ±1%:", X.filter(near("unit_price_try","p_latest")).height)
print("unit == as-of price ±1%:", X.filter(near("unit_price_try","p_asof")).height)
r = X.filter(pl.col("p_asof")>0).with_columns((pl.col("unit_price_try")/pl.col("p_asof")).alias("ratio"))
print("ratio unit/as-of: min %.2f median %.2f max %.2f" % (r["ratio"].min(), r["ratio"].median(), r["ratio"].max()))
print("unit == latest but != as-of:", X.filter(near("unit_price_try","p_latest") & ~near("unit_price_try","p_asof")).height)
# package label without package
pk = P.group_by("claim_id").agg((pl.col("procedure_category")=="paket").any().alias("has_paket"), pl.col("package_code").is_not_null().any().alias("has_pkgcode"), pl.col("is_package_included").any().alias("has_incl"))
lab = H.join(pk, on="claim_id").filter(pl.col("expected_denial_reason")=="Kismi paket ici satir reddi")
nopkg = lab.filter(~pl.col("has_paket") & ~pl.col("has_pkgcode") & ~pl.col("has_incl") & (pl.col("package_candidate")!="True"))
print("Kismi paket label:", lab.height, "| with no package line/code/included/candidate:", nopkg.height, nopkg.group_by("claim_type").len().sort("claim_type").rows())
# payable > billed
print("proc lines payable>billed:", P.filter(pl.col("expected_payable_try")>pl.col("billed_amount_try")+0.005).select("procedure_line_id","billed_amount_try","expected_payable_try").rows())
print("claims payable>billed:", H.filter(pl.col("expected_total_payable_try")>pl.col("expected_total_billed_try")).select("claim_id","expected_total_billed_try","expected_total_payable_try").rows())
# ICU lines
print("ICU-like procedure names:", P.filter(pl.col("procedure_name").str.to_lowercase().str.contains("yoğun bakım|yogun bakim")).height)
# medula dates
m = R.join(H.select("claim_id","claim_type","claim_start_date","claim_end_date","provider_type"), on="claim_id")
print(m.select("claim_id","hata_kodu","medula_stage","rejection_timestamp","claim_start_date","claim_end_date","claim_type","provider_type").rows())
