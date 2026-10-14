"""Cohort ratios vs anchor, copay composition, care-setting blind spots. Usage: python -I followup3.py <out_dir>"""
import json, sys, collections, re
from pathlib import Path
import polars as pl
OUT=Path(sys.argv[1]); RES=OUT/"analysis"
C=Path("/home/safa/Documents/Bilun/data/synthetic/sut/claims")
P=json.loads((OUT/"patient_billing_reports.json").read_text()); COH=json.loads((OUT/"cohort_recovery_summary.json").read_text())
hdr=pl.read_parquet(C/"claim_headers.parquet"); H={r["claim_id"]:r for r in hdr.to_dicts()}
proc=pl.read_parquet(C/"procedure_claim_lines.parquet")
pt=pl.read_csv(RES/"per_patient.csv")
billed=pt["billed_total"].sum()
print(f"cohort billed={billed:.2f} | recoverable={COH['grand_total_recoverable']} ({COH['grand_total_recoverable']/billed*100:.1f}%) | audit_exposure={COH['total_audit_exposure']} ({COH['total_audit_exposure']/billed*100:.1f}%) | UI billed-at-risk sum={pt['ui_billed_at_risk'].sum():.2f} ({pt['ui_billed_at_risk'].sum()/billed*100:.1f}%) | copay waived={COH['total_copay_savings']}")
g=COH["grand_total_recoverable"]
for k in ["total_anestezi_puani","total_yatak_puani","total_refakatci","total_icu_puani","total_strategy_uplift","total_material_uplift","total_drg_uplift","total_session_uplift","total_procedure_addon_uplift"]:
    print(f"  {k}: {COH[k]} = {COH[k]/g*100:.1f}% of recoverable")
print("savings_by_category keys shown in donut (v>0, not copay/lab/strategy):", {k:v for k,v in COH["savings_by_category"].items() if v>0 and k not in ("copay","lab","strategy","medula_playbook")})
# copay: rate corrections on procedure lines vs drug lines
proc_codes=set(proc["procedure_code"].cast(pl.Utf8).to_list())
agg=collections.defaultdict(float); ex=[]
for pid,r in P.items():
    for rc in r["copay"]["rate_corrections"]:
        kind="procedure" if str(rc.get("code")) in proc_codes else "drug/other"
        agg[(kind, rc.get("exemption_ground"))]+=float(rc.get("copay_component_try") or 0)
        if kind=="procedure" and float(rc.get("copay_component_try") or 0)>3000: ex.append((pid[-4:], rc["code"], rc["name"], rc["billed_try"], rc["copay_component_try"], rc["detail"], H.get(rc.get("claim_id"),{}).get("claim_type")))
for k,v in sorted(agg.items(), key=lambda x:-x[1]): print("  copay component", k, round(v,2))
print("  large procedure 'copay' waivers:", ex[:6])
print("copay actions with empty detail:", sum(1 for r in P.values() for a in r["recommended_actions"] if a["surface"]=="copay" and not a.get("detail")))
# procedure_must_package on non-inpatient claims
cnt=collections.Counter(); exs=[]
for pid,r in P.items():
    for a in r["recommended_actions"]:
        if a.get("message_code")=="procedure_must_package":
            ct=H[a["claim_id"]]["claim_type"]; cnt[ct]+=1
            if ct in ("poliklinik","koruyucu","acil") and len(exs)<5: exs.append((pid[-4:], ct, a["procedure_code"], a["procedure_name"]))
print("procedure_must_package by claim_type:", dict(cnt), exs)
# surgical EK-2C-type lines (P-codes or 6xxxxx) on poliklinik/koruyucu/acil claims; does any engine row flag care setting?
surg=proc.filter(pl.col("procedure_code").cast(pl.Utf8).str.contains(r"^P?6\d{5}$")).join(hdr.select("claim_id","claim_type"),on="claim_id")
print("6xxxxx/P6xxxxx surgical lines by claim_type:", surg.group_by("claim_type").len().sort(["len","claim_type"],descending=[True,False]).to_dicts())
print("care_setting_review rows:", sum(len(r["care_setting_review"]["opportunities"]) for r in P.values()), "(claim types:", [o["claim_type"] for r in P.values() for o in r["care_setting_review"]["opportunities"]], ")")
print("ICU rows:", sum(len(r["icu_puani"]["opportunities"]) for r in P.values()), "| claims with ICU (5101xx yogun) lines:", proc.filter(pl.col("procedure_name").str.to_lowercase().str.contains("yoğun bakım")).height)
dup=[a["detail"] for r in P.values() for a in r["recommended_actions"] if a["surface"]=="drug_indication" and re.search(r"(\b[A-Z]\d\d(?:\.\d)?\b), \1", a["detail"] or "")]
print("drug-indication texts with repeated ICD codes:", len(dup), "of", sum(1 for r in P.values() for a in r["recommended_actions"] if a["surface"]=="drug_indication"))
