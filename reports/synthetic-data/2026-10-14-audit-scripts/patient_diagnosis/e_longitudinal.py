"""(e) Longitudinal coherence of each patient's history, chronic flags, visit counters, cross-field agreement."""
from common import claims, episodes, write
import polars as pl

ep = episodes()
cd = claims("claim_diagnoses")
lines = []
P = lines.append

codes = cd.group_by("episode_id").agg(pl.col("icd10_code").alias("cd_codes"))
ep = ep.join(codes, left_on="SQ_EPISODE", right_on="episode_id", how="left").with_columns(
    pl.col("TUM_EPS_TANILAR").str.split(",").alias("tum"),
)
ep = ep.with_columns(pl.concat_list("tum", "cd_codes").list.unique().alias("all_codes"))

def has(pattern):
    return pl.col("all_codes").list.eval(pl.element().str.contains(pattern)).list.any()

ep = ep.with_columns(
    has(r"^E1[0-4]").alias("c_dm"),
    has(r"^I1[0-5]").alias("c_htn"),
    has(r"^I").alias("c_anyI"),
    has(r"^(D5|D6|D7|D8|C8[1-9]|C9)").alias("c_blood"),
    has(r"^C").alias("c_cancer"),
    ((pl.col("KB-S") > 140) | (pl.col("KB-D") > 90)).alias("bp_rule"),
)
F = {"Diyabet Hastada": "c_dm", "Hipertansiyon Hastada": "c_htn", "Kalp Damar Hastada": "c_anyI", "Kan Hastaliklari Hastada": "c_blood"}
P("== chronic flags vs the episode's own ICD codes (TUM_EPS_TANILAR U claim_diagnoses) ==")
for flag, cc in F.items():
    a = ep.filter(pl.col(flag) & ~pl.col(cc)).height
    b = ep.filter(~pl.col(flag) & pl.col(cc)).height
    P(f"{flag}: true={ep[flag].sum()}/94 | flag without matching code: {a} | matching code without flag: {b}")
P(f"diabetes code without Diyabet flag: {ep.filter(pl.col('c_dm') & ~pl.col('Diyabet Hastada')).select('SQ_EPISODE', 'tier', 'scenario_tag', 'all_codes').rows()}")
P(f"Hipertansiyon flag == (KB-S>140 or KB-D>90) on the same visit: {ep.filter(pl.col('Hipertansiyon Hastada') == pl.col('bp_rule')).height}/94  (flag derived from one random BP reading, not from I10)")
P(f"episodes coded I10-I15 whose flag is False: {ep.filter(pl.col('c_htn') & ~pl.col('Hipertansiyon Hastada')).height}; examples: {ep.filter(pl.col('c_htn') & ~pl.col('Hipertansiyon Hastada')).select('SQ_EPISODE','KB-S','KB-D').head(4).rows()}")
multi = ep.filter(pl.len().over("HASTA_ID") >= 2)
flips = multi.group_by("HASTA_ID").agg([pl.col(f).n_unique().alias(f) for f in F])
P(f"multi-episode patients: {flips.height}; patients whose patient-level chronic flag flips between episodes -> " + ", ".join(f"{f}: {flips.filter(pl.col(f) > 1).height}" for f in F))
# diabetes that disappears / appears
s = multi.sort("HASTA_ID", "edate").with_columns(pl.col("c_dm").cum_max().over("HASTA_ID").shift(1).over("HASTA_ID").fill_null(False).alias("dm_before"))
gone = s.filter(pl.col("dm_before") & ~pl.col("c_dm") & ~pl.col("Diyabet Hastada"))
P(f"later episodes of a known diabetic with no diabetes code AND no Diyabet flag: {gone.height} episodes, {gone['HASTA_ID'].n_unique()} patients")
s2 = multi.sort("HASTA_ID", "edate").with_columns(pl.col("c_cancer").cum_max().over("HASTA_ID").shift(1).over("HASTA_ID").fill_null(False).alias("ca_before"))
cgone = s2.filter(pl.col("ca_before") & ~pl.col("c_cancer"))
P(f"later episodes of a cancer patient with no C-code at all: {cgone.height} episodes, {cgone['HASTA_ID'].n_unique()} patients")
ca = ep.with_columns(pl.col("all_codes").list.eval(pl.element().filter(pl.element().str.starts_with("C")).str.slice(0, 3)).alias("cats")).explode("cats").drop_nulls("cats").group_by("HASTA_ID").agg(pl.col("cats").unique().sort())
P(f"patients with >=2 different primary-site cancers: {ca.filter(pl.col('cats').list.len() >= 2).rows()}")

