"""Which EK-2B procedures WOULD legitimately carry each material family? (evidence for the compat table)

Reads data/gazette/curated/ek2b_catalog_history.parquet (read-only); prints matching procedure codes
valid in 2023-2024, per family regex used in 32_material_procedure_link.py.
"""
import polars as pl

from common import norm_expr
from compat import FAMILY_PROC_RE

pl.Config.set_tbl_rows(400)
pl.Config.set_fmt_str_lengths(90)
pl.Config.set_tbl_width_chars(200)

e = pl.read_parquet("/home/safa/Documents/Bilun/data/gazette/curated/ek2b_catalog_history.parquet")
e = (e.filter((pl.col("valid_from") <= "2024-12-31") & ((pl.col("valid_to").is_null()) | (pl.col("valid_to") >= "2023-01-01")))
     .select("code", "name").unique("code").with_columns(norm_expr("name").alias("k")))
print("EK-2B codes valid 2023-2024:", e.height)
for fam, rx in FAMILY_PROC_RE.items():
    hit = e.filter(pl.col("k").str.contains(rx)).sort("code")
    print(f"\n=== {fam}: {hit.height} EK-2B procedures match /{rx}/ ; first 12:")
    print(hit.select("code", "name").head(12))
