import polars as pl
pl.Config.set_tbl_cols(60); pl.Config.set_fmt_str_lengths(300); pl.Config.set_tbl_width_chars(400); pl.Config.set_tbl_rows(30)
R="/home/safa/Documents/Bilun/data/synthetic/sut/"
an=pl.read_parquet(R+"clean/anadata_clean.parquet")
for c in ["YAKINMA","OYKU","Muayene Notu","Tedavi Notu"]:
    print("==",c, "n_unique=",an[c].n_unique(), "nulls=", an[c].null_count())
    print(an.select(c).head(6).to_series().to_list())
cp=pl.read_parquet(R+"claims/patient_copay_profiles.parquet")
print(cp)
cd=pl.read_parquet(R+"claims/claim_diagnoses.parquet")
print(cd.head(12))
