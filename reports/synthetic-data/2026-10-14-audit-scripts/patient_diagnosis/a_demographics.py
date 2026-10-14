"""(a) Age and sex: cross-table consistency and cohort mix."""
from common import episodes, write
import polars as pl

ep = episodes()
lines = []
P = lines.append

P(f"episodes={ep.height} anadata_rows={ep['SQ_EPISODE'].drop_nulls().len()} claim_rows={ep['claim_id'].drop_nulls().len()}")
P(f"unmatched anadata->claim: {ep.filter(pl.col('claim_id').is_null()).height}; unmatched claim->anadata: {ep.filter(pl.col('SQ_EPISODE').is_null()).height}")

# 1. sex consistency within patient
sx = ep.group_by("HASTA_ID").agg(pl.col("CINSIYET").n_unique().alias("n_sex"))
P(f"patients with >1 sex value across episodes: {sx.filter(pl.col('n_sex') > 1).height}/{sx.height}")

# 2. TANI_YASI vs episode year - birth_year
ep = ep.with_columns((pl.col("EPISODE_TARIH").dt.year() - pl.col("birth_year")).alias("age_calc"))
mism = ep.filter(pl.col("age_calc") != pl.col("TANI_YASI"))
P(f"episodes where TANI_YASI != year(EPISODE_TARIH)-birth_year: {mism.height}/{ep.height}")
# 3. anadata date vs claim start
dd = ep.filter(pl.col("edate") != pl.col("cstart"))
P(f"episodes where anadata EPISODE_TARIH != claim_start_date: {dd.height}/{ep.height}")

# 4. distributions
pat = (
    ep.sort("edate")
    .group_by("HASTA_ID")
    .agg(
        pl.col("CINSIYET").first().alias("sex"),
        pl.col("TANI_YASI").first().alias("age_first_visit"),  # what the app shows (_first_by_patient after date sort)
        pl.col("TANI_YASI").max().alias("age_last"),
        pl.col("birth_year").first(),
        pl.col("tier").first(),
        pl.len().alias("n_ep"),
    )
)
P(f"birth_year range: {pat['birth_year'].min()}..{pat['birth_year'].max()}")
P(f"age at episode range: {ep['TANI_YASI'].min()}..{ep['TANI_YASI'].max()}")
P("sex (patients): " + str(dict(pat.group_by("sex").len().sort("sex").iter_rows())))
P("sex (episodes): " + str(dict(ep.group_by("CINSIYET").len().sort("CINSIYET").iter_rows())))
bucket = (
    pl.when(pl.col("a") < 18).then(pl.lit("a<18"))
    .when(pl.col("a") < 40).then(pl.lit("b18-39"))
    .when(pl.col("a") < 65).then(pl.lit("c40-64"))
    .when(pl.col("a") < 75).then(pl.lit("d65-74"))
    .otherwise(pl.lit("e75+"))
)
pb = pat.with_columns(pl.col("age_last").alias("a")).with_columns(bucket.alias("bucket")).group_by("bucket").len().sort("bucket")
P("patients by age at latest episode: " + str(dict(pb.iter_rows())))
eb = (
    ep.with_columns(pl.col("TANI_YASI").alias("a")).with_columns(bucket.alias("bucket"))
    .group_by("bucket", "claim_type").len().pivot(on="claim_type", index="bucket", values="len").sort("bucket").fill_null(0)
)
P("episodes by age bucket x claim_type:\n" + str(eb))
ip = ep.filter(pl.col("claim_type") == "yatis")
P(f"inpatient (yatis) episodes: {ip.height}; age>=65: {ip.filter(pl.col('TANI_YASI') >= 65).height}; age<40: {ip.filter(pl.col('TANI_YASI') < 40).height}; median age {ip['TANI_YASI'].median()}")
P(f"median age all episodes {ep['TANI_YASI'].median()}; patients >=75: {pat.filter(pl.col('age_last') >= 75).height}; <13: {pat.filter(pl.col('age_last') < 13).height}")
P("minors (<18 at any episode):\n" + str(ep.filter(pl.col("TANI_YASI") < 18).select("HASTA_ID", "tier", "CINSIYET", "TANI_YASI", "claim_type", "department", "primary_icd10", "TUM_EPS_TANILAR")))
P("Tier A patients:\n" + str(pat.filter(pl.col("tier") == "A").sort("HASTA_ID")))
write("a_demographics.txt", "\n".join(lines))
