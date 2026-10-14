"""(c) Sex- and age-specific procedures, labs, drugs and materials vs the patient's sex/age.

Text is folded Turkish-aware (I->ı, İ->i, then diacritics stripped) before regex matching, so
'VAJINAL', 'Vajinal', 'VAJİNAL' all match r'\\bvajin'. Sources: procedure_claim_lines, drug_claim_lines,
material_claim_lines (joined via claim_id -> claim_headers.episode_id -> anadata), performed_procedure_lines.
"""
from common import claims, episodes, write, tr_fold
import polars as pl

ep = episodes().select("SQ_EPISODE", "claim_id", "HASTA_ID", "tier", "CINSIYET", "TANI_YASI", "department", "primary_icd10", "claim_type")
pr = claims("procedure_claim_lines").select("claim_id", pl.col("procedure_line_id").alias("line_id"), pl.col("procedure_code").alias("code"), pl.col("procedure_name").alias("name"), pl.col("procedure_category").alias("cat")).with_columns(pl.lit("procedure").alias("src"))
dr = claims("drug_claim_lines").select("claim_id", pl.col("drug_claim_line_id").alias("line_id"), pl.col("drug_code").alias("code"), pl.col("drug_name").alias("name")).with_columns(pl.lit("ilac").alias("cat"), pl.lit("drug").alias("src"))
ma = claims("material_claim_lines").select("claim_id", pl.col("material_line_id").alias("line_id"), pl.col("material_code").alias("code"), pl.col("material_name").alias("name")).with_columns(pl.lit("malzeme").alias("cat"), pl.lit("material").alias("src"))
pp = claims("performed_procedure_lines").select("claim_id", pl.col("performed_line_id").alias("line_id"), pl.col("procedure_code").alias("code"), pl.col("procedure_name").alias("name")).with_columns(pl.lit("emr_performed").alias("cat"), pl.lit("performed").alias("src"))
allx = pl.concat([pr, dr, ma, pp], how="diagonal").join(ep, on="claim_id", how="left").with_columns(tr_fold(pl.col("name")).alias("f"))
lines = []
P = lines.append
P(f"lines scanned: {allx.height} ({dict(allx.group_by('src').len().sort('src').iter_rows())}); unjoined to patient: {allx.filter(pl.col('CINSIYET').is_null()).height}")

MALE_ONLY = [r"\bpenil", r"\bpenis(?:e|in|te|ten)?\b", r"\bpenektomi", r"\bskrot", r"\btestis", r"\btestik", r"\borsi", r"\bprostat", r"\bvazektomi", r"\bsunnet", r"\bhidrosel", r"\bvarikosel", r"\bepididim", r"\bspermatosel", r"\bkriptorsid", r"\bspermiyogram", r"\bsemen\b", r"\bpsa\b"]
FEMALE_ONLY = [r"\bvajin", r"\bvajen", r"\bvulva", r"\buter", r"\brahim", r"(?:^|[\s(,/])over\b", r"\bovaryan", r"\booforektomi", r"\bmyom", r"\bhisterektomi", r"\bhisteroskopi", r"\bsezaryen", r"\bdogum\b", r"\bdogumu\b", r"\bserviks", r"\bkolposkopi", r"\bkonizasyon", r"\bsalpenj", r"\bsalping", r"\bendometri", r"\bdouglas", r"\bkuldosentez", r"\bovul\b", r"\bjinekolo", r"\bobstetri", r"\bgebe", r"\banne sutu", r"\blaktasyon", r"\binseminasyon", r"\bembriyo", r"\boosit", r"\bsistorektosel", r"\bkolpo"]
FEMALE_ONLY_EXCLUDE = r"\bbrca"  # 'Ailesel Meme/Over Kanseri (BRCA1/2)' is tested in both sexes
FERTILITY = [r"\binseminasyon", r"\bembriyo", r"\boosit", r"\btup bebek"]  # biologically implausible in women >= 50 (judgment threshold)
FEMALE_PRED = [r"\bmammoplasti", r"\bpresakral norektomi", r"\bbeta hcg \(idrar\)", r"\baromasin"]  # judgment
MALE_PRED_DRUG = [r"\bkoate", r"\bbenefix", r"\bnovoeight", r"\brefacto", r"\bxalfu"]  # judgment: X-linked haemophilia A/B concentrates; alfuzosin (BPH)
MALE_PRED_PROC = [r"testosteron-hcg"]  # judgment: Leydig-cell (testicular) stimulation test
INFANT = [r"\bbebek", r"\byenidogan", r"\bpremat", r"\b2 yas alti", r"\bneonat", r"\binfant", r"\bkonakion mm ped"]  # wrong for anyone >= 2 y
CHILD = [r"\bcocuk", r"\bpediatrik", r"\bped\b", r"\bpediasure", r"\badolesan", r"\bokul\b"]  # wrong for adults >= 18
CHILD_JUDG = [r"\bkonjenital", r"\bdogumsal", r"kuru kan", r"\berb palsi", r"\bseptostomi", r"-hcg uyari testi"]  # paediatric-predominant (judgment)
CHILD_JUDG_DRUG = [r"(?:susp|surup).*(?:mg\s*/\s*5\s*ml|mg/ml oral)|(?:mg\s*/\s*5\s*ml|mg/ml oral).*(?:susp|surup)|\bes 600"]  # paediatric oral suspension strengths (judgment)
ADULT_ONLY = [r"\beriskin", r"\byetiskin"]  # wrong for < 18


def any_of(pats):
    e = pl.lit(False)
    for p in pats:
        e = e | pl.col("f").str.contains(p)
    return e


