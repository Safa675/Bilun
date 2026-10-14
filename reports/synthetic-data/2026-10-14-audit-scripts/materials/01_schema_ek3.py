"""Inspect schemas of raw and curated EK-3 annex parquets (read-only)."""
import glob
import os
from collections import Counter

import polars as pl

RAW = "/home/safa/Documents/Bilun/data/gazette/raw"
CUR = "/home/safa/Documents/Bilun/data/gazette/curated"

schemas = Counter()
examples = {}
for f in sorted(glob.glob(f"{RAW}/annex=EK-3*/effective_date=*/*.parquet")):
    s = pl.read_parquet_schema(f)
    key = tuple(s.keys())
    schemas[key] += 1
    examples.setdefault(key, f)
print("RAW distinct schemas:", len(schemas))
for k, n in schemas.most_common():
    print(n, k)
    print("   e.g.", os.path.relpath(examples[k], RAW))

print()
for f in sorted(glob.glob(f"{CUR}/ek3*.parquet")):
    d = pl.read_parquet(f)
    print(os.path.basename(f), d.shape, list(d.columns))
