import polars as pl
pl.Config.set_tbl_cols(60); pl.Config.set_fmt_str_lengths(120); pl.Config.set_tbl_width_chars(300); pl.Config.set_tbl_rows(200)
e=pl.read_parquet("/home/safa/Documents/Bilun/data/gazette/curated/ek1a_chronic_exemptions.parquet")
print(e.shape); print(e.schema)
print(e)
