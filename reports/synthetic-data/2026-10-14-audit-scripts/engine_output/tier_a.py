"""Tier-A headline view (what the patient page shows first). Usage: python -I tier_a.py <out_dir>"""
import json, sys
from pathlib import Path
import polars as pl
OUT=Path(sys.argv[1]); RES=OUT/"analysis"
C=Path("/home/safa/Documents/Bilun/data/synthetic/sut/claims")
P=json.loads((OUT/"patient_billing_reports.json").read_text())
proc=pl.read_parquet(C/"procedure_claim_lines.parquet"); hdr=pl.read_parquet(C/"claim_headers.parquet")
pt=pl.read_csv(RES/"per_patient.csv")
def sortval(a): return max([v for v in (a.get("sgk_uplift_try"),a.get("compliance_savings_try"),a.get("billed_try")) if v is not None] or [0])
for n in ["0002","0003","0006","0009","0010","0013","0029","0038"]:
    pid=f"SENTETIK-HASTA-{n}"; r=P[pid]; m=pt.filter(pl.col("pid")==pid).to_dicts()[0]
    print(f"\n### {pid} billed={m['billed_total']} recoverable={m['total_recoverable_try']} ui_at_risk={m['ui_billed_at_risk']} ({m['ui_billed_known']}/{m['ui_billed_count']}) risk_findings={m['ui_risk_findings']} audit_exposure={m['audit_exposure_try']} actions={m['action_count']} anes={m['tl_anestezi_puani']} yatak={m['tl_yatak_puani']} refakat={m['tl_refakatci']}")
    for h in hdr.filter(pl.col("patient_id")==pid).to_dicts():
        names=proc.filter(pl.col("claim_id")==h["claim_id"]).select("procedure_code","procedure_name","procedure_category").to_dicts()
        surg=[f"{x['procedure_code']}:{x['procedure_name'][:40]}" for x in names if x["procedure_category"] not in ("laboratuvar",)][:4]
        print(f"  claim {h['claim_id'][-3:]} {h['claim_type']} {h['department']} icd={h['primary_icd10']} billed={h['expected_total_billed_try']} | {surg}")
    acts=sorted(r["recommended_actions"], key=sortval, reverse=True)[:3]
    for a in acts:
        print("  TOP:", a["surface"], a["kind"], a.get("claim_id","")[-3:] if a.get("claim_id") else None, a.get("procedure_code") or a.get("material_code"), (a.get("procedure_name") or a.get("material_name") or "")[:45], "| TL", sortval(a), "|", (a.get("detail") or "")[:150])
