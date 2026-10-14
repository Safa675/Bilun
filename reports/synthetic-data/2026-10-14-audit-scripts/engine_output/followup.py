"""Follow-up measurements on anaesthesia, bed-day and tier-A rows. Usage: python -I followup.py <out_dir>"""
import json, sys
from pathlib import Path
import polars as pl
OUT=Path(sys.argv[1]); RES=OUT/"analysis"
C=Path("/home/safa/Documents/Bilun/data/synthetic/sut/claims")
proc=pl.read_parquet(C/"procedure_claim_lines.parquet"); hdr=pl.read_parquet(C/"claim_headers.parquet")
an=pl.read_csv(RES/"anesthesia_rows.csv", infer_schema_length=0).with_columns(pl.col("tl").cast(pl.Float64))
pl.Config.set_tbl_rows(40); pl.Config.set_fmt_str_lengths(70); pl.Config.set_tbl_width_chars(250)
print("anaesthesia TL by procedure_category of the line it is attached to:")
print(an.group_by("procedure_category").agg(pl.len().alias("rows"), pl.col("tl").sum().round(2).alias("tl")).with_columns((pl.col("tl")/pl.col("tl").sum()*100).round(1).alias("pct")).sort(["tl","procedure_category"], descending=[True,False]))
print(an.filter(pl.col("procedure_category").is_in(["laboratuvar","muayene","yatak"])).select("claim_id","procedure_code","procedure_name","procedure_category","group","tl").head(8))
names = proc.filter(pl.col("procedure_name").str.to_lowercase().str.contains("anestez")).select("claim_id","procedure_code","procedure_name","billed_amount_try")
print("claim lines whose name mentions anestezi:", names.height); print(names.head(6))
anes_claims=set(names["claim_id"].to_list())
print("anaesthesia uplift rows on claims that already contain an anaesthesia-named line:", an.filter(pl.col("claim_id").is_in(list(anes_claims))).height)
# bed lines vs yatak opportunity
bd=pl.read_csv(RES/"bed_companion_rows.csv", infer_schema_length=0).with_columns(pl.col("tl").cast(pl.Float64))
bedlines=proc.filter(pl.col("procedure_category")=="yatak").group_by("claim_id").agg(pl.col("procedure_code").unique().alias("bed_codes"), pl.col("billed_amount_try").cast(pl.Float64).sum().alias("bed_billed"))
y=bd.filter(pl.col("block")=="yatak_puani").join(bedlines,on="claim_id",how="left")
print("yatak rows:",y.height,"| on claims that already bill a 'yatak' category line:", y.filter(pl.col("bed_billed").is_not_null()).height,
      "| TL on those:", round(y.filter(pl.col("bed_billed").is_not_null())["tl"].sum(),2), "| on claims with P-package code:", y.filter(pl.col("package_codes").is_not_null()).height,
      "| TL on package claims:", round(y.filter(pl.col("package_codes").is_not_null())["tl"].sum(),2))
print(y.filter(pl.col("bed_billed").is_not_null()).select("claim_id","days","tl","bed_codes","bed_billed","package_codes").head(6))
r=bd.filter(pl.col("block")=="refakatci")
print("refakatci rows on package claims:", r.filter(pl.col("package_codes").is_not_null()).height, "TL", round(r.filter(pl.col("package_codes").is_not_null())["tl"].sum(),2))
print("refakatci companion evidence: rows with suppression note 'Verify companion actually stayed':", r.filter(pl.col("detail").is_not_null()).height)
