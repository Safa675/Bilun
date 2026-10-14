"""What the Tier-A showcase patients (demo_manifest.json) actually carry in drugs and labs.
Reads outputs of d_drug_indication.py and g_lab_vs_dx.py (run those first)."""
import json

import polars as pl

from common import REPO, anadata, drugs, hdr, headers, labs, recete

man = json.load(open(REPO / "data/synthetic/demo_manifest.json"))
tier_a = [f"SENTETIK-HASTA-{i}" for i in man["tier_a_patient_indices"]]
landing = f"SENTETIK-HASTA-{man['default_landing_index']}"
d = drugs()
h = headers()
ind = pl.read_csv("out/d_indication_check.csv")
cat = pl.read_csv("out/g_lab_test_categories.csv")

hdr("Tier A patients: drug lines / indication failures")
da = d.filter(pl.col("patient_id").is_in(tier_a))
ia = ind.filter(pl.col("patient_id").is_in(tier_a))
print("Tier A drug lines:", da.height, "| narrow-indication lines:", ia.height,
      "| no indication on claim:", ia.filter(~pl.col("ind_on_claim")).height,
      "| none in patient history:", ia.filter(~pl.col("ind_in_patient_history")).height)
print(ia.filter(~pl.col("ind_in_patient_history")).select("drug_claim_line_id", "department", "inn", "claim_icds"))

hdr(f"default landing patient {landing}")
a = anadata().filter(pl.col("HASTA_ID") == landing).select("SQ_EPISODE", "TANI_YASI", "CINSIYET", "TANIKODU")
print(a)
print(h.filter(pl.col("patient_id") == landing).select("claim_id", "claim_type", "department", "primary_icd10"))
print(d.filter(pl.col("patient_id") == landing).select("claim_id", "drug_name", "quantity", "unit_price_try"))
print(recete().filter(pl.col("HASTA_ID") == landing).select("ilac_adi", "verilis_yolu", "doz_mg", "siklik", "gun").head(4))
lc = cat.join(labs().select("basvuru_id", "HASTA_ID").unique(), on="basvuru_id").filter(pl.col("HASTA_ID") == landing)
print(lc.select("basvuru_id", "ek2b_name", "category"))
print(labs().filter((pl.col("HASTA_ID") == landing) & (pl.col("SUB_CODE") == "L108550"))
      .select("SUB_CODE", "sonuc_sayisal", "sonuc_nitel", "birim", "ref_alt", "ref_ust", "organ_sistemi"))

hdr("kohort label vs diagnoses (cohort label carried on recete/lab rows)")
k = anadata().group_by("HASTA_ID").agg(pl.col("kohort").first(), pl.col("TUM_EPS_TANILAR").str.join(",").alias("dx"))
k = k.with_columns(pl.col("dx").str.contains(r"(^|,)C\d").alias("has_C"))
print(k.group_by("kohort").agg(pl.len().alias("patients"), pl.col("has_C").sum().alias("with_C_code")).sort("kohort"))
