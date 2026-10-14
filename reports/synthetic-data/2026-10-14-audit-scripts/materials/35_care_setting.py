"""Care setting of implant/device lines: claim_type (yatis / gunubirlik / poliklinik / acil) and bed-days.

JUDGMENT: revision arthroplasty, airway/oesophageal stents, sternal plates, ICDs are inpatient procedures;
a polyclinic (poliklinik) claim cannot carry an arthroplasty implant.
Needs link.parquet (32).
"""
import os

import polars as pl

from common import HERE, load

pl.Config.set_tbl_rows(60)
pl.Config.set_fmt_str_lengths(50)
pl.Config.set_tbl_width_chars(220)

m, p, h, a, cp = load()
lnk = pl.read_parquet(os.path.join(HERE, "link.parquet")).select("material_line_id", "family")
x = (m.select("material_line_id", "claim_id", "material_code", "material_name", "billed_amount_try")
     .join(lnk, on="material_line_id").join(h.select("claim_id", "claim_type", "admission_date", "discharge_date"), on="claim_id"))
print("[setting] material lines by claim_type:", x.group_by("claim_type").len().sort("claim_type").rows())
IMPLANT = ["ARTHROPLASTY_IMPLANT", "ORTHO_IMPLANT_GENERIC", "AIRWAY_BRONCHOSCOPY", "ESOPHAGEAL_STENT", "THORACIC_SURGERY", "CARDIAC_ICD"]
imp = x.filter(pl.col("family").is_in(IMPLANT) & pl.col("material_name").str.contains(
    r"(?i)STENT|ENDOBRONŞİYAL VALF|PLAK|DEFORMİTE BARI|BANT|^KALÇA$|^DİZ$|artroplasti|implant|ICD"))
print("[setting] surgical implants (arthroplasty parts, stents, valves, plates/bars/bands, ICD):", imp.height,
      "| on non-inpatient claims:", imp.filter(pl.col("claim_type") != "yatis").height)
print(imp.filter(pl.col("claim_type") != "yatis").select(
    pl.col("material_line_id").str.replace("MLZ-F-SENTETIK-HASTA-", ""), "material_code",
    pl.col("material_name").str.slice(0, 45), "claim_type").sort("material_line_id"))
# length of stay of inpatient claims carrying implants
los = (imp.filter(pl.col("claim_type") == "yatis").select("claim_id", "admission_date", "discharge_date").unique()
       .with_columns((pl.col("discharge_date").str.to_date() - pl.col("admission_date").str.to_date()).dt.total_days().alias("los_days")))
print("[setting] inpatient implant claims: LOS days distribution:", los.group_by("los_days").len().sort("los_days").rows())
