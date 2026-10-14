"""Audit the engine output produced by run_reports.py.  Usage: python -I analyze.py <out_dir>

Reads only <out_dir>/*.json (engine output), the 9 top-level synthetic claim parquets and the
curated EK-2C catalogue (reference data). Writes CSV/JSON results into <out_dir>/analysis/.
"""
from __future__ import annotations

import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

import polars as pl

OUT = Path(sys.argv[1]).resolve()
RES = OUT / "analysis"
RES.mkdir(exist_ok=True)
C = Path("/home/safa/Documents/Bilun/data/synthetic/sut/claims")
TIER_A = ["0002", "0003", "0006", "0009", "0010", "0013", "0029", "0038"]
TIER_B = ["0004", "0005", "0007", "0008", "0012", "0018", "0023", "0024", "0025", "0026", "0027",
          "0028", "0030", "0031", "0032", "0033"]

P = json.loads((OUT / "patient_billing_reports.json").read_text())
B = json.loads((OUT / "bill_billing_reports.json").read_text())
COH = json.loads((OUT / "cohort_recovery_summary.json").read_text())
CIDX = json.loads((OUT / "cohort_compliance_index.json").read_text())

hdr = pl.read_parquet(C / "claim_headers.parquet")
proc = pl.read_parquet(C / "procedure_claim_lines.parquet")
mat = pl.read_parquet(C / "material_claim_lines.parquet")
drug = pl.read_parquet(C / "drug_claim_lines.parquet")
dx = pl.read_parquet(C / "claim_diagnoses.parquet")


def tier(pid: str) -> str:
    n = pid[-4:]
    return "A" if n in TIER_A else "B" if n in TIER_B else "C"


def fold(s: str | None) -> str:
    s = (s or "").replace("İ", "i").replace("I", "ı").lower()
    s = s.translate(str.maketrans("ıöüşğç", "iousgc"))
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


# ---------------------------------------------------------------- billed totals (UI "Toplam faturalanan")
lines_billed = pl.concat([
    proc.select("claim_id", "patient_id", pl.col("billed_amount_try").cast(pl.Float64)),
    mat.select("claim_id", "patient_id", pl.col("billed_amount_try").cast(pl.Float64)),
    drug.select("claim_id", "patient_id", pl.col("billed_amount_try").cast(pl.Float64)),
])
claim_billed = lines_billed.group_by("claim_id").agg(pl.col("billed_amount_try").sum().alias("line_billed"))
claims = hdr.join(claim_billed, on="claim_id", how="left").with_columns(
    pl.col("line_billed").fill_null(0.0),
    pl.col("expected_total_billed_try").cast(pl.Float64))
pat_billed = claims.group_by("patient_id").agg(
    pl.col("line_billed").sum().alias("billed_total"),
    pl.col("expected_total_billed_try").sum().alias("header_billed_total"),
    pl.len().alias("n_claims"))
BILLED = {r["patient_id"]: r for r in pat_billed.to_dicts()}
CLAIM = {r["claim_id"]: r for r in claims.to_dicts()}


# ---------------------------------------------------------------- UI KPI replicas
def ui_billed_at_risk(rep: dict) -> tuple[float, int, int]:
    """frontend/src/lib/workspaceViews.ts complianceBilledAtRiskSummary."""
    total = known = count = 0
    for a in rep["recommended_actions"]:
        if a.get("finding_type") != "compliance" or a["surface"] == "drug_indication":
            continue
        count += 1
        if a.get("billed_try") is None:
            continue
        total += a["billed_try"]
        known += 1
    return round(total, 2), known, count


def ui_risk_findings(rep: dict) -> int:
    """frontend/src/lib/complianceFindings.ts buildUnifiedComplianceFindings row count."""
    acts = [a for a in rep["recommended_actions"] if a.get("finding_type") == "compliance"]
    groups, seen = 0, set()
    for a in acts:
        fid = a.get("finding_id")
        if fid:
            if fid not in seen:
                seen.add(fid)
                groups += 1
        else:
            groups += 1
    claim_id = rep.get("claim_id")
    scoped = [f for f in rep["claim_compliance"]["findings"]
              if f.get("patient_id") == rep["patient_id"]
              and (not claim_id or f.get("claim_id") in (claim_id, None))]
    extra = sum(1 for f in scoped if not (f.get("finding_id") and f["finding_id"] in seen))
    return groups + extra


