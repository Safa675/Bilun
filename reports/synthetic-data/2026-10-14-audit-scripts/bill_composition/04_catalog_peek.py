import polars as pl
pl.Config.set_tbl_rows(40); pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(250); pl.Config.set_fmt_str_lengths(70)
G = "/home/safa/Documents/Bilun/data/gazette/curated"
b = pl.read_parquet(f"{G}/ek2b_catalog_history.parquet")
c = pl.read_parquet(f"{G}/ek2c_catalog_history.parquet")
for n, d in [("ek2b", b), ("ek2c", c)]:
    print("=====", n, d.shape); print(d.schema)
    print(d.head(5).to_dicts())
    for col in d.columns:
        print(f"  {col}: nulls={d[col].null_count()} nuniq={d[col].n_unique()}")
print(b.filter(pl.col("code").is_in(["600150","612070","510010","510120","530000","705240","520021","520080"])).sort(["code","valid_from"]).to_dicts())
print(c.filter(pl.col("package_code").is_in(["P605820","P611720","P615440","P620440","P600040","609270","P609270"])).sort(["package_code","valid_from"]).to_dicts()[:20])
print(c["group"].value_counts().sort("count",descending=True).head(40).to_dicts())
