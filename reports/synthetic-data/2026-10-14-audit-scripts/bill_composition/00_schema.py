import polars as pl
pl.Config.set_tbl_cols(50); pl.Config.set_tbl_width_chars(250); pl.Config.set_fmt_str_lengths(80)
R = "/home/safa/Documents/Bilun/data/synthetic/sut"
files = [f"{R}/claims/{n}.parquet" for n in ["claim_headers","procedure_claim_lines","drug_claim_lines","material_claim_lines","claim_diagnoses","expected_rule_outputs","medula_rejection_events","patient_copay_profiles","performed_procedure_lines"]] + [f"{R}/clean/{n}.parquet" for n in ["anadata_clean","lab_clean","recete_clean"]]
for f in files:
    df = pl.read_parquet(f)
    print("=====", f.split("/sut/")[1], df.shape)
    for c, t in df.schema.items():
        s = df[c]
        nn = s.null_count()
        nu = s.n_unique()
        ex = s.drop_nulls().head(3).to_list()
        print(f"  {c:40s} {str(t):20s} nulls={nn:5d} nuniq={nu:5d} ex={ex}")
