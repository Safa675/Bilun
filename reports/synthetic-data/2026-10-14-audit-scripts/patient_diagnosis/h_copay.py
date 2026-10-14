"""(h) patient_copay_profiles vs age/sex and claim context."""
from common import claims, episodes, write
import polars as pl

cp = claims("patient_copay_profiles")
ep = episodes()
lines = []
P = lines.append
pat = ep.sort("edate").group_by("HASTA_ID").agg(pl.col("CINSIYET").first(), pl.col("TANI_YASI").min().alias("age_min"), pl.col("TANI_YASI").max().alias("age_max"), pl.col("tier").first(), pl.col("claim_type").alias("types"), pl.col("scenario_tag").alias("tags"))
j = cp.join(pat, left_on="patient_id", right_on="HASTA_ID")
for c in ["sgk_benefit_class", "veteran_martyr_status", "national_service_status", "elderly_allowance_2022"]:
    P(f"{c}: {dict(cp.group_by(c).len().sort(c).iter_rows())}")
P(f"birth_year range {cp['birth_year'].min()}..{cp['birth_year'].max()}; null birth_year: {cp['birth_year'].null_count()}")
P(f"patients aged >=65 at latest claim: {j.filter(pl.col('age_max') >= 65).height}; of those with elderly_allowance_2022=True: {j.filter((pl.col('age_max') >= 65) & pl.col('elderly_allowance_2022')).height}; allowance=True under 65: {j.filter((pl.col('age_max') < 65) & pl.col('elderly_allowance_2022')).height}")
P(f"non-default statuses: {j.filter((pl.col('sgk_benefit_class') != 'standard') | (pl.col('veteran_martyr_status') != 'none') | (pl.col('national_service_status') != 'none') | pl.col('elderly_allowance_2022')).select('patient_id','tier','CINSIYET','age_min','age_max','sgk_benefit_class','veteran_martyr_status','national_service_status','elderly_allowance_2022','tags').rows()}")
write("h_copay.txt", "\n".join(lines))
