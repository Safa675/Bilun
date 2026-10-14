"""Material vs patient: age-labelled devices, diagnosis indication, within-claim coherence.

Age: anadata_clean.TANI_YASI via claim_headers.episode_id == SQ_EPISODE (cross-checked with
patient_copay_profiles.birth_year). Diagnoses: claim_diagnoses (all roles) + claim_headers.primary_icd10.
Indication regexes are JUDGMENT (generous: any plausibly related ICD-10 block counts).
"""
import os

import polars as pl

from common import B, HERE, load, norm_expr
from compat import material_family_expr

pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_rows(100)
pl.Config.set_fmt_str_lengths(55)
pl.Config.set_tbl_width_chars(250)

m, p, h, a, cp = load()
d = pl.read_parquet(B + "claim_diagnoses.parquet")
dx = (pl.concat([d.select("claim_id", "icd10_code"),
                 h.select("claim_id", pl.col("primary_icd10").alias("icd10_code"))])
      .unique().group_by("claim_id").agg(pl.col("icd10_code").sort().str.join(",").alias("dx")))
age = (h.select("claim_id", "episode_id", "claim_type", "department")
       .join(a.select(pl.col("SQ_EPISODE").alias("episode_id"), pl.col("TANI_YASI").alias("age"),
                      pl.col("CINSIYET").alias("sex")), on="episode_id", how="left"))
x = (m.select("material_line_id", "claim_id", "patient_id", "material_code", "material_name", "material_type",
              "billed_amount_try")
     .with_columns(material_family_expr().alias("family"), norm_expr("material_name").alias("k"))
     .join(age, on="claim_id", how="left").join(dx, on="claim_id", how="left"))
print("patients with material lines:", x["patient_id"].n_unique(), "| age range:", x["age"].min(), "-", x["age"].max(),
      "| missing age:", x["age"].is_null().sum())

# ---------- 1) age-labelled devices (label is in the EK-3 name itself) ----------
x = x.with_columns(
    pl.when(x["k"].str.contains(r"\bBEBEK")).then(pl.lit("INFANT"))
    .when(x["k"].str.contains(r"\bCOCUK|PEDIATRIK")).then(pl.lit("CHILD"))
    .when(x["k"].str.contains(r"ERISKIN|YETISKIN")).then(pl.lit("ADULT"))
    .otherwise(None).alias("age_label"))
x = x.with_columns(
    (((pl.col("age_label") == "INFANT") & (pl.col("age") >= 2)) | ((pl.col("age_label") == "CHILD") & (pl.col("age") >= 18))
     | ((pl.col("age_label") == "ADULT") & (pl.col("age") < 18))).alias("age_label_mismatch"))
lab = x.filter(pl.col("age_label").is_not_null())
print("\n[patient] age-labelled lines:", lab.height, "| mismatching patient age:", lab["age_label_mismatch"].sum())
print(lab.select(pl.col("material_line_id").str.replace("MLZ-F-SENTETIK-HASTA-", ""), "material_code", "material_name",
                 "age_label", "age", "age_label_mismatch"))
mix = lab.group_by("claim_id").agg(pl.col("age_label").unique().sort()).filter(pl.col("age_label").list.len() > 1)
print("claims mixing age labels (infant/child with adult device on same claim):", mix.height)
print(mix)

# ---------- 2) diagnosis indication (JUDGMENT table) ----------
AMPUT = r"Z89|T87|S48|S58|S68|S78|S88|S98|Q71|Q72|Q73|C40|C41"
IND = {
    "ARTHROPLASTY_IMPLANT": r"M05|M06|M08|M15|M16|M17|M19|M24|M87|M89|M96|S42|S72|S82|T84|Z96|C40|C41|C79\.5",
    "ORTHO_IMPLANT_GENERIC": r"M1[5-9]|M8[4-9]|S\d|T84|Z96",
    "APHERESIS": r"G61|G70|G35|G36|M31|M32|D59|D68|D69|D47|D89|T86|N0[0-8]|E78|K7[0-2]|A4[01]|R65|R57|L1[0-4]|H3[45]|I42|C90|C88|C9[1-5]|K5[01]|C84",
    "THALASSEMIA_PUMP_SET": r"D56|D57|D58|D61|D46|D64|E83\.1",
    "DIALYSIS_RRT": r"N1[7-9]|I12|I13|E87|T79\.5|R34",
    "AIRWAY_BRONCHOSCOPY": r"J38|J39|J95\.5|J98|J4[34]|J47|J1[2-8]|J84|J86|J96|R59|R91|D86|C3[234]|C78|C15|Q3[12]|T17|A15",
    "ESOPHAGEAL_STENT": r"C15|C16\.0|K22|J86|C34|C78",
    "THORACIC_SURGERY": r"Q67\.[67]|M95\.4|S2[27]|J9[0-4]|J86|C3[48]|C45|C78|T81|Z95|I2[05]|J1[2-8]",
    "ERCP": r"K8[0-6]|C2[2-5]|K91|S36",
    "CARDIAC_ICD": r"I4[2-9]|I50|I2[1-5]|Q2[0-4]",
}
ind_expr = pl.lit(None, pl.Boolean)
for fam, rx in IND.items():
    ind_expr = pl.when(pl.col("family") == fam).then(pl.col("dx").str.contains(rx)).otherwise(ind_expr)
