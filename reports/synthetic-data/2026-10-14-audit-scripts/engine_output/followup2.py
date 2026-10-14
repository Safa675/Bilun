"""Bed-day double count, companion lines, Documents-tab fit, Tier-A headlines. Usage: python -I followup2.py <out_dir>"""
import json, sys, collections
from pathlib import Path
import polars as pl
OUT=Path(sys.argv[1]); RES=OUT/"analysis"
C=Path("/home/safa/Documents/Bilun/data/synthetic/sut/claims")
P=json.loads((OUT/"patient_billing_reports.json").read_text())
proc=pl.read_parquet(C/"procedure_claim_lines.parquet"); hdr=pl.read_parquet(C/"claim_headers.parquet")
mat=pl.read_parquet(C/"material_claim_lines.parquet"); drug=pl.read_parquet(C/"drug_claim_lines.parquet")
H={r["claim_id"]:r for r in hdr.to_dicts()}
# bed-day: full expected vs gap
exp=gap=0.0
for r in P.values():
    for o in r["yatak_puani"]["opportunities"]:
        if o.get("included_in_sgk_total", True):
            exp+=o["expected_yatak_try"]; gap+=o["recoverable_uplift_try"]
print(f"yatak: counted (expected_yatak_try)={exp:.2f}  real gap (recoverable_uplift_try)={gap:.2f}  already-billed TL counted as recoverable={exp-gap:.2f}")
ref=proc.filter(pl.col("procedure_name").str.to_lowercase().str.contains("refakat") | pl.col("procedure_code").is_in(["510121","510120"]))
print("claim lines that are companion/bed-type 51012x:", ref.select("claim_id","procedure_code","procedure_name","billed_amount_try").head(8).to_dicts())
# anaesthesia: per-claim session duplicates on the same claim
an=pl.read_csv(RES/"anesthesia_rows.csv", infer_schema_length=0).with_columns(pl.col("tl").cast(pl.Float64))
top=an.group_by("claim_id").agg(pl.len().alias("rows"),pl.col("tl").sum().round(2).alias("tl"),pl.col("procedure_name").alias("lines")).sort(["rows","tl"],descending=[True,True]).head(3)
for t in top.to_dicts(): print("ANES multi:", t["claim_id"], t["rows"], t["tl"], t["lines"])
# Documents tab fit
dd=pl.read_csv(RES/"documents_tab_items.csv", infer_schema_length=0)
by_claim_proc=proc.group_by("claim_id").agg(pl.col("procedure_code"),pl.col("procedure_name"),pl.col("procedure_category"))
PC={r["claim_id"]:r for r in by_claim_proc.to_dicts()}
mat_claims=set(mat["claim_id"].to_list()); drug_claims=set(drug["claim_id"].to_list())
def fit(row):
    ref=row["ref"] or ""; c=H.get(row["claim_id"],{}); pc=PC.get(row["claim_id"],{"procedure_code":[],"procedure_name":[],"procedure_category":[]})
    names=" | ".join(pc["procedure_name"]).lower()
    if ref=="ORTAK-21":
        return "biopsy/excision present" if any(k in names for k in ["biyopsi","eksizyon","rezeksiyon","ektomi","çıkar"]) else "NO biopsy/excision on bill"
    if ref=="ORTAK-17":
        return f"claim_type={c.get('claim_type')}"
    if ref=="ORTOPEDİ-6":
        return "codes="+ (row["procedure_codes"] or "")
    if ref.startswith("07") or ref.startswith("04") or ref.startswith("03") or ref.startswith("16") or ref.startswith("05") or ref.startswith("06") or ref.startswith("09") or ref.startswith("11") or ref.startswith("12"):
        return f"has_material={row['claim_id'] in mat_claims} has_drug={row['claim_id'] in drug_claims} related={row['procedure_codes']}"
    return ""
dd=dd.with_columns(pl.struct(dd.columns).map_elements(fit, return_dtype=pl.Utf8).alias("fit"))
print(dd.group_by("ref","fit").agg(pl.len().alias("n")).sort(["ref","n","fit"],descending=[False,True,False],nulls_last=True).to_pandas().to_string(max_colwidth=120))
ortho=dd.filter(pl.col("ref")=="ORTOPEDİ-6")
for r in ortho.head(15).to_dicts():
    pc=PC[r["claim_id"]]; codes=(r["procedure_codes"] or "").split("|")
    trig=[n for c,n in zip(pc["procedure_code"],pc["procedure_name"]) if c in codes or c.lstrip("P") in codes]
    print("ORTO-6", r["claim_id"], r["claim_type"], H[r["claim_id"]]["department"], "trigger lines:", trig[:3])
for r in dd.filter(pl.col("source")=="medula_playbook").to_dicts():
    pc=PC.get(r["claim_id"]); rel=r["procedure_codes"]
    rel_name=[n for c,n in zip(pc["procedure_code"],pc["procedure_name"]) if c==rel] if pc else []
    print("PLAYBOOK", r["pid"][-4:], r["claim_id"][-3:], r["claim_type"], r["ref"], "| related:", rel, rel_name[:1], "| has_material:", r["claim_id"] in mat_claims, "| has_drug:", r["claim_id"] in drug_claims)
print("checklist items per claim: ", dd.filter(pl.col("source")=="checklist").group_by("claim_id").len()["len"].describe().with_columns(pl.col("value").round(3)).to_dicts())
print("NaN-ref item:", dd.filter(pl.col("ref").is_null()).to_dicts())