BLOCKS = ["session_uplift", "drg_uplift", "blood_uplift", "yatak_puani", "icu_puani", "yenidogan_yatak",
          "refakatci", "anestezi_puani", "material_uplift", "care_setting_review",
          "procedure_addon_uplift", "drg_package_adequacy", "procedure_capture_gap"]


def block_sgk(rep: dict, b: str) -> float:
    """TL of a block that enters sgk_uplift_try (included_in_sgk_total rows)."""
    tot = 0.0
    for o in rep[b]["opportunities"]:
        if o.get("included_in_sgk_total") is False:
            continue
        v = o.get("recoverable_uplift_try")
        if v is None:
            v = o.get("expected_yatak_try") if b == "yatak_puani" else o.get("expected_try")
        tot += float(v or 0)
    return round(tot, 2)


rows = []
for pid, rep in sorted(P.items()):
    tot, known, count = ui_billed_at_risk(rep)
    ft = collections.Counter(a.get("finding_type") for a in rep["recommended_actions"])
    bt = BILLED.get(pid, {})
    row = dict(pid=pid, tier=tier(pid), n_claims=bt.get("n_claims"), billed_total=round(bt.get("billed_total", 0), 2),
               header_billed_total=round(bt.get("header_billed_total", 0), 2),
               action_count=rep["action_count"], n_compliance=ft["compliance"], n_opportunity=ft["opportunity"],
               n_informational=ft["informational"], ui_risk_findings=ui_risk_findings(rep),
               ui_billed_at_risk=tot, ui_billed_known=known, ui_billed_count=count,
               total_recoverable_try=rep["total_recoverable_try"], audit_exposure_try=rep["audit_exposure_try"],
               n_docs_tab=sum(1 for a in rep["recommended_actions"] if a["surface"] in ("claim_checklist", "medula_playbook")))
    for b in BLOCKS:
        row[f"tl_{b}"] = block_sgk(rep, b)
    row["copay_waived"] = rep["copay"].get("patient_copay_waived_total_try") or 0
    rows.append(row)
pt = pl.DataFrame(rows)
pt.write_csv(RES / "per_patient.csv")

brow = []
for key, rep in sorted(B.items()):
    pid, cid = key.split("::")
    tot, known, count = ui_billed_at_risk(rep)
    c = CLAIM[cid]
    brow.append(dict(pid=pid, claim_id=cid, claim_type=c["claim_type"], department=c["department"],
                     primary_icd10=c["primary_icd10"], billed=round(c["line_billed"], 2),
                     ui_billed_at_risk=tot, ui_billed_known=known, ui_billed_count=count,
                     ui_risk_findings=ui_risk_findings(rep), total_recoverable_try=rep["total_recoverable_try"],
                     audit_exposure_try=rep["audit_exposure_try"], action_count=rep["action_count"]))
bt = pl.DataFrame(brow)
bt.write_csv(RES / "per_bill.csv")

# ---------------------------------------------------------------- (a) double counting / multi-rule lines
mat_by_code = collections.defaultdict(list)
for r in mat.to_dicts():
    mat_by_code[(r["patient_id"], r["material_code"])].append(r)
multi = []
for pid, rep in P.items():
    g = collections.defaultdict(list)
    for a in rep["recommended_actions"]:
        if a.get("finding_type") == "compliance" and a["surface"] == "materials" and a.get("billed_try") is not None:
            g[a.get("material_code")].append(a)
    for code, acts in g.items():
        lines = mat_by_code.get((pid, code), [])
        line_billed = round(sum(float(x["billed_amount_try"]) for x in lines), 2)
        multi.append(dict(pid=pid, material_code=code, material_name=acts[0].get("material_name"),
                          n_rules=len(acts), kinds="|".join(a["kind"] for a in acts),
                          claim_ids="|".join(sorted({str(a.get("claim_id")) for a in acts})),
                          tl_counted=round(sum(a["billed_try"] for a in acts), 2), line_billed=line_billed,
                          n_lines=len(lines)))
mt = pl.DataFrame(multi)
mt.write_csv(RES / "material_line_hits.csv")

# recoverable-side double hits: anaesthesia rows per claim and per claim-date
an = []
for pid, rep in P.items():
    for o in rep["anestezi_puani"]["opportunities"]:
        an.append(dict(pid=pid, claim_id=o["claim_id"], procedure_code=o["procedure_code"],
                       group=o.get("anestezi_group"), anestezi_code=o.get("anestezi_code"),
                       tl=float(o.get("recoverable_uplift_try") or o.get("expected_try") or 0),
                       included=o.get("included_in_sgk_total")))