P("\n== counters and cross-field agreement ==")
n_ep = ep.group_by("HASTA_ID").agg(pl.len().alias("n_ep"), pl.col("TOPLAM_GELIS_SAYISI").unique().alias("toplam"))
P(f"TOPLAM_GELIS_SAYISI == actual episode count: {n_ep.filter(pl.col('toplam').list.len() == 1).filter(pl.col('toplam').list.first() == pl.col('n_ep')).height}/50 patients; GELIS_SAYISI values: {ep['GELIS_SAYISI'].unique().to_list()}")
P(f"GELIS_TIPI == claim_type: {ep.filter(pl.col('GELIS_TIPI') == pl.col('claim_type')).height}/94; SERVISADI == department: {ep.filter(pl.col('SERVISADI') == pl.col('department')).height}/94; TANIKODU == primary_icd10: {ep.filter(pl.col('TANIKODU') == pl.col('primary_icd10')).height}/94")
P(f"department strings: {dict(ep.group_by('department').len().sort('department').iter_rows())}")
P(f"donem values: {ep['donem'].unique().to_list()}; episodes dated 2023 but donem=2024: {ep.filter((pl.col('edate').dt.year() == 2023) & (pl.col('donem') == '2024')).height}")
kc = ep.group_by("HASTA_ID").agg(pl.col("kohort").first(), pl.col("c_cancer").any().alias("any_cancer"))
P(f"kohort values: {dict(kc.group_by('kohort').len().sort('kohort').iter_rows())}; kohort=cancer with no C-code ever: {kc.filter((pl.col('kohort') == 'cancer') & ~pl.col('any_cancer')).height}/{kc.filter(pl.col('kohort') == 'cancer').height}; patients with a C-code not in kohort=cancer: {kc.filter((pl.col('kohort') != 'cancer') & pl.col('any_cancer')).height}/{kc.filter(pl.col('any_cancer')).height}")

# chronology of episode numbering
o = multi.with_columns(pl.col("SQ_EPISODE").str.slice(-3).cast(pl.Int32).alias("seq"), pl.col("edate").rank("ordinal").over("HASTA_ID").cast(pl.Int32).alias("chron"))
nonchron = o.group_by("HASTA_ID").agg((pl.col("seq") == pl.col("chron")).all().alias("ok")).filter(~pl.col("ok"))
P(f"multi-episode patients whose episode numbers (…-001, -002 …) are NOT in date order: {nonchron.height}/{o['HASTA_ID'].n_unique()}")
# overlapping stays
iv = ep.select("HASTA_ID", "claim_id", "cstart", "cend", "claim_type")
ov = iv.join(iv, on="HASTA_ID", suffix="_b").filter((pl.col("claim_id") < pl.col("claim_id_b")) & (pl.col("cstart") <= pl.col("cend_b")) & (pl.col("cstart_b") <= pl.col("cend")))
P(f"same-patient claims with overlapping date ranges: {ov.height} -> {ov.select('claim_id', 'claim_type', 'cstart', 'cend', 'claim_id_b', 'claim_type_b', 'cstart_b', 'cend_b').rows()}")
gaps = ep.sort("HASTA_ID", "cstart").with_columns((pl.col("cstart") - pl.col("cend").shift(1).over("HASTA_ID")).dt.total_days().alias("gap"))
P(f"min gap (days) between a discharge and the same patient's next claim: {gaps['gap'].min()}")

