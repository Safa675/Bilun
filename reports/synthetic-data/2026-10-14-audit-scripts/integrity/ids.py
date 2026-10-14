import polars as pl
B = "/home/safa/Documents/Bilun/data/synthetic/sut/"
H = pl.read_parquet(B+"claims/claim_headers.parquet")
P = pl.read_parquet(B+"claims/procedure_claim_lines.parquet")
D = pl.read_parquet(B+"claims/drug_claim_lines.parquet")
M = pl.read_parquet(B+"claims/material_claim_lines.parquet")
G = pl.read_parquet(B+"claims/claim_diagnoses.parquet")
E = pl.read_parquet(B+"claims/expected_rule_outputs.parquet")
R = pl.read_parquet(B+"claims/medula_rejection_events.parquet")
A = pl.read_parquet(B+"clean/anadata_clean.parquet")
L = pl.read_parquet(B+"clean/lab_clean.parquet")
X = pl.read_parquet(B+"clean/recete_clean.parquet")
C = pl.read_parquet(B+"claims/patient_copay_profiles.parquet")
hk = H.select("claim_id","patient_id","episode_id")
print("dup claim_id", H["claim_id"].is_duplicated().sum(), "dup episode", H["episode_id"].is_duplicated().sum())
for name, T, idc in [("proc",P,"procedure_line_id"),("drug",D,"drug_claim_line_id"),("mat",M,"material_line_id"),("diag",G,"diagnosis_id")]:
    j = T.join(hk, on="claim_id", how="left", suffix="_h")
    orphan = j.filter(pl.col("patient_id_h").is_null()).height
    pid_mis = j.filter(pl.col("patient_id_h").is_not_null() & (pl.col("patient_id")!=pl.col("patient_id_h"))).height
    ep_mis = j.filter(pl.col("episode_id_h").is_not_null() & (pl.col("episode_id")!=pl.col("episode_id_h"))).height if "episode_id" in T.columns else "n/a"
    print(f"{name}: rows={T.height} dup_id={T[idc].is_duplicated().sum()} orphan_claim={orphan} patient_mismatch={pid_mis} episode_mismatch={ep_mis}")
print("claims without procedure lines:", H.join(P.select("claim_id").unique(), on="claim_id", how="anti").height)
print("claims without diagnoses:", H.join(G.select("claim_id").unique(), on="claim_id", how="anti").height)
# material -> procedure link
mp = M.join(P.select("procedure_line_id", pl.col("claim_id").alias("p_claim")), on="procedure_line_id", how="left")
print("material lines: null proc link", M["procedure_line_id"].is_null().sum(), "dangling", mp.filter(pl.col("procedure_line_id").is_not_null() & pl.col("p_claim").is_null()).height, "cross-claim link", mp.filter(pl.col("p_claim").is_not_null() & (pl.col("p_claim")!=pl.col("claim_id"))).height)
# anadata episodes vs headers
print("anadata episodes not in headers:", A.join(H.select(pl.col("episode_id").alias("SQ_EPISODE")), on="SQ_EPISODE", how="anti").height, "| header episodes not in anadata:", H.join(A.select(pl.col("SQ_EPISODE").alias("episode_id")), on="episode_id", how="anti").height)
print("anadata HASTA_ID vs header patient on episode mismatch:", A.join(H.select(pl.col("episode_id").alias("SQ_EPISODE"), "patient_id"), on="SQ_EPISODE").filter(pl.col("HASTA_ID")!=pl.col("patient_id")).height)
# recete / lab linkage
print("recete RF_EPISODE sample:", X["RF_EPISODE"].head(3).to_list(), "| in header episodes:", X.join(H.select(pl.col("episode_id").alias("RF_EPISODE")), on="RF_EPISODE", how="semi").height, "/", X.height)
print("lab basvuru_id sample:", L["basvuru_id"].head(3).to_list(), "| in header episodes:", L.join(H.select(pl.col("episode_id").alias("basvuru_id")), on="basvuru_id", how="semi").height, "/", L.height, "| in claim ids:", L.join(H.select(pl.col("claim_id").alias("basvuru_id")), on="basvuru_id", how="semi").height)
# expected outputs / medula references
lines = pl.concat([P.select(pl.col("procedure_line_id").alias("line_id")), D.select(pl.col("drug_claim_line_id").alias("line_id")), M.select(pl.col("material_line_id").alias("line_id"))])
print("expected outputs: claim missing", E.join(H.select("claim_id"), on="claim_id", how="anti").height, "| line_id null", E["line_id"].is_null().sum(), "| line_id not found", E.filter(pl.col("line_id").is_not_null() & (pl.col("line_id")!="")).join(lines, on="line_id", how="anti").height, "/", E.height)
print("medula events: claim missing", R.join(H.select("claim_id"), on="claim_id", how="anti").height)
# patients
pats = H["patient_id"].unique()
print("patients in headers", pats.len(), "| copay profiles", C.height, "| copay without claims", C.join(H.select("patient_id").unique(), on="patient_id", how="anti").height)
print("patients with labs", L["HASTA_ID"].n_unique(), "| with recete", X["HASTA_ID"].n_unique(), "| with drug lines", D["patient_id"].n_unique(), "| with materials", M["patient_id"].n_unique())