an = pl.DataFrame(an)
pname = proc.select("claim_id", "procedure_code", "procedure_name", "procedure_category", "procedure_date",
                    pl.col("billed_amount_try").cast(pl.Float64).alias("proc_billed"), "is_package_included", "package_code").unique(
    subset=["claim_id", "procedure_code"], keep="first")
an = an.join(pname, on=["claim_id", "procedure_code"], how="left").join(
    claims.select("claim_id", "claim_type", "department", "primary_icd10", "provider_type", "facility_tier"), on="claim_id", how="left")
anes_billed = proc.filter(pl.col("procedure_code").cast(pl.Utf8).str.contains(r"^55\d{4}$")).group_by("claim_id").agg(
    pl.col("procedure_code").alias("billed_anesthesia_codes"))
pkg_claims = proc.filter(pl.col("procedure_code").cast(pl.Utf8).str.starts_with("P")).group_by("claim_id").agg(
    pl.col("procedure_code").alias("package_codes"))
an = an.join(anes_billed, on="claim_id", how="left").join(pkg_claims, on="claim_id", how="left")
an.with_columns(pl.col("billed_anesthesia_codes").list.join("|"), pl.col("package_codes").list.join("|")).write_csv(RES / "anesthesia_rows.csv")

# bed-day / companion rows with claim context
bed = []
for pid, rep in P.items():
    for b in ("yatak_puani", "refakatci"):
        for o in rep[b]["opportunities"]:
            c = CLAIM[o["claim_id"]]
            bed.append(dict(pid=pid, block=b, claim_id=o["claim_id"], claim_type=c["claim_type"],
                            department=c["department"], admission=c["admission_date"], discharge=c["discharge_date"],
                            days=o.get("bed_days", o.get("days")), tl=float(o.get("expected_yatak_try") or o.get("expected_try") or 0),
                            included=o.get("included_in_sgk_total"), detail=o.get("detail")))
bd = pl.DataFrame(bed).join(pkg_claims.with_columns(pl.col("package_codes").list.join("|")), on="claim_id", how="left")
bd.write_csv(RES / "bed_companion_rows.csv")

# ---------------------------------------------------------------- (b) rule-to-line object mismatch (keyword method)
# Each clause that names a specific device/object class -> stems that must appear in the folded line name
# (material name + code-family hints). Generic clauses (documentation, tender, barcode...) are not judged.
OBJECT_STEMS = [
    (r"koroner stent", ["koroner"]),
    (r"kalp pili", ["kalp pili", "pacemaker", "icd", "pil "]),
    (r"pace elektrod", ["elektrod", "elektrot"]),
    (r"tekerlekli sandalye|wheelchair", ["sandalye", "wheelchair"]),
    (r"standing table", ["standing", "dik konumlandirma"]),
    (r"protez/ortez|ortez/protez|protez bakim|ortez", ["protez", "ortez", "soket", "liner", "splint", "mold", "harness", "batarya"]),
    (r"isitme cihaz|kulak kalib", ["isitme", "kulak"]),
    (r"koklear implant", ["koklear"]),
    (r"konusma islemcisi", ["konusma islemci", "ses islemci"]),
    (r"beyin sapi implant", ["beyin sapi"]),
    (r"gozluk|optik|kontakt lens|teleskopik", ["gozluk", "lens", "cam", "cerceve", "optik", "teleskop"]),
    (r"deri taklidi|deri yedegi", ["deri"]),
    (r"yara bakim", ["yara", "ortu", "pansuman"]),
    (r"kemik uyarici|kemik yapimini uyaran", ["kemik", "stimulator", "uyarici"]),
    (r"greft", ["greft", "graft", "membran", "doku"]),
    (r"mesh", ["mesh", "yama"]),
    (r"hidrofilik sonda|alt bez", ["sonda", "kateter", "bez"]),
    (r"kan sekeri olcum", ["glukometre", "kan sekeri", "olcum cihaz"]),
    (r"tv5680", ["tv5680"]),
    (r"mobilite cihaz", ["sandalye", "mobilite", "walker", "yurutec"]),
    (r"ismarlama|kisiye ozel", ["ismarlama", "kisiye ozel", "protez", "ortez"]),
    (r"doku bankasi", ["greft", "doku", "allogreft", "kemik"]),
]


def clause_stems(text: str) -> list[str] | None:
    f = fold(text)
    for pat, stems in OBJECT_STEMS:
        if re.search(pat, f):
            return stems
    return None