# external prostheses split: amputation prostheses need an amputation/limb-deficiency code; orthoses tolerated
is_amp_prosthesis = (pl.col("family") == "EXT_PROSTHESIS_ORTHOSIS") & pl.col("k").str.contains(
    r"PROTEZ|SOKET|LINER|HARNESS|DEZARTIKULASYON|MYOELEKTRIK|BATARYA")
ind_expr = pl.when(is_amp_prosthesis).then(pl.col("dx").str.contains(AMPUT)).otherwise(ind_expr)
# airway STENTS / VALVES (therapeutic implants) need stenosis/tumour/fistula/emphysema - pneumonia or
# respiratory failure alone is not an indication (JUDGMENT); diagnostic items keep the generous list
AIRWAY_IMPLANT = r"J38|J39|J95\.5|J98|J43|J44|J86|C3[234]|C78|C15|Q3[12]|T17|A15|D14|D38"
is_airway_implant = (pl.col("family") == "AIRWAY_BRONCHOSCOPY") & pl.col("k").str.contains(r"STENT|VALF")
ind_expr = pl.when(is_airway_implant).then(pl.col("dx").str.contains(AIRWAY_IMPLANT)).otherwise(ind_expr)
x = x.with_columns(ind_expr.alias("indication_ok"), is_amp_prosthesis.alias("amputation_prosthesis"),
                   is_airway_implant.alias("airway_implant"))
chk = x.filter(pl.col("indication_ok").is_not_null())
print("\n[patient] diagnosis-indication check: lines evaluated", chk.height,
      "| no supporting ICD-10 on the claim:", (~chk["indication_ok"]).sum())
print(chk.group_by("family").agg(pl.len().alias("lines"), (~pl.col("indication_ok")).sum().alias("no_indication"),
                                 pl.col("dx").filter(~pl.col("indication_ok")).unique().alias("claim_dx_when_missing"))
      .sort("lines", descending=True))
aw = x.filter(pl.col("airway_implant"))
print("airway stent/valve lines:", aw.height, "| without stenosis/tumour/fistula/emphysema code:", (~aw["indication_ok"]).sum(),
      "| their claim dx:", aw["dx"].unique().sort().to_list())
amp = x.filter(pl.col("amputation_prosthesis"))
print("amputation-prosthesis lines:", amp.height, "| claims with any amputation code (Z89/T87/S48..S98/Q71-73):",
      amp.filter(pl.col("indication_ok"))["claim_id"].n_unique(), "| billed TRY:", round(amp["billed_amount_try"].sum(), 2))
print("whole cohort: claims carrying an amputation-status code:",
      d.filter(pl.col("icd10_code").str.contains(AMPUT))["claim_id"].n_unique())

# ---------- 3) arthroplasty site vs diagnosis site (EK-3F-1 'UYGULAMA YERİ' = name for AP codes) ----------
idn = pl.read_parquet(os.path.join(HERE, "identity.parquet")).select("material_line_id", "asof_full")
ap = (x.filter(pl.col("family") == "ARTHROPLASTY_IMPLANT").join(idn, on="material_line_id", how="left")
      .with_columns(pl.col("asof_full").str.split(" | ").list.first().alias("site_field"),
                    pl.when(pl.col("dx").str.contains(r"M16|S72\.[0-2]")).then(pl.lit("KALÇA"))
                    .when(pl.col("dx").str.contains(r"M17|S82\.[01]")).then(pl.lit("DİZ"))
                    .when(pl.col("dx").str.contains(r"M19\.0|S42\.[02]")).then(pl.lit("OMUZ")).otherwise(None).alias("dx_site")))
print("\n[patient] arthroplasty implant site vs diagnosis site (site-specific dx only):")
print(ap.select(pl.col("material_line_id").str.replace("MLZ-F-SENTETIK-HASTA-", ""), "material_code", "site_field", "dx",
                "dx_site", (pl.col("dx_site").is_not_null() & (pl.col("dx_site") != pl.col("site_field"))).alias("site_mismatch"), "age"))

# ---------- 4) within-claim device coherence (JUDGMENT): hip AND knee arthroplasty parts / amputee + arthroplasty ----------
per_claim = (x.join(idn, on="material_line_id", how="left")
             .with_columns(pl.when(pl.col("family") == "ARTHROPLASTY_IMPLANT").then(pl.col("asof_full").str.split(" | ").list.first()).alias("ap_site"))
             .group_by("claim_id").agg(pl.col("ap_site").drop_nulls().unique().sort().alias("ap_sites"),
                                       pl.col("amputation_prosthesis").any().alias("has_amp_prosthesis"),
                                       (pl.col("family") == "ARTHROPLASTY_IMPLANT").any().alias("has_arthroplasty"),
                                       pl.col("material_name").str.slice(0, 40).alias("materials"), pl.col("age").first()))
odd = per_claim.filter((pl.col("ap_sites").list.len() > 1) | (pl.col("has_amp_prosthesis") & pl.col("has_arthroplasty")))
print("\n[patient] claims mixing arthroplasty sites or amputation prosthesis + arthroplasty on one invoice:", odd.height)
print(odd.select("claim_id", "ap_sites", "has_amp_prosthesis", "has_arthroplasty", "age", "materials"))
x.write_parquet(os.path.join(HERE, "patient_fit.parquet"))
