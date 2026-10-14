"""Peek at raw EK-3 snapshot layouts for a few annexes (read-only)."""
import glob
import sys

import polars as pl

pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_rows(14)
pl.Config.set_fmt_str_lengths(60)
pl.Config.set_tbl_width_chars(300)

RAW = "/home/safa/Documents/Bilun/data/gazette/raw"
for pat in sys.argv[1:]:
    for f in sorted(glob.glob(f"{RAW}/{pat}")):
        d = pl.read_parquet(f)
        meta = [c for c in d.columns if c.startswith("__")]
        print("=====", f.replace(RAW + "/", ""), d.shape)
        print(d.select(meta[:1] + ["__is_mulga", "__sheet_name"]).unique().head(5))
        print(d.drop(meta).head(14))
