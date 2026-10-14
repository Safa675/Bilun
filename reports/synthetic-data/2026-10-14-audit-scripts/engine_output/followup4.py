"""Remaining counts: mismatch families, anaesthesia on 'islem' lines, UI count gaps, docs-tab fit. Usage: python -I followup4.py <out_dir>"""
import json, sys, re, collections
from pathlib import Path
import polars as pl
OUT=Path(sys.argv[1]); RES=OUT/"analysis"
C=Path("/home/safa/Documents/Bilun/data/synthetic/sut/claims")
P=json.loads((OUT/"patient_billing_reports.json").read_text())
proc=pl.read_parquet(C/"procedure_claim_lines.parquet"); hdr=pl.read_parquet(C/"claim_headers.parquet")
pt=pl.read_csv(RES/"per_patient.csv"); bt=pl.read_csv(RES/"per_bill.csv")
mm=pl.read_csv(RES/"rule_line_pairs_materials.csv", infer_schema_length=0)
x=mm.filter(pl.col("verdict")=="MISMATCH").with_columns(pl.col("clause").str.slice(0,40).alias("clause40"))
print("mismatch by kind:", x.group_by("kind").len().sort("kind").to_dicts())
print("coronary-stent clause on non-coronary stents:", x.filter(pl.col("clause").str.starts_with("Koroner stent")).height,
      "| patients:", x["pid"].n_unique(), "| billed_try on mismatched rows:", round(x["billed_try"].cast(pl.Float64).sum(),2))
print("mismatches per tier:", x.with_columns(pl.col("pid").str.slice(-4).alias("n")).with_columns(
    pl.when(pl.col("n").is_in(["0002","0003","0006","0009","0010","0013","0029","0038"])).then(pl.lit("A")).otherwise(pl.lit("B/C")).alias("tier")).group_by("tier").len().sort("tier").to_dicts())
an=pl.read_csv(RES/"anesthesia_rows.csv", infer_schema_length=0).with_columns(pl.col("tl").cast(pl.Float64))
isl=an.filter(pl.col("procedure_category")=="islem").with_columns(pl.col("procedure_code").str.contains(r"^P?6\d{5}$").alias("surgical_6x"))
print("anaesthesia on 'islem' lines: surgical 6xxxxx:", isl.filter(pl.col("surgical_6x")).height, round(isl.filter(pl.col("surgical_6x"))["tl"].sum(),2),
      "| non-6xxxxx:", isl.filter(~pl.col("surgical_6x")).height, round(isl.filter(~pl.col("surgical_6x"))["tl"].sum(),2),
      "| examples:", isl.filter(~pl.col("surgical_6x")).select("procedure_code","procedure_name").head(5).to_dicts())
surg_tl=isl.filter(pl.col("surgical_6x"))["tl"].sum(); print(f"anaesthesia TL on non-surgical lines overall: {an['tl'].sum()-surg_tl:.2f} of {an['tl'].sum():.2f} ({(an['tl'].sum()-surg_tl)/an['tl'].sum()*100:.1f}%)")
print("patients with recoverable > billed:", pt.filter(pl.col("total_recoverable_try")>pl.col("billed_total")).select("pid","billed_total","total_recoverable_try").to_dicts())
print("patients where 'Riskli bulgu' count != count in the billed-at-risk note:", pt.filter((pl.col("ui_risk_findings")!=pl.col("ui_billed_count")) & (pl.col("ui_billed_known")<pl.col("ui_billed_count"))).height,
      "| of which billed note says 'none':", pt.filter((pl.col("ui_risk_findings")!=pl.col("ui_billed_count")) & (pl.col("ui_billed_known")==0) & (pl.col("ui_billed_count")>0)).select("pid","ui_risk_findings","ui_billed_count").to_dicts())
print("per-patient Documents-tab action counts: min/median/max", pt["n_docs_tab"].min(), pt["n_docs_tab"].median(), pt["n_docs_tab"].max(), "| zero:", pt.filter(pl.col("n_docs_tab")==0)["pid"].to_list(), "| total:", pt["n_docs_tab"].sum())
dd=pl.read_csv(RES/"documents_tab_items.csv", infer_schema_length=0)
H={r["claim_id"]:r for r in hdr.to_dicts()}
names=proc.group_by("claim_id").agg(pl.col("procedure_name").str.join(" | ").alias("names"))
N={r["claim_id"]:r["names"].lower() for r in names.to_dicts()}
ortho_kw=r"artro|kırık|kirik|eklem|amputasyon|osteotomi|tendon|bağ |bag |vertebra|protez|fiksasyon|redüksiyon|menisk|sinovektomi|artrodez|osteomyelit"
o6=dd.filter(pl.col("ref")=="ORTOPEDİ-6").with_columns(pl.col("claim_id").map_elements(lambda c: bool(re.search(ortho_kw, N.get(c,""))), return_dtype=pl.Boolean).alias("ortho_surgery_on_bill"))
print("ORTOPEDİ-6 (pre/post-op X-rays) items:", o6.height, "| bills with an orthopaedic-surgery line:", o6.filter(pl.col("ortho_surgery_on_bill")).height,
      "| without:", o6.filter(~pl.col("ortho_surgery_on_bill")).select("claim_id","claim_type").to_dicts()[:6])
k17=dd.filter(pl.col("ref")=="ORTAK-17").group_by("claim_type").len().sort("claim_type").to_dicts(); print("ORTAK-17 by claim_type:", k17)
for r in P["SENTETIK-HASTA-0033"]["claim_submission_checklist"]["items"]:
    if not r.get("fatura_inceleme_ref"): print("0033 non-FI checklist item:", {k:r.get(k) for k in ["checklist_id","checklist_kind","claim_id","material_code","procedure_code","detail","message_tr","trigger"] if k in r})
generic=dd.filter(pl.col("ref").is_in(["ORTAK-5","ORTAK-17","ORTAK-21","ORTAK-27","ORTAK-29"])).height
print(f"generic ORTAK boilerplate rows: {generic} of {dd.filter(pl.col('source')=='checklist').height} checklist rows; patients with >=1 ORTAK row:", dd.filter(pl.col("ref").str.starts_with("ORTAK"))["pid"].n_unique())
an2=an.with_columns(pl.col("procedure_code").str.contains(r"^P?6\d{5}$").alias("surgical_6x"))
s=an2.filter(pl.col("surgical_6x")); ns=an2.filter(~pl.col("surgical_6x"))
print(f"anaesthesia rows by code (all categories): 6xxxxx surgical rows={s.height} TL={s['tl'].sum():.2f} | other rows={ns.height} TL={ns['tl'].sum():.2f} ({ns['tl'].sum()/an2['tl'].sum()*100:.1f}% of {an2['tl'].sum():.2f})")
print("non-surgical anaesthesia rows by category:", ns.group_by("procedure_category").agg(pl.len(), pl.col("tl").sum().round(2)).sort("procedure_category").to_dicts())
