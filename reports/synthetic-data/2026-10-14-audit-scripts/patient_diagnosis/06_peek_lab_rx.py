import polars as pl
pl.Config.set_tbl_cols(60); pl.Config.set_fmt_str_lengths(80); pl.Config.set_tbl_width_chars(300); pl.Config.set_tbl_rows(80)
R="/home/safa/Documents/Bilun/data/synthetic/sut/"
lab=pl.read_parquet(R+"clean/lab_clean.parquet")
print(lab.head(10))
print(lab.group_by("SUB_CODE","birim","organ_sistemi").agg(pl.len(),pl.col("sonuc_sayisal").min().alias("mn"),pl.col("sonuc_sayisal").max().alias("mx"),pl.col("ref_alt").first(),pl.col("ref_ust").first()).sort("SUB_CODE"))
rx=pl.read_parquet(R+"clean/recete_clean.parquet")
print(rx.head(10))
print(rx.group_by("ilac_adi").agg(pl.len()).sort("len",descending=True))
dr=pl.read_parquet(R+"claims/drug_claim_lines.parquet")
print(dr.group_by("drug_name").agg(pl.len()).sort("len",descending=True))