P("\n== story coherence for multi-claim patients ==")
st = multi.sort("HASTA_ID", "edate").group_by("HASTA_ID", maintain_order=True).agg(
    pl.len().alias("n"),
    pl.col("tier").first(),
    pl.col("department").n_unique().alias("n_dept"),
    pl.col("primary_icd10").str.slice(0, 1).n_unique().alias("n_chapters"),
    pl.col("primary_icd10").str.slice(0, 3).n_unique().alias("n_primary_cat"),
    pl.col("all_codes").list.explode().value_counts().alias("vc"),
)
st = st.with_columns(
    (pl.col("n_primary_cat") == pl.col("n")).alias("no_primary_repeat"),
    pl.col("vc").list.eval(pl.element().struct.field("count") > 1).list.any().alias("any_code_repeat"),
).drop("vc")
P(f"patients: {st.height}; all primaries in different ICD categories: {st['no_primary_repeat'].sum()}; every episode in a different ICD chapter: {st.filter(pl.col('n_chapters') == pl.col('n')).height}; >=3 departments: {st.filter(pl.col('n_dept') >= 3).height}; share no code at all across episodes: {st.filter(~pl.col('any_code_repeat')).height}")
P(str(st))
tl = multi.sort("HASTA_ID", "edate").with_columns(
    pl.format("{} {} {} {}[{}]", pl.col("edate"), pl.col("claim_type"), pl.col("department"), pl.col("primary_icd10"), pl.col("TUM_EPS_TANILAR")).alias("s")
).group_by("HASTA_ID", maintain_order=True).agg(pl.col("TANI_YASI").first().alias("age"), pl.col("CINSIYET").first().alias("sex"), pl.col("tier").first(), pl.col("s").str.join(" -> "))
for pid in ["SENTETIK-HASTA-0003", "SENTETIK-HASTA-0002", "SENTETIK-HASTA-0045", "SENTETIK-HASTA-0038", "SENTETIK-HASTA-0039"]:
    r = tl.filter(pl.col("HASTA_ID") == pid).row(0, named=True)
    P(f"TIMELINE {pid} ({r['sex']}, {r['age']}y at first visit, tier {r['tier']}): {r['s']}")

P("\n== department vs primary diagnosis (judgment mapping) ==")
c3 = pl.col("primary_icd10").str.slice(0, 3)
solid = (c3 >= "C00") & (c3 <= "C80")
heme = (c3 >= "C81") & (c3 <= "C96")
dm = ep.with_columns(
    pl.when(solid & (pl.col("department") == "Hematoloji")).then(pl.lit("solid tumour in Hematoloji"))
    .when(heme & ~pl.col("department").is_in(["Hematoloji", "Onkoloji"])).then(pl.lit("haematologic malignancy outside Hematoloji/Onkoloji"))
    .when(solid & ~pl.col("department").is_in(["Onkoloji", "Hematoloji", "Gogus Hastaliklari", "genel_cerrahi"])).then(pl.lit("solid tumour in unrelated dept"))
    .otherwise(None).alias("dept_issue")
).filter(pl.col("dept_issue").is_not_null())
P(f"department/diagnosis mismatches: {dm.height}")
P("\n".join(f"  {r}" for r in dm.select("SQ_EPISODE", "tier", "CINSIYET", "TANI_YASI", "department", "primary_icd10", "claim_type", "dept_issue").rows()))
acute_outpt = ep.filter(pl.col("primary_icd10").is_in(["J96.0", "I21.4", "I63.9", "N17.9", "J15.4", "J18.9", "S72.0", "G61.0", "K85.9"]) & pl.col("claim_type").is_in(["poliklinik", "koruyucu", "meslek_hastaligi", "gunubirlik"]))
P(f"acute/inpatient-type primaries billed as poliklinik/koruyucu/meslek/gunubirlik (judgment): {acute_outpt.height}")
P("\n".join(f"  {r}" for r in acute_outpt.select("SQ_EPISODE", "tier", "TANI_YASI", "claim_type", "department", "primary_icd10").rows()))
odd_type = ep.filter((pl.col("claim_type") == "koruyucu") | (pl.col("claim_type") == "meslek_hastaligi") | ((pl.col("claim_type") == "acil") & pl.col("primary_icd10").is_in(["E66.9", "E02", "E03.9", "M16.1"])))
P(f"preventive / occupational / emergency claims with a mismatched primary (judgment): {odd_type.select('SQ_EPISODE','tier','claim_type','department','primary_icd10').rows()}")
los = ep.filter(pl.col("claim_type") == "yatis").with_columns((pl.col("cend") - pl.col("cstart")).dt.total_days().alias("los"))
P(f"inpatient LOS for low-acuity primaries (judgment): {los.filter(pl.col('primary_icd10').is_in(['E78.0','E66.9','M77.1','M23.2','G47.3','M54.5','M75.1'])).select('SQ_EPISODE','tier','primary_icd10','los').rows()}")
write("e_longitudinal.txt", "\n".join(lines))
