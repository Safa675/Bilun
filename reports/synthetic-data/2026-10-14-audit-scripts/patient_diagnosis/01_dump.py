import polars as pl
pl.Config.set_tbl_cols(60); pl.Config.set_fmt_str_lengths(60); pl.Config.set_tbl_width_chars(400); pl.Config.set_tbl_rows(500)
R="/home/safa/Documents/Bilun/data/synthetic/sut/"
ch=pl.read_parquet(R+"claims/claim_headers.parquet")
print(ch.select("claim_id","episode_id","claim_type","occupational_context","facility_tier","provider_type","department","admission_date","discharge_date","claim_start_date","claim_end_date","primary_icd10","scenario_tag"))
an=pl.read_parquet(R+"clean/anadata_clean.parquet")
print(an.select("HASTA_ID","SQ_EPISODE","EPISODE_TARIH","TANI_YASI","CINSIYET","KB-S","KB-D","Nabiz","SPO2","Boy","Kilo","BMI","ILK_TANI_SON_TANI_GUN_FARKI","TOPLAM_GELIS_SAYISI","GELIS_SAYISI","GELIS_TIPI","SERVISADI","TANIKODU","TUM_EPS_TANILAR","TANI_TIPI"))
print(an.select("HASTA_ID","SQ_EPISODE","TANITARIH","MIN_TANI_TARIH","MAX_TANI_TARIH","Hipertansiyon Hastada","Kalp Damar Hastada","Diyabet Hastada","Kan Hastaliklari Hastada","kohort","donem"))
