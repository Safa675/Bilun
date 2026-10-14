import polars as pl
pl.Config.set_tbl_cols(60); pl.Config.set_fmt_str_lengths(80); pl.Config.set_tbl_width_chars(250)
R="/home/safa/Documents/Bilun/data/synthetic/sut/"
files={"claim_headers":"claims/claim_headers.parquet","procedure_claim_lines":"claims/procedure_claim_lines.parquet","drug_claim_lines":"claims/drug_claim_lines.parquet","material_claim_lines":"claims/material_claim_lines.parquet","claim_diagnoses":"claims/claim_diagnoses.parquet","expected_rule_outputs":"claims/expected_rule_outputs.parquet","medula_rejection_events":"claims/medula_rejection_events.parquet","patient_copay_profiles":"claims/patient_copay_profiles.parquet","performed_procedure_lines":"claims/performed_procedure_lines.parquet","anadata_clean":"clean/anadata_clean.parquet","lab_clean":"clean/lab_clean.parquet","recete_clean":"clean/recete_clean.parquet"}
for k,v in files.items():
    df=pl.read_parquet(R+v)
    print("=====",k,df.shape)
    for c,t in df.schema.items():
        print(f"   {c}: {t}")
