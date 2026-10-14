"""Cross-layer observations that bear on the patient story (Tier A showcase claims; out-of-layer quick checks)."""
from common import claims, clean, episodes, write
import polars as pl

lines = []
P = lines.append
ep = episodes()
pr = claims("procedure_claim_lines")
ma = claims("material_claim_lines")
dr = claims("drug_claim_lines")
A = ep.filter(pl.col("tier") == "A").sort("HASTA_ID", "edate")
for r in A.iter_rows(named=True):
    procs = pr.filter(pl.col("claim_id") == r["claim_id"]).filter(pl.col("procedure_category").is_in(["islem", "paket"])).select("procedure_code", "procedure_name").rows()
    mats = ma.filter(pl.col("claim_id") == r["claim_id"])["material_name"].to_list()
    P(f"{r['claim_id']} [{r['scenario_tag']}] {r['CINSIYET']}{r['TANI_YASI']} {r['claim_type']} {r['department']} {r['primary_icd10']} | procedures: {procs} | materials: {mats}")
# 'yatak' category lines that are not bed-days
y = pr.filter(pl.col("procedure_category") == "yatak").group_by("procedure_code", "procedure_name").agg(pl.len(), pl.col("quantity").min().alias("qmin"), pl.col("quantity").max().alias("qmax"))
P(f"\n'yatak' (bed-day) category lines: {y.rows()}")
# lab table quick sanity
lab = clean("lab_clean")
u = lab.group_by("SUB_CODE").agg(pl.col("birim").n_unique().alias("n_units"), pl.col("organ_sistemi").n_unique().alias("n_org"))
P(f"lab_clean: rows={lab.height}, SUB_CODEs={u.height}, SUB_CODEs reported in >1 unit: {u.filter(pl.col('n_units') > 1).height}, in >1 organ system: {u.filter(pl.col('n_org') > 1).height}")
calc = lab.with_columns(((pl.col("sonuc_sayisal") < pl.col("ref_alt")) | (pl.col("sonuc_sayisal") > pl.col("ref_ust"))).alias("abn_calc"))
P(f"lab anormal_mi agrees with value vs own reference range: {calc.filter(pl.col('abn_calc') == pl.col('anormal_mi')).height}/{calc.height}")
write("x_crosslayer.txt", "\n".join(lines))
