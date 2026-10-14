import polars as pl, glob
f=glob.glob("/home/safa/Documents/Bilun/data/gazette/raw/annex=EK-1A/effective_date=unknown/*.parquet")[0]
e=pl.read_parquet(f).select("Unnamed: 0","EK-1/A")
for a,b in e.iter_rows():
    print(repr(a)[:70], "|", repr(b)[:110])
