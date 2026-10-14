"""(f) Vitals: physiologic plausibility, BMI arithmetic, within-patient height/weight stability, vitals vs diagnosis."""
from common import episodes, write
import polars as pl

ep = episodes().sort("HASTA_ID", "edate")
lines = []
P = lines.append
for c in ["KB-S", "KB-D", "Nabiz", "SPO2", "Boy", "Kilo", "BMI"]:
    s = ep[c]
    P(f"{c}: min={s.min()} p25={s.quantile(0.25)} median={s.median()} p75={s.quantile(0.75)} max={s.max()} mean={round(s.mean(),1)} sd={round(s.std(),1)}")
P(f"KB-D >= KB-S (diastolic >= systolic): {ep.filter(pl.col('KB-D') >= pl.col('KB-S')).height}/94 -> {ep.filter(pl.col('KB-D') >= pl.col('KB-S')).select('SQ_EPISODE','tier','KB-S','KB-D').rows()}")
pp = pl.col("KB-S") - pl.col("KB-D")
P(f"pulse pressure < 20 mmHg: {ep.filter(pp < 20).height}/94; <= 10: {ep.filter(pp <= 10).height}/94; pulse pressure > 100: {ep.filter(pp > 100).height}")
P(f"SBP >= 160 or DBP >= 100 (stage-2 range) in a single visit: {ep.filter((pl.col('KB-S') >= 160) | (pl.col('KB-D') >= 100)).height}/94")
P(f"SpO2 values present: {sorted(ep['SPO2'].unique().to_list())}; SpO2 <= 92: {ep.filter(pl.col('SPO2') <= 92).height}/94; SpO2 <94: {ep.filter(pl.col('SPO2') < 94).height}/94; SpO2 < 90: {ep.filter(pl.col('SPO2') < 90).height}")
P(f"SpO2 <= 92 in poliklinik/koruyucu visits: {ep.filter((pl.col('SPO2') <= 92) & pl.col('claim_type').is_in(['poliklinik','koruyucu'])).height}/{ep.filter(pl.col('claim_type').is_in(['poliklinik','koruyucu'])).height}")
jrf = ep.filter(pl.col("primary_icd10") == "J96.0").select("SQ_EPISODE", "tier", "claim_type", "SPO2", "Nabiz")
P(f"J96.0 acute respiratory failure episodes and their SpO2: {jrf.rows()}")
P(f"Nabiz > 100: {ep.filter(pl.col('Nabiz') > 100).height}/94; Nabiz < 60: {ep.filter(pl.col('Nabiz') < 60).height}/94")
# BMI arithmetic
ep = ep.with_columns((pl.col("Kilo") / (pl.col("Boy") / 100) ** 2).round(1).alias("bmi_calc"))
P(f"BMI == Kilo/(Boy/100)^2 (±0.1): {ep.filter((pl.col('BMI') - pl.col('bmi_calc')).abs() <= 0.1).height}/94")
P(f"BMI < 16: {ep.filter(pl.col('BMI') < 16).height}/94; BMI 16-18.5: {ep.filter((pl.col('BMI') >= 16) & (pl.col('BMI') < 18.5)).height}; BMI >= 40: {ep.filter(pl.col('BMI') >= 40).height}/94")
# sex-specific height
P(f"women with height >= 180 cm: {ep.filter((pl.col('CINSIYET') == 'K') & (pl.col('Boy') >= 180)).height}/{ep.filter(pl.col('CINSIYET') == 'K').height} female episodes; men <= 155 cm: {ep.filter((pl.col('CINSIYET') == 'E') & (pl.col('Boy') <= 155)).height}/{ep.filter(pl.col('CINSIYET') == 'E').height}")
P(f"female height mean {round(ep.filter(pl.col('CINSIYET')=='K')['Boy'].mean(),1)} vs male {round(ep.filter(pl.col('CINSIYET')=='E')['Boy'].mean(),1)} (no sex difference => drawn from one distribution)")
# within-patient stability
multi = ep.filter(pl.len().over("HASTA_ID") >= 2)
hs = multi.group_by("HASTA_ID").agg((pl.col("Boy").max() - pl.col("Boy").min()).alias("h_range"), (pl.col("Kilo").max() - pl.col("Kilo").min()).alias("w_range"), pl.col("tier").first(), pl.col("TANI_YASI").min().alias("age"))
P(f"multi-episode patients: {hs.height}; height range > 3 cm: {hs.filter(pl.col('h_range') > 3).height}; > 10 cm: {hs.filter(pl.col('h_range') > 10).height}; max height range {hs['h_range'].max()} cm; median {hs['h_range'].median()} cm")
P(str(hs.sort("h_range", descending=True)))
w = multi.with_columns(
    (pl.col("Kilo") - pl.col("Kilo").shift(1).over("HASTA_ID")).alias("dw"),
    (pl.col("edate") - pl.col("edate").shift(1).over("HASTA_ID")).dt.total_days().alias("dd"),
    (pl.col("Boy") - pl.col("Boy").shift(1).over("HASTA_ID")).alias("dh"),
).drop_nulls("dw")
big = w.filter((pl.col("dw").abs() >= 20) & (pl.col("dd") <= 180))
P(f"consecutive same-patient visits: {w.height}; weight change >=20 kg within <=180 days: {big.height}; max |dw| {w['dw'].abs().max()} kg")
P("worst weight swings: " + str(w.with_columns((pl.col("dw").abs() / pl.col("dd")).alias("kg_per_day")).sort("kg_per_day", descending=True).select("SQ_EPISODE", "tier", "dd", "dw", "dh").head(6).rows()))
P(f"minors' anthropometrics: {ep.filter(pl.col('TANI_YASI') < 18).select('HASTA_ID','CINSIYET','TANI_YASI','Boy','Kilo','BMI').rows()}")
P(f"Tier A default landing 0003 vitals by visit: {ep.filter(pl.col('HASTA_ID') == 'SENTETIK-HASTA-0003').select('edate','KB-S','KB-D','SPO2','Boy','Kilo','BMI').rows()}")
write("f_vitals.txt", "\n".join(lines))
