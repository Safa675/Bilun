"""(d) Per-claim diagnosis sets: counts, primary/secondary, dates vs claim window, EK-1A exemption flag."""
from common import claims, clean, episodes, write, CURATED
import polars as pl

ep = episodes()
cd = claims("claim_diagnoses")
lines = []
P = lines.append

# counts per claim
cnt = cd.group_by("claim_id").agg(pl.len().alias("n"), pl.col("is_primary").sum().alias("n_primary"))
P(f"claims with diagnoses: {cnt.height}/94; dx per claim distribution: {dict(cnt.group_by('n').len().sort('n').iter_rows())}")
P(f"claims with exactly 1 primary: {cnt.filter(pl.col('n_primary') == 1).height}")
P(f"role/is_primary agreement: {cd.filter((pl.col('diagnosis_role') == 'birincil') == pl.col('is_primary')).height}/{cd.height}; roles: {dict(cd.group_by('diagnosis_role').len().iter_rows())}")
P(f"claim_diagnoses.claim_id vs episode_id consistent with claim_headers: {cd.join(ep.select('claim_id', 'SQ_EPISODE'), on='claim_id').filter(pl.col('episode_id') == pl.col('SQ_EPISODE')).height}/{cd.height}")

# dates
d = cd.join(ep.select("claim_id", "cstart", "cend", "claim_type", "HASTA_ID"), on="claim_id").with_columns(pl.col("diagnosis_date").str.to_date().alias("dd"))
P(f"diagnosis_date == claim_start_date: {d.filter(pl.col('dd') == pl.col('cstart')).height}/{d.height}; outside [start,end]: {d.filter((pl.col('dd') < pl.col('cstart')) | (pl.col('dd') > pl.col('cend'))).height}")
an = clean("anadata_clean")
P(f"anadata TANITARIH==MIN_TANI_TARIH==MAX_TANI_TARIH==EPISODE_TARIH: {an.filter((pl.col('TANITARIH') == pl.col('EPISODE_TARIH')) & (pl.col('MIN_TANI_TARIH') == pl.col('EPISODE_TARIH')) & (pl.col('MAX_TANI_TARIH') == pl.col('EPISODE_TARIH'))).height}/{an.height}; ILK_TANI_SON_TANI_GUN_FARKI==0: {an.filter(pl.col('ILK_TANI_SON_TANI_GUN_FARKI') == 0).height}/{an.height}; TANI_TIPI values: {an['TANI_TIPI'].unique().to_list()}")
# chronic code re-dated at every visit
chronic = pl.col("icd10_code").str.contains(r"^(E1[0-4]|I1[0-5]|I2[0-5]|I48|I50|N18|J44|J45|E03|E05|E78|E66|G35|G20|G40|C\d\d|M81|M17|M16|K70|Z95|Z96)")
rp = d.filter(chronic).group_by("HASTA_ID", "icd10_code").agg(pl.col("dd").n_unique().alias("n_dates"), pl.col("episode_id").n_unique().alias("n_ep"), pl.col("dd").min().alias("first"), pl.col("dd").max().alias("last")).filter(pl.col("n_ep") >= 2)
P(f"chronic code x patient seen in >=2 episodes: {rp.height}; each carries a different diagnosis_date per episode: {rp.filter(pl.col('n_dates') == pl.col('n_ep')).height}")
P(str(rp.sort("HASTA_ID").head(12)))

# EK-1A exemption flag vs curated catalog (3-char entries include sub-codes; 4-char entries only that code)
ek = pl.read_parquet(CURATED / "ek1a_chronic_exemptions.parquet")
codes = cd.select("icd10_code").unique()
def in_ek1a(code: str) -> bool:
    c3 = code[:3]
    for s, e in ek.select("icd10_start", "icd10_end").iter_rows():
        if "." in s:
            if code == s:
                return True
        elif s[0] == c3[0] and s <= c3 <= e[:3]:
            return True
    return False
m = codes.with_columns(pl.col("icd10_code").map_elements(in_ek1a, return_dtype=pl.Boolean).alias("ek1a_calc"))
dd2 = cd.join(m, on="icd10_code")
mis = dd2.filter(pl.col("ek1a_calc") != pl.col("exemption_eligible"))
P(f"exemption_eligible vs EK-1A catalog recomputation: mismatches {mis.height}/{dd2.height}; eligible share {dd2['exemption_eligible'].sum()}/{dd2.height}")
P("codes and EK-1A status: " + ", ".join(f"{c}={'Y' if v else 'n'}" for c, v in m.sort("icd10_code").iter_rows()))
sec = dd2.filter(pl.col("exemption_eligible") & ~pl.col("is_primary"))
P(f"exemption_eligible=True on SECONDARY diagnoses: {sec.height}/{dd2.filter(pl.col('exemption_eligible')).height} eligible rows")
ip = dd2.join(ep.select("claim_id", "claim_type"), on="claim_id").filter(pl.col("exemption_eligible") & (pl.col("claim_type") == "yatis"))
P(f"exemption_eligible=True on inpatient (yatis) claims, where the EK-1A outpatient-exam copay does not arise: {ip.height}")
# health report field anywhere?
from common import CLAIMS, CLEAN
import glob
cols_with_report = []
for f in sorted(glob.glob(str(CLAIMS / "*.parquet")) + glob.glob(str(CLEAN / "*.parquet"))):
    for c in pl.read_parquet_schema(f):
        if any(k in c.lower() for k in ("rapor", "report")):
            cols_with_report.append(f"{f.split('/')[-1]}:{c}")
P(f"columns mentioning rapor/report in the cohort: {cols_with_report}")
# header-vs-claim_diagnoses EK-1A consequence for copay demo patient 0036
z = cd.filter(pl.col("patient_id") == "SENTETIK-HASTA-0036").select("icd10_code", "is_primary", "exemption_eligible")
P(f"0036 (copay_exemption_ek1a_demo; header primary {ep.filter(pl.col('HASTA_ID') == 'SENTETIK-HASTA-0036')['primary_icd10'].item()}): claim_diagnoses rows = {z.rows()}")
write("d_diag_sets.txt", "\n".join(lines))