mm = []
for pid, rep in P.items():
    for a in rep["recommended_actions"]:
        if a["surface"] != "materials":
            continue
        name = a.get("material_name") or ""
        stems = clause_stems(a.get("detail") or "")
        if stems is None:
            verdict = "generic_clause"
        else:
            verdict = "match" if any(s in fold(name) for s in stems) else "MISMATCH"
        mm.append(dict(pid=pid, claim_id=a.get("claim_id"), kind=a["kind"], material_code=a.get("material_code"),
                       line_name=name, clause=a.get("detail"), sut=a.get("sut_section_id"), verdict=verdict,
                       billed_try=a.get("billed_try")))
mmd = pl.DataFrame(mm)
mmd.write_csv(RES / "rule_line_pairs_materials.csv")

# ---------------------------------------------------------------- (c) composition
comp = {k: COH[k] for k in ["grand_total_recoverable", "total_anestezi_puani", "total_yatak_puani", "total_refakatci",
                             "total_icu_puani", "total_yenidogan_yatak", "total_material_uplift", "total_strategy_uplift",
                             "total_drg_uplift", "total_session_uplift", "total_procedure_addon_uplift", "total_blood_uplift",
                             "total_copay_savings", "total_audit_exposure", "total_package_adequacy_review", "total_capture_gap"]}
risk_by_kind = collections.Counter()
for rep in P.values():
    for a in rep["recommended_actions"]:
        if a.get("finding_type") == "compliance" and a["surface"] != "drug_indication" and a.get("billed_try") is not None:
            risk_by_kind[a["kind"]] += a["billed_try"]
comp["ui_billed_at_risk_by_kind"] = {k: round(v, 2) for k, v in risk_by_kind.most_common()}
comp["cohort_index_billed_at_risk_try"] = CIDX.get("billed_at_risk_try")
(RES / "composition.json").write_text(json.dumps(comp, ensure_ascii=False, indent=1))

# ---------------------------------------------------------------- documents tab
docs = []
for pid, rep in P.items():
    for it in rep["claim_submission_checklist"]["items"]:
        c = CLAIM.get(it.get("claim_id"), {})
        docs.append(dict(pid=pid, claim_id=it.get("claim_id"), claim_type=c.get("claim_type"), source="checklist",
                         ref=it.get("fatura_inceleme_ref") or it.get("checklist_kind"), text=it.get("message_tr") or it.get("detail"),
                         docs="|".join(it.get("required_documents") or []), procedure_codes="|".join(it.get("procedure_codes") or [])))
    for e in rep["medula_rejection_playbook"]["entries"]:
        c = CLAIM.get(e.get("claim_id"), {})
        docs.append(dict(pid=pid, claim_id=e.get("claim_id"), claim_type=c.get("claim_type"), source="medula_playbook",
                         ref=e.get("playbook_id"), text=e.get("problem_summary_tr"), docs="",
                         procedure_codes=str(e.get("related_procedure_code") or "")))
dd = pl.DataFrame(docs)
dd.write_csv(RES / "documents_tab_items.csv")

# ---------------------------------------------------------------- print summary
pl.Config.set_tbl_rows(60)
pl.Config.set_tbl_cols(20)
pl.Config.set_fmt_str_lengths(90)
pl.Config.set_tbl_width_chars(250)
print("billed line-sum == header sum for all patients:",
      bool((pt["billed_total"] - pt["header_billed_total"]).abs().max() < 0.01))
print("patients:", pt.height, "| with >=1 action:", pt.filter(pl.col("action_count") > 0).height,
      "| with >=1 compliance/opportunity action:", pt.filter((pl.col("n_compliance") + pl.col("n_opportunity")) > 0).height,
      "| with recoverable>0:", pt.filter(pl.col("total_recoverable_try") > 0).height,
      "| dashboard n_patients:", COH["n_patients"])
print("actions total:", int(pt["action_count"].sum()), "| informational share:",
      round(pt["n_informational"].sum() / pt["action_count"].sum(), 3))
print("patients ui_billed_at_risk > billed:", pt.filter(pl.col("ui_billed_at_risk") > pl.col("billed_total")).select(
    "pid", "billed_total", "ui_billed_at_risk", "ui_billed_known", "ui_billed_count").to_dicts())
print("patients audit_exposure > billed:", pt.filter(pl.col("audit_exposure_try") > pl.col("billed_total")).height,
      "| recoverable > billed:", pt.filter(pl.col("total_recoverable_try") > pl.col("billed_total")).height)