is_drug = pl.col("src") == "drug"
allx = allx.with_columns(
    any_of(MALE_ONLY).alias("m_only"),
    (any_of(FEMALE_ONLY) & ~pl.col("f").str.contains(FEMALE_ONLY_EXCLUDE)).alias("f_only"),
    any_of(FERTILITY).alias("fert"),
    any_of(FEMALE_PRED).alias("f_pred"),
    ((any_of(MALE_PRED_DRUG) & is_drug) | any_of(MALE_PRED_PROC)).alias("m_pred"),
    any_of(INFANT).alias("infant"),
    any_of(CHILD).alias("child"),
    (any_of(CHILD_JUDG) | (any_of(CHILD_JUDG_DRUG) & is_drug)).alias("child_j"),
    any_of(ADULT_ONLY).alias("adult"),
)
cols = ["src", "claim_id", "tier", "CINSIYET", "TANI_YASI", "department", "primary_icd10", "code", "name"]


def rows(df):
    return "\n".join("  " + " | ".join(str(v) for v in r) for r in df.iter_rows())


P("KEYWORDS (regex on Turkish-folded text):")
for k, v in [("MALE_ONLY", MALE_ONLY), ("FEMALE_ONLY", FEMALE_ONLY), ("FERTILITY(F>=50)", FERTILITY), ("FEMALE_PRED(judgment)", FEMALE_PRED), ("MALE_PRED_DRUG(judgment)", MALE_PRED_DRUG), ("MALE_PRED_PROC(judgment)", MALE_PRED_PROC), ("INFANT(>=2y wrong)", INFANT), ("CHILD(>=18y wrong)", CHILD), ("CHILD_JUDG", CHILD_JUDG), ("CHILD_JUDG_DRUG", CHILD_JUDG_DRUG), ("ADULT_ONLY(<18 wrong)", ADULT_ONLY)]:
    P(f"  {k}: {v}")

P("\n== every male-only / female-only hit (compatible ones included, to show the matches are real) ==")
P(rows(allx.filter(pl.col("m_only") | pl.col("f_only")).select(["m_only", "f_only"] + cols).sort("claim_id")))
sex_bad = allx.filter((pl.col("m_only") & (pl.col("CINSIYET") == "K")) | (pl.col("f_only") & (pl.col("CINSIYET") == "E")))
P(f"\nSTRICT sex-incompatible lines: {sex_bad.height} of {allx.filter(pl.col('m_only') | pl.col('f_only')).height} sex-specific lines; patients={sex_bad['HASTA_ID'].n_unique()}")
P(rows(sex_bad.select(cols).sort("claim_id")))
fert_bad = allx.filter(pl.col("fert") & (pl.col("CINSIYET") == "K") & (pl.col("TANI_YASI") >= 50))
P(f"\nFertility procedures on women >=50 (judgment threshold): {fert_bad.height}")
P(rows(fert_bad.select(cols)))
pred_bad = allx.filter((pl.col("m_pred") & (pl.col("CINSIYET") == "K")) | (pl.col("f_pred") & (pl.col("CINSIYET") == "E")))
P(f"\nSex-PREDOMINANT mismatches (judgment): {pred_bad.height} of {allx.filter(pl.col('m_pred') | pl.col('f_pred')).height} sex-predominant lines")
P(rows(allx.filter(pl.col("m_pred") | pl.col("f_pred")).select(["m_pred", "f_pred"] + cols).sort("claim_id")))
inf_bad = allx.filter(pl.col("infant") & (pl.col("TANI_YASI") >= 2))
P(f"\nINFANT-only items on patients aged >=2: {inf_bad.height} of {allx.filter(pl.col('infant')).height}")
P(rows(inf_bad.select(cols).sort("claim_id")))
ch_bad = allx.filter(pl.col("child") & ~pl.col("infant") & (pl.col("TANI_YASI") >= 18))
P(f"\nCHILD-only items on adults >=18: {ch_bad.height} of {allx.filter(pl.col('child') & ~pl.col('infant')).height}")
P(rows(ch_bad.select(cols).sort("claim_id")))
age_strict = pl.concat([inf_bad, ch_bad])
P(f"\nSTRICT age-incompatible lines (infant>=2y + child>=18y): {age_strict.height} lines, {age_strict['HASTA_ID'].n_unique()} patients, {age_strict['claim_id'].n_unique()} claims")
cj = allx.filter(pl.col("child_j") & ~pl.col("child") & ~pl.col("infant"))
P(f"\nPaediatric-PREDOMINANT items (judgment) on patients aged {cj['TANI_YASI'].min()}..{cj['TANI_YASI'].max()}: {cj.height}")
P(rows(cj.select(cols).sort("claim_id")))
ad_bad = allx.filter(pl.col("adult") & (pl.col("TANI_YASI") < 18))
P(f"\nADULT-only items on minors: {ad_bad.height} of {allx.filter(pl.col('adult')).height}")
minors = allx.filter(pl.col("TANI_YASI") < 18).select(cols)
P(f"\nAll lines on minors (16y, 17y) for manual review: {minors.height}")
P(rows(minors))
strict = pl.concat([sex_bad, fert_bad, inf_bad, ch_bad])
P(f"\nTOTAL strict sex/age-incompatible lines: {strict.height}; patients: {strict['HASTA_ID'].n_unique()}/50; claims: {strict['claim_id'].n_unique()}/94")
P(f"Tier A patients with a strict sex/age-incompatible line: {sorted(strict.filter(pl.col('tier') == 'A')['HASTA_ID'].unique().to_list())}")
allx.select(["m_only", "f_only", "fert", "m_pred", "f_pred", "infant", "child", "child_j", "adult"] + cols).write_csv("out/c_all_lines_flags.csv")
write("c_sex_age_lines.txt", "\n".join(lines))
