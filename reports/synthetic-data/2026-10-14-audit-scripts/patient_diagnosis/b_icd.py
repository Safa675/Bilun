"""(b) ICD-10: format, sex/age plausibility, dagger/asterisk, three-source agreement.

No ICD-10 catalog exists in the repo; code titles below are WHO ICD-10 titles from domain knowledge (judgment).
"""
from common import claims, episodes, write, icd3
import polars as pl

ep = episodes()
cd = claims("claim_diagnoses")
lines = []
P = lines.append

# ---- long table of every code occurrence, by source ----
src_hdr = ep.select(pl.col("SQ_EPISODE").alias("ep"), pl.col("primary_icd10").alias("code")).with_columns(pl.lit("claim_headers.primary_icd10").alias("src"))
src_tk = ep.select(pl.col("SQ_EPISODE").alias("ep"), pl.col("TANIKODU").alias("code")).with_columns(pl.lit("anadata.TANIKODU").alias("src"))
src_all = (
    ep.select(pl.col("SQ_EPISODE").alias("ep"), pl.col("TUM_EPS_TANILAR").str.split(",").alias("code"))
    .explode("code").with_columns(pl.col("code").str.strip_chars(), pl.lit("anadata.TUM_EPS_TANILAR").alias("src"))
)
src_cd = cd.select(pl.col("episode_id").alias("ep"), pl.col("icd10_code").alias("code")).with_columns(pl.lit("claim_diagnoses").alias("src"))
occ = pl.concat([src_hdr, src_tk, src_all, src_cd]).join(
    ep.select(pl.col("SQ_EPISODE").alias("ep"), "HASTA_ID", "tier", "CINSIYET", "TANI_YASI", "department", "claim_type"), on="ep", how="left"
)
P(f"code occurrences by source: {dict(occ.group_by('src').len().sort('src').iter_rows())}")
P(f"distinct codes overall: {occ['code'].n_unique()}  -> {sorted(occ['code'].unique().to_list())}")

# ---- format ----
fmt_ok = pl.col("code").str.contains(r"^[A-Z][0-9]{2}(\.[0-9]{1,2})?$")
bad = occ.filter(~fmt_ok)
P(f"format violations (WHO pattern A00 / A00.0): {bad.height}/{occ.height}")

# ---- sex-specific ----
c3 = icd3(pl.col("code"))
female_only = ((c3 >= "O00") & (c3 <= "O99")) | ((c3 >= "N70") & (c3 <= "N98")) | ((c3 >= "C51") & (c3 <= "C58")) | c3.is_in(["D06", "D25", "D26", "D27", "D28", "D39", "E28", "Z32", "Z33", "Z34", "Z35", "Z36", "Z37", "Z39"])
male_only = ((c3 >= "N40") & (c3 <= "N51")) | ((c3 >= "C60") & (c3 <= "C63")) | c3.is_in(["D29", "D40", "E29"])
occ = occ.with_columns(female_only.alias("f_only"), male_only.alias("m_only"))
sexbad = occ.filter((pl.col("f_only") & (pl.col("CINSIYET") == "E")) | (pl.col("m_only") & (pl.col("CINSIYET") == "K")))
P(f"sex-specific codes present: female-only occurrences={occ['f_only'].sum()}, male-only occurrences={occ['m_only'].sum()}")
P(f"sex-incompatible ICD occurrences: {sexbad.height}")
P(str(occ.filter(pl.col("f_only") | pl.col("m_only")).unique(["ep", "code"]).select("ep", "code", "CINSIYET", "TANI_YASI", "department").sort("ep")))
mbc = occ.filter((c3 == "C50") & (pl.col("CINSIYET") == "E")).unique(["ep"]).select("ep", "tier", "CINSIYET", "TANI_YASI", "department")
allc50 = occ.filter(c3 == "C50").unique(["ep"])
P(f"C50 breast cancer episodes: {allc50.height}; in men: {mbc.height} (judgment: male breast cancer ~1% of cases)\n{mbc}")

# ---- age plausibility (judgment thresholds) ----
rules = [
    ("H25", 50, "senile cataract"),
    ("M81", 40, "osteoporosis w/o secondary cause"),
    ("M16", 35, "primary coxarthrosis"),
    ("M17", 35, "gonarthrosis"),
    ("C90", 35, "multiple myeloma"),
    ("C61", 45, "prostate cancer"),
    ("C18", 25, "colon cancer"),
    ("C34", 35, "lung cancer"),
    ("Z95", 40, "CABG status (Z95.1)"),
    ("I25", 30, "atherosclerotic heart disease"),
    ("I21", 30, "acute MI"),
    ("I20", 30, "angina"),
    ("I11", 30, "hypertensive heart disease + HF"),
    ("I50", 30, "heart failure"),
    ("I63", 30, "cerebral infarction"),
    ("E11", 25, "type 2 diabetes"),
    ("I10", 20, "essential hypertension"),
    ("I12", 30, "hypertensive renal disease + renal failure"),
    ("N18", 25, "chronic kidney disease"),
    ("N40", 40, "BPH"),
    ("G20", 40, "Parkinson"),
    ("K70", 30, "alcoholic liver disease"),
    ("J44", 40, "COPD"),
]
rows = []
for cat, thr, label in rules:
    hit = occ.filter((c3 == cat) & (pl.col("TANI_YASI") < thr)).unique(["ep", "code"]).with_columns(pl.lit(f"{cat}<{thr} {label}").alias("rule"))
    rows.append(hit.select("rule", "ep", "code", "CINSIYET", "TANI_YASI", "tier"))
