"""(g) labs vs diagnosis / department / claim window / episode linkage."""
import polars as pl

from common import anadata, dx, ek2b, hdr, headers, labs, save

lb = labs()
h = headers()
names = ek2b().group_by("code").agg(pl.col("name").last().alias("ek2b_name"))

# judgment: a routine core panel any clinician expects to see somewhere in 83 episodes
ROUTINE = {
    "L107020": "Hemogram", "L102890": "Glukoz (serum)", "L104780": "Kreatinin (serum)", "L107420": "Üre",
    "L102820": "HbA1c", "L102830": "HbA1c HPLC", "L102840": "HbA1c elfo", "L100300": "ALT", "L101280": "AST",
    "L101850": "CRP", "L101840": "CRP lateks", "L107380": "TSH", "L106910": "Na", "L106150": "K",
    "L107250": "Trigliserid", "L105000": "LDL", "L100320": "Albümin", "L102410": "Ferritin", "L107010": "Tam idrar",
    "L106430": "PT/INR", "L107360": "Troponin I", "L107370": "Troponin T", "L106770": "sT4", "L107520": "B12",
    "L100220": "25-OH D", "L102120": "Demir", "L100710": "ALP", "L100800": "Amilaz", "L105100": "Lipaz",
    "L102090": "D-dimer", "L102450": "Fibrinojen",
}
tests = lb.select("basvuru_id", "SUB_CODE").unique().join(names, left_on="SUB_CODE", right_on="code", how="left")
cat = (
    pl.when(pl.col("SUB_CODE").is_in(list(ROUTINE))).then(pl.lit("routine_core"))
    .when(pl.col("ek2b_name").str.contains(r"(?i)oranı")).then(pl.lit("flow_cytometry_marker"))
    .when(pl.col("ek2b_name").str.contains(r"(?i)IgE antikoru")).then(pl.lit("specific_allergen_IgE"))
    .when(pl.col("ek2b_name").str.contains(r"(?i)uyarı testi|baskılama testi|öğün|yükleme testi|dakika")).then(pl.lit("single_timepoint_of_dynamic_test"))
    .when(pl.col("ek2b_name").str.contains(r"(?i)\(BOS\)|\(Kuru kan\)|\(Doku\)|\(Kemik iliği\)|\(Diğer|\(Vücut sıvıları\)")).then(pl.lit("unusual_specimen_CSF_tissue_dryblood"))
    .otherwise(pl.lit("other_specialised"))
)
tests = tests.with_columns(cat.alias("category"))

hdr("what was tested (169 episode-tests)")
print(tests.group_by("category").len().sort("len", descending=True))
print("routine core tests anywhere in the cohort:", tests.filter(pl.col("category") == "routine_core").height)
print(tests.filter(pl.col("category") == "other_specialised").select("ek2b_name").head(25))
save(tests, "g_lab_test_categories")

hdr("diabetics without HbA1c / glucose")
cdx = pl.concat([dx().select("claim_id", pl.col("icd10_code").alias("icd")), h.select("claim_id", pl.col("primary_icd10").alias("icd"))])
ep = h.select("claim_id", "episode_id", "patient_id", "department", "claim_type", "start", "end")
dm_claim = cdx.filter(pl.col("icd").str.slice(0, 3).is_between(pl.lit("E10"), pl.lit("E14"))).join(ep, on="claim_id").select("episode_id").unique()
a = anadata().select(pl.col("SQ_EPISODE").alias("episode_id"), pl.col("Diyabet Hastada").alias("dm_flag"))
dm_eps = pl.concat([dm_claim, a.filter(pl.col("dm_flag")).select("episode_id")]).unique()
lab_eps = lb.select(pl.col("basvuru_id").alias("episode_id")).unique()
dm_with_labs = dm_eps.join(lab_eps, on="episode_id")
glyc = {"L102820", "L102830", "L102840", "L102890", "L102940", "L102950"}
has_glyc = lb.filter(pl.col("SUB_CODE").is_in(list(glyc))).select(pl.col("basvuru_id").alias("episode_id")).unique()
print("diabetic episodes (E10-E14 on claim or 'Diyabet Hastada' flag):", dm_eps.height,
      "| with any lab:", dm_with_labs.height,
      "| with HbA1c or glucose:", dm_with_labs.join(has_glyc, on="episode_id").height)
ckd = cdx.filter(pl.col("icd").str.slice(0, 3).is_in(["N17", "N18", "N19"])).join(ep, on="claim_id").select("episode_id").unique().join(lab_eps, on="episode_id")
has_cr = lb.filter(pl.col("SUB_CODE").is_in(["L104780", "L107420"])).select(pl.col("basvuru_id").alias("episode_id")).unique()
print("renal-failure episodes (N17-N19) with labs:", ckd.height, "| with creatinine or urea:", ckd.join(has_cr, on="episode_id").height)
onc_eps = cdx.filter(pl.col("icd").str.slice(0, 1) == "C").join(ep, on="claim_id").select("episode_id").unique().join(lab_eps, on="episode_id")
has_cbc = lb.filter(pl.col("SUB_CODE") == "L107020").select(pl.col("basvuru_id").alias("episode_id")).unique()
print("cancer episodes (C codes) with labs:", onc_eps.height, "| with a hemogram:", onc_eps.join(has_cbc, on="episode_id").height)

hdr("department vs test category (examples)")
td = tests.join(ep, left_on="basvuru_id", right_on="episode_id", how="left")
print(td.group_by("department", "category").len().sort("department", "len", descending=[False, True]).head(40))
print(td.filter(pl.col("department").str.contains("(?i)ortopedi|kardiyoloji"))
      .select("department", "ek2b_name").head(15))

hdr("lab date vs claim window; linkage")
lw = lb.join(ep, left_on="basvuru_id", right_on="episode_id", how="left")
print("lab rows whose basvuru_id has no claim:", lw.filter(pl.col("claim_id").is_null()).height)
print("basvuru_id -> claims (max):", ep.group_by("episode_id").len()["len"].max())
print("patient on lab row == patient on claim:", (lw["HASTA_ID"] == lw["patient_id"]).sum(), "of", lw.height)
lw = lw.with_columns(pl.col("l_date").is_between(pl.col("start"), pl.col("end")).alias("in_window"),
                     (pl.col("l_date") == pl.col("start")).alias("on_day1"),
                     (pl.col("end") - pl.col("start")).dt.total_days().alias("los"))
print(lw.select(pl.len(), pl.col("in_window").sum(), pl.col("on_day1").sum()))
multi = lw.filter(pl.col("los") >= 1)
print("lab rows on multi-day stays:", multi.height, "| on admission day:", multi["on_day1"].sum(),
      "| episodes:", multi["basvuru_id"].n_unique(), "| max LOS:", multi["los"].max())
per_ep = lb.group_by("basvuru_id").agg(pl.col("SUB_CODE").n_unique().alias("tests"))
print("distinct tests per lab episode:", per_ep["tests"].value_counts().sort("tests").rows())
no_lab = h.join(lab_eps, left_on="episode_id", right_on="episode_id", how="anti")
print("claims with no lab at all:", no_lab.height, "| of which inpatient (yatis):", no_lab.filter(pl.col("claim_type") == "yatis").height)
