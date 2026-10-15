"""Scratch harness: build showcase claims in-process and run the engine (read-only).

Nothing here writes to the repo. Claims are built from the dataclasses in
src/bilun/domain/claims/models.py the way the unit tests do, priced from the
curated catalogs in force on each line date, then run through:
  * the specific detector(s) for the injected fault (direct call), and
  * the full single-patient report (compute_patient_billing_report) plus the
    validation core (analyze_claim), so any other rule that fires is visible.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
os.chdir(ROOT)

import polars as pl  # noqa: E402

from cat import EK2B, EK2C  # noqa: E402
from src.bilun.domain.billing.engine import analyze_claim  # noqa: E402
from src.bilun.domain.billing.patient_report import compute_patient_billing_report  # noqa: E402
from src.bilun.domain.claims.dataset_builder import _enrich_material_regulatory_flags  # noqa: E402
from src.bilun.domain.claims.models import (  # noqa: E402
    ClaimDiagnosis,
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    MedulaRejectionEvent,
    PerformedProcedureLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext  # noqa: E402

FACILITY_TIER = "2_3_basamak_ozel"
PROVIDER_TYPE = "Ozel"
Z = Decimal("0.00")


def D(s: str) -> date:
    return date.fromisoformat(s)


def money(x: float | Decimal) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _inforce(df: pl.DataFrame, d: str) -> pl.DataFrame:
    return df.filter((pl.col("valid_from") <= d) & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= d)))


def catalog_row(code: str, on: date) -> dict[str, Any]:
    """Return the EK-2B (or EK-2C for P-codes) row in force on ``on``; fail loudly."""
    d = on.isoformat()
    if code.startswith("P"):
        rows = _inforce(EK2C.filter(pl.col("package_code") == code), d)
        if rows.height != 1:
            raise ValueError(f"EK-2C {code} on {d}: {rows.height} rows")
        r = rows.row(0, named=True)
        return {"code": code, "name": r["name"], "puan": r["puan"], "price_try": r["price_try"],
                "valid_from": r["valid_from"], "annex": "EK-2C", "group": r["group"]}
    rows = _inforce(EK2B.filter(pl.col("code") == code), d)
    if rows.height != 1:
        raise ValueError(f"EK-2B {code} on {d}: {rows.height} rows")
    r = rows.row(0, named=True)
    return {"code": code, "name": r["name"], "puan": r["puan"], "price_try": r["price_try"],
            "valid_from": r["valid_from"], "annex": "EK-2B", "group": None}


def _category_for(code: str) -> str:
    if code.startswith("P"):
        return "paket"
    if code.startswith("L"):
        return "laboratuvar"
    if code in {"510010", "510120", "510121", "510090", "530000"}:
        return "yatak"
    if code.startswith("52"):
        return "muayene"
    return "islem"


@dataclass
class Bill:
    pid: str
    cid: str
    claim_type: str
    department: str
    admission: date | None
    discharge: date | None
    primary_icd10: str
    package_candidate: bool = False
    start: date | None = None
    end: date | None = None
    occupational_context: str = "none"
    procs: list[ProcedureClaimLine] = field(default_factory=list)
    mats: list[MaterialClaimLine] = field(default_factory=list)
    drugs: list[DrugClaimLine] = field(default_factory=list)
    dx: list[ClaimDiagnosis] = field(default_factory=list)
    performed: list[PerformedProcedureLine] = field(default_factory=list)
    medula: list[MedulaRejectionEvent] = field(default_factory=list)
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)  # line_id -> catalog provenance

    @property
    def episode(self) -> str:
        return self.cid.replace("C", "E", 1)

    # ── lines ────────────────────────────────────────────────────────────
    def diag(self, icd: str, *, primary: bool = False, role: str | None = None, on: date | None = None) -> None:
        n = len(self.dx) + 1
        self.dx.append(ClaimDiagnosis(
            diagnosis_id=f"{self.cid}-DX{n}", claim_id=self.cid, patient_id=self.pid,
            episode_id=self.episode, icd10_code=icd, is_primary=primary,
            diagnosis_role=role or ("primary" if primary else "secondary"),
            diagnosis_date=on or self.start or self.admission, exemption_eligible=False,
        ))

    def proc(self, code: str, on: date, qty: int = 1, *, category: str | None = None,
             unit_price: float | None = None, line_id: str | None = None, specialty: str = "",
             package_code: str = "", is_package_included: bool = False, sag_sol: str = "",
             name: str | None = None) -> str:
        row = catalog_row(code, on)
        unit = money(row["price_try"] if unit_price is None else unit_price)
        lid = line_id or f"{self.cid}-P{len(self.procs) + 1:02d}"
        billed = money(unit * qty)
        self.procs.append(ProcedureClaimLine(
            procedure_line_id=lid, claim_id=self.cid, patient_id=self.pid, episode_id=self.episode,
            procedure_date=on, procedure_code=code, procedure_name=name or row["name"],
            procedure_category=category or _category_for(code), quantity=qty,
            unit_price_try=unit, billed_amount_try=billed, expected_payable_try=billed,
            is_package_included=is_package_included, package_code=package_code,
            surcharge_applicable=False, copay_rate_applicable=False,
            denial_reason_expected="", rule_trace_expected="", procedure_specialty_code=specialty,
            sag_sol=sag_sol,
        ))
        self.sources[lid] = row
        return lid

    def mat(self, code: str, name: str, on: date, unit_price: float, *, qty: int = 1,
            proc_line_id: str = "", material_type: str = "implant", specialty_category: str = "",
            line_id: str | None = None, source: str = "", **flags: Any) -> str:
        lid = line_id or f"{self.cid}-M{len(self.mats) + 1:02d}"
        unit = money(unit_price)
        billed = money(unit * qty)
        self.mats.append(MaterialClaimLine(
            material_line_id=lid, claim_id=self.cid, procedure_line_id=proc_line_id,
            patient_id=self.pid, material_date=on, material_code=code, material_name=name,
            material_type=material_type, specialty_category=specialty_category, quantity=qty,
            unit_price_try=unit, billed_amount_try=billed, expected_payable_try=billed,
            is_bundled=False, requires_pre_auth=False, denial_reason_expected="",
            rule_trace_expected="", **flags,
        ))
        self.sources[lid] = {"code": code, "name": name, "price_try": unit_price, "source": source}
        return lid

    def drug(self, name: str, on: date, *, barkod: str, drug_code: str = "", qty: int = 1,
             unit_price: float = 0.0, equivalence_group: str = "", line_id: str | None = None,
             **clinical: Any) -> str:
        lid = line_id or f"{self.cid}-D{len(self.drugs) + 1:02d}"
        unit = money(unit_price)
        billed = money(unit * qty)
        self.drugs.append(DrugClaimLine(
            drug_claim_line_id=lid, prescription_id=f"{self.cid}-RX1", claim_id=self.cid,
            patient_id=self.pid, episode_id=self.episode, drug_claim_date=on, drug_name=name,
            drug_code=drug_code, barkod=barkod, equivalence_group=equivalence_group, quantity=qty,
            unit_price_try=unit, billed_amount_try=billed, expected_payable_try=billed,
            discount_tier_expected=Z, denial_reason_expected="", rule_trace_expected="", **clinical,
        ))
        return lid

    def perf(self, code: str, on: date, name: str | None = None, source: str = "emr") -> str:
        lid = f"{self.cid}-EMR{len(self.performed) + 1:02d}"
        row = catalog_row(code, on)
        self.performed.append(PerformedProcedureLine(
            performed_line_id=lid, claim_id=self.cid, patient_id=self.pid, episode_id=self.episode,
            service_date=on, procedure_code=code, procedure_name=name or row["name"], source=source,
        ))
        return lid

    # ── assembly ─────────────────────────────────────────────────────────
    def header(self) -> ClaimHeader:
        total = sum((p.billed_amount_try for p in self.procs), Z) + sum(
            (m.billed_amount_try for m in self.mats), Z) + sum((d.billed_amount_try for d in self.drugs), Z)
        return ClaimHeader(
            claim_id=self.cid, patient_id=self.pid, episode_id=self.episode, claim_type=self.claim_type,
            facility_tier=FACILITY_TIER, provider_type=PROVIDER_TYPE, department=self.department,
            admission_date=self.admission, discharge_date=self.discharge,
            claim_start_date=self.start or self.admission, claim_end_date=self.end or self.discharge,
            primary_icd10=self.primary_icd10, package_candidate=self.package_candidate,
            expected_total_billed_try=total, expected_total_payable_try=total,
            expected_denial_reason="", scenario_tag="", occupational_context=self.occupational_context,
        )

    def ctx(self) -> PatientClaimContext:
        header = self.header()
        mats = _enrich_material_regulatory_flags({m.material_line_id: m for m in self.mats}, {header.claim_id: header})
        return PatientClaimContext(
            patient_id=self.pid, claims=(header,), procedure_lines=tuple(self.procs),
            material_lines=tuple(mats.values()), drug_lines=tuple(self.drugs), diagnoses=tuple(self.dx),
            performed_procedure_lines=tuple(self.performed), medula_rejection_events=tuple(self.medula),
            medula_rejection_ingest_available=bool(self.medula),
        )

    def total(self) -> Decimal:
        return self.header().expected_total_billed_try

    def copy(self, cid_suffix: str = "") -> Bill:
        b = Bill(**{k: getattr(self, k) for k in ("pid", "cid", "claim_type", "department", "admission",
                                                  "discharge", "primary_icd10", "package_candidate",
                                                  "start", "end", "occupational_context")})
        b.procs, b.mats, b.drugs = list(self.procs), list(self.mats), list(self.drugs)
        b.dx, b.performed, b.medula = list(self.dx), list(self.performed), list(self.medula)
        b.sources = dict(self.sources)
        return b


def stay_dates(admission: date, discharge: date) -> list[date]:
    return [admission + timedelta(days=i) for i in range((discharge - admission).days + 1)]


# ── engine run + signal extraction ───────────────────────────────────────
_UPLIFT_BLOCKS = ("session_uplift", "drg_uplift", "blood_uplift", "yatak_puani", "icu_puani",
                  "yenidogan_yatak", "refakatci", "anestezi_puani", "material_uplift",
                  "care_setting_review", "procedure_addon_uplift", "drg_package_adequacy")
_MATERIAL_LISTS = ("pre_auth_required", "miat_restricted", "bundled_separate_billing",
                   "miat_interval_violations", "prose_bundling_violations", "specialty_prose_violations",
                   "kdv_price_reviews")


def _f(x: Any) -> float:
    try:
        return round(float(x or 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


def ui_signals(rep: Any, viol: list[dict]) -> list[tuple]:
    """What a user sees: recommended actions, block uplifts not in actions, scalars, compliance."""
    out: list[tuple] = []
    for a in rep.recommended_actions:
        tl = a.get("sgk_uplift_try") or a.get("audit_risk_try") or a.get("compliance_savings_try") or a.get("billed_try") or 0.0
        out.append(("action", a.get("surface"), a.get("kind"), a.get("procedure_code") or a.get("material_code") or a.get("drug_name") or "", _f(tl)))
    for name in ("anestezi_puani", "refakatci", "icu_puani", "yenidogan_yatak"):
        for r in getattr(rep, name).opportunities:
            amt = _f(r.get("recoverable_uplift_try"))
            if amt > 0:
                out.append(("block", name, r.get("rule_id") or r.get("type"), r.get("procedure_code") or r.get("anestezi_code") or "", amt))
    for scalar in ("audit_exposure_try", "capture_gap_try", "compliance_adjustment_try"):
        if _f(getattr(rep, scalar, 0.0)):
            out.append(("scalar", scalar, "", "", _f(getattr(rep, scalar))))
    for f in rep.claim_compliance.findings:
        out.append(("compliance", f.get("rule_id"), f.get("severity"), f.get("procedure_code") or f.get("material_code") or f.get("drug_code") or f.get("line_id") or "", 0.0))
    for blk in ("claim_reviews", "claim_advisories", "financial_findings"):
        for r in (getattr(rep, blk).rows or []):
            out.append(("wavea", blk, r.get("rule_id") or r.get("family"), "", _f(r.get("amount_try") or r.get("risk_amount_try"))))
    for v in viol:
        out.append(("validate", v.get("rule"), v.get("rule_id") or v.get("violation_kind") or "", v.get("material_code") or v.get("procedure_code") or v.get("drug_name") or "", _f(v.get("risk_amount") or v.get("savings_try"))))
    return out


def run_engine(ctx: PatientClaimContext) -> tuple[Any, list[dict]]:
    return compute_patient_billing_report(ctx.patient_id, claim_context=ctx), analyze_claim(ctx)


def signals(ctx: PatientClaimContext) -> tuple[list[tuple], Any, list[dict]]:
    """Every non-zero / non-informational output of the report and validation core."""
    rep = compute_patient_billing_report(ctx.patient_id, claim_context=ctx)
    out: list[tuple] = []
    for name in _UPLIFT_BLOCKS:
        for r in getattr(rep, name).opportunities:
            amt = _f(r.get("recoverable_uplift_try"))
            if amt > 0 or r.get("review_kind"):
                out.append(("report", name, r.get("type") or r.get("rule_id"), r.get("procedure_code") or r.get("anestezi_code") or r.get("bed_code") or "", amt))
    for r in rep.procedure_capture_gap.opportunities:
        out.append(("report", "procedure_capture_gap", r.get("type"), r.get("procedure_code"), _f(r.get("recoverable_gap_try"))))
    for r in rep.billing_strategy.recommendations:
        if r.get("type") == "informational":
            continue
        if r.get("message_code") in ("claim_package_ok", "claim_itemized_ok") and not _f(r.get("savings_try")):
            continue
        out.append(("report", "billing_strategy", r.get("type") or r.get("recommendation_kind"), r.get("procedure_code") or r.get("recommended_package_code") or "", _f(r.get("savings_try"))))
    for t in rep.lab.flagged_tests:
        out.append(("report", "lab", t.get("flag_type"), t.get("sut_code"), _f(t.get("savings_try"))))
    for lst in _MATERIAL_LISTS:
        for r in getattr(rep.materials, lst, []) or []:
            out.append(("report", f"materials.{lst}", r.get("rule_id") or r.get("note", "")[:40], r.get("sut_code") or r.get("material_code"), _f(r.get("price_try") or r.get("billed_try") or r.get("risk_amount"))))
    di = rep.drug_indication
    for f in (di.findings or []):
        out.append(("report", "drug_indication", f"{f.finding_kind}/{f.severity}", f.drug_name, 0.0))
    if not di.findings:
        for r in di.violations or []:
            out.append(("report", "drug_indication", r.get("violation_kind"), r.get("drug_name"), 0.0))
    for r in rep.medula_rejection_playbook.entries:
        out.append(("report", "medula_playbook", r.get("playbook_id"), r.get("sonuc_kodu"), 0.0))
    for r in rep.claim_submission_checklist.items:
        out.append(("report", "claim_checklist", r.get("checklist_kind"), r.get("procedure_code") or r.get("material_code") or "", 0.0))
    if _f(rep.audit_exposure_try):
        out.append(("report", "audit_exposure_try", "drg_unbundling", "", _f(rep.audit_exposure_try)))
    for f in rep.claim_compliance.findings:
        out.append(("compliance", f.get("rule_id"), f.get("line_kind"), f.get("line_id") or "", _f(f.get("billed_at_risk_try") or f.get("amount_try"))))
    for blk in ("claim_reviews", "claim_advisories", "financial_findings"):
        b = getattr(rep, blk)
        for r in (b.rows or []):
            out.append(("wavea", blk, r.get("rule_id") or r.get("family"), r.get("line_id") or r.get("claim_id") or "", _f(r.get("amount_try") or r.get("risk_amount_try"))))
    viol = analyze_claim(ctx)
    for v in viol:
        out.append(("validate", v.get("rule"), v.get("rule_id") or v.get("violation_kind") or "", v.get("material_name") or v.get("procedure_code") or v.get("drug_name") or "", _f(v.get("savings_try") or v.get("risk_amount"))))
    return out, rep, viol


def diff(clean: list[tuple], faulty: list[tuple]) -> tuple[list[tuple], list[tuple]]:
    from collections import Counter
    c, f = Counter(clean), Counter(faulty)
    only_f = list((f - c).elements())
    only_c = list((c - f).elements())
    return only_f, only_c


def bill_rows(b: Bill) -> list[dict[str, Any]]:
    rows = []
    for p in b.procs:
        src = b.sources.get(p.procedure_line_id, {})
        rows.append({"date": p.procedure_date.isoformat(), "code": p.procedure_code, "name": p.procedure_name,
                     "qty": p.quantity, "unit": str(p.unit_price_try), "billed": str(p.billed_amount_try),
                     "source": f"{src.get('annex', '')} valid_from {src.get('valid_from', '')}"})
    for m in b.mats:
        src = b.sources.get(m.material_line_id, {})
        rows.append({"date": m.material_date.isoformat(), "code": m.material_code, "name": m.material_name,
                     "qty": m.quantity, "unit": str(m.unit_price_try), "billed": str(m.billed_amount_try),
                     "source": src.get("source", "")})
    for d in b.drugs:
        rows.append({"date": d.drug_claim_date.isoformat() if d.drug_claim_date else "", "code": d.barkod,
                     "name": d.drug_name, "qty": d.quantity, "unit": str(d.unit_price_try),
                     "billed": str(d.billed_amount_try), "source": "EK-4A"})
    return rows