agebad = pl.concat(rows)
P(f"age-implausible diagnosis instances (judgment thresholds): {agebad.height} instances, {agebad['ep'].n_unique()} episodes, {agebad.join(ep.select(pl.col('SQ_EPISODE').alias('ep'), 'HASTA_ID'), on='ep')['HASTA_ID'].n_unique()} patients")
P(str(agebad.sort("rule", "TANI_YASI")))
P(f"perinatal P-codes anywhere: {occ.filter(pl.col('code').str.starts_with('P')).height}")

# ---- asterisk without dagger: G63.2* requires E10-E14 with .4 ----
epcodes = occ.filter(pl.col("src") == "claim_diagnoses").group_by("ep").agg(pl.col("code").alias("codes"))
g632 = epcodes.filter(pl.col("codes").list.contains("G63.2")).with_columns(
    pl.col("codes").list.eval(pl.element().str.contains(r"^E1[0-4]\.4$")).list.any().alias("has_dagger"),
    pl.col("codes").list.eval(pl.element().str.contains(r"^E1[0-4]")).list.any().alias("has_any_dm"),
).join(ep.select(pl.col("SQ_EPISODE").alias("ep"), "tier", "TANI_YASI", "primary_icd10"), on="ep")
P(f"G63.2 (asterisk, diabetic polyneuropathy) episodes: {g632.height}; without E1x.4 dagger: {g632.filter(~pl.col('has_dagger')).height}; without ANY diabetes code: {g632.filter(~pl.col('has_any_dm')).height}")
P(str(g632.sort("ep")))

# ---- K80.2 gallbladder stone + Z90.4 (acquired absence of digestive organ, typically post-cholecystectomy) ----
kz = epcodes.filter(pl.col("codes").list.contains("K80.2") & pl.col("codes").list.contains("Z90.4"))
P(f"K80.2 + Z90.4 in same episode (judgment: possible contradiction): {kz.height} {kz['ep'].to_list()}")

# ---- three-source agreement ----
cdp = cd.filter(pl.col("is_primary")).group_by("episode_id").agg(pl.col("icd10_code").alias("cd_primary"), pl.len().alias("n_primary"))
cds = cd.group_by("episode_id").agg(pl.col("icd10_code").sort().alias("cd_set"), pl.len().alias("n_cd"))
ag = (
    ep.select("SQ_EPISODE", "HASTA_ID", "tier", "primary_icd10", "TANIKODU", "TUM_EPS_TANILAR")
    .join(cdp, left_on="SQ_EPISODE", right_on="episode_id", how="left")
    .join(cds, left_on="SQ_EPISODE", right_on="episode_id", how="left")
    .with_columns(pl.col("TUM_EPS_TANILAR").str.split(",").list.eval(pl.element().str.strip_chars()).alias("tum"))
    .with_columns(
        (pl.col("primary_icd10") == pl.col("TANIKODU")).alias("hdr_eq_tanikodu"),
        pl.col("cd_primary").list.contains(pl.col("primary_icd10")).alias("hdr_in_cd_primary"),
        (pl.col("tum").list.sort() == pl.col("cd_set")).alias("tum_eq_cdset"),
        (pl.col("tum").list.unique().list.sort() == pl.col("cd_set").list.unique().list.sort()).alias("tum_eq_cdset_unique"),
        pl.col("tum").list.contains(pl.col("TANIKODU")).alias("tanikodu_in_tum"),
        pl.col("cd_set").list.contains(pl.col("primary_icd10")).alias("hdr_in_cdset"),
        (pl.col("tum").list.len() != pl.col("tum").list.unique().list.len()).alias("dup_in_tum"),
        (pl.col("cd_set").list.len() != pl.col("cd_set").list.unique().list.len()).alias("dup_in_cd"),
    )
)
for c in ["hdr_eq_tanikodu", "hdr_in_cd_primary", "tum_eq_cdset", "tum_eq_cdset_unique", "tanikodu_in_tum", "hdr_in_cdset"]:
    P(f"{c}: true={ag[c].sum()} false={ag.height - ag[c].sum()}")
P(f"episodes with duplicate code in TUM_EPS_TANILAR: {ag['dup_in_tum'].sum()}; in claim_diagnoses: {ag['dup_in_cd'].sum()}")
P(f"episodes with !=1 primary in claim_diagnoses: {ag.filter(pl.col('n_primary') != 1).height}")
P(str(ag.filter(~pl.col("tanikodu_in_tum") | ~pl.col("tum_eq_cdset") | pl.col("dup_in_tum") | ~pl.col("hdr_in_cdset")).select("SQ_EPISODE", "tier", "primary_icd10", "TANIKODU", "TUM_EPS_TANILAR", "cd_set")))
P("header primary vs claim_diagnoses primary (mismatches): " + str(ag.filter(~pl.col("hdr_in_cd_primary")).select("SQ_EPISODE", "tier", "primary_icd10", "cd_primary").rows()))
write("b_icd.txt", "\n".join(lines))