print("bills ui_billed_at_risk > billed:", bt.filter(pl.col("ui_billed_at_risk") > pl.col("billed")).height, "of", bt.height,
      "| bills audit_exposure > billed:", bt.filter(pl.col("audit_exposure_try") > pl.col("billed")).height,
      "| bills recoverable > billed:", bt.filter(pl.col("total_recoverable_try") > pl.col("billed")).height)
print(bt.filter(pl.col("total_recoverable_try") > pl.col("billed")).select("claim_id", "claim_type", "billed", "total_recoverable_try").head(12))
print("UI count mismatch (Riskli bulgu vs 'none of N'):",
      pt.filter((pl.col("ui_billed_known") == 0) & (pl.col("ui_billed_count") > 0) & (pl.col("ui_risk_findings") != pl.col("ui_billed_count"))).height,
      "patients; examples:", pt.filter((pl.col("ui_billed_known") == 0) & (pl.col("ui_risk_findings") != pl.col("ui_billed_count"))).select(
          "pid", "ui_risk_findings", "ui_billed_count").head(5).to_dicts())
print("material lines hit by >1 rule:", mt.filter(pl.col("n_rules") > 1).height, "of", mt.height,
      "| TL counted on them:", round(mt.filter(pl.col("n_rules") > 1)["tl_counted"].sum(), 2),
      "| their line billed:", round(mt.filter(pl.col("n_rules") > 1)["line_billed"].sum(), 2))
print(mt.sort("tl_counted", descending=True).head(8).select("pid", "material_name", "n_rules", "kinds", "tl_counted", "line_billed"))
print("material compliance actions with claim_id None:", mmd.filter(pl.col("claim_id").is_null()).height, "of", mmd.height)
print("rule-line verdicts:", mmd.group_by("verdict").len().sort("verdict").to_dicts())
print(mmd.filter(pl.col("verdict") == "MISMATCH").select("pid", "kind", "line_name", "clause").to_pandas().to_string(max_colwidth=95)
      if mmd.filter(pl.col("verdict") == "MISMATCH").height else "no mismatches")
print("anaesthesia rows:", an.height, "TL:", round(an["tl"].sum(), 2), "| by claim_type:",
      an.group_by("claim_type").agg(pl.len(), pl.col("tl").sum().round(2)).sort("claim_type").to_dicts())
print("anaesthesia rows on claims that already bill a 55xxxx code:", an.filter(pl.col("billed_anesthesia_codes").is_not_null()).height,
      "| on claims with a P-package code:", an.filter(pl.col("package_codes").is_not_null()).height,
      "| procedure_category counts:", an.group_by("procedure_category").len().sort(["len", "procedure_category"], descending=[True, False]).to_dicts())
per_claim = an.group_by("claim_id").agg(pl.len().alias("n"), pl.col("tl").sum().round(2), pl.col("procedure_date").n_unique().alias("dates"))
print("claims with >1 anaesthesia row:", per_claim.filter(pl.col("n") > 1).height, "| rows on them:",
      per_claim.filter(pl.col("n") > 1)["n"].sum(), "| max rows on one claim:", per_claim["n"].max())
print("anaesthesia rows whose procedure_name looks non-surgical (muayene/takip/konsultasyon/test):",
      an.filter(pl.col("procedure_name").map_elements(fold, return_dtype=pl.Utf8).str.contains("muayene|takip|konsult|vizit|tetkik|test|grafi|ultrason|enjeksiyon|kan ")).select(
          "claim_id", "procedure_code", "procedure_name", "claim_type", "tl").to_dicts()[:10])
print("bed/companion rows by block x claim_type:", bd.group_by("block", "claim_type").agg(pl.len(), pl.col("tl").sum().round(2)).sort(["block", "claim_type"]).to_dicts())
print("docs tab: per-patient counts min/median/max:", dd.group_by("pid").len()["len"].min(), dd.group_by("pid").len()["len"].median(),
      dd.group_by("pid").len()["len"].max(), "| patients with items:", dd["pid"].n_unique())
print(dd.group_by("source", "ref", "text").agg(pl.len().alias("n"), pl.col("pid").n_unique().alias("patients"),
                                                pl.col("claim_type").unique().sort().alias("claim_types")).sort(["n", "source", "ref"], descending=[True, False, False], nulls_last=True).to_pandas().to_string(max_colwidth=110))
print("composition:", json.dumps(comp, ensure_ascii=False))
