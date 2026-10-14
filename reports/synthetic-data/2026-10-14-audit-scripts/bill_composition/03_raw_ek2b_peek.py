import polars as pl
B = "/home/safa/Documents/Bilun/data/gazette/raw/annex=EK-2B"
f = f"{B}/effective_date=2024-05-11/EK-2B_HIZMET_BASI_ISLEM_PUAN_LISTESI_Yur.11.05.2024__EK-2B.parquet"
df = pl.read_parquet(f)
cols = df.columns[:4]
df.select(cols).with_row_index().write_csv("out_raw_ek2b_2024.csv", separator="|")
print(df.select(cols).head(12).to_dicts())
