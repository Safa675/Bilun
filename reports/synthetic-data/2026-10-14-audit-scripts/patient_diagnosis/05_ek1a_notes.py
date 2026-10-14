import polars as pl, glob
f=glob.glob("/home/safa/Documents/Bilun/data/gazette/raw/annex=EK-1A/effective_date=unknown/*.parquet")[0]
e=pl.read_parquet(f).select("Unnamed: 0")
rows=e.to_series().to_list()
print(rows[0]); print(rows[-2]); print(rows[-1])
