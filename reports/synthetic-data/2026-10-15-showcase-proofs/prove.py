"""Prove each showcase fault: target detector fires on the faulty bill, silent on the clean bill.

Run from the repo root: .venv/bin/python reports/synthetic-data/2026-10-15-showcase-proofs/prove.py [S1 ...]
Writes results/<story>.json with bill rows, direct-detector output and the
full-report signal diff. Read-only on the repo.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

from harness import bill_rows, run_engine, ui_signals
from stories import CLEAN_ONLY, STORIES

from src.bilun.domain.billing.claim_lab import _optimize_lab_billing_from_claims
from src.bilun.domain.billing.claim_strategy import recommend_billing_strategy_from_claims
from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
from src.bilun.domain.prose_rules.anestezi_puani import detect_anestezi_puani_opportunities
from src.bilun.domain.prose_rules.common_billing_errors import (
    detect_drug_quantity_error,
    detect_duplicate_exam_10day,
    detect_vakabasi_wrong_method,
)
from src.bilun.domain.prose_rules.drg_unbundling import analyze_claim_unbundling
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities
from src.bilun.domain.prose_rules.material_bundling import check_material_bundling_for_context
from src.bilun.domain.prose_rules.medula_rejection import detect_medula_rejection_playbook_entries
from src.bilun.domain.prose_rules.claim_utils import claim_is_day_case, infer_care_setting
from src.bilun.domain.prose_rules.payment_method import check_payment_method_compliance
from src.bilun.domain.prose_rules.procedure_addon_uplift import detect_missing_procedure_addon_opportunities
from src.bilun.domain.prose_rules.procedure_capture_gap import detect_procedure_capture_gaps
from src.bilun.domain.prose_rules.refakatci import detect_refakatci_opportunities
from src.bilun.domain.prose_rules.session_uplift import detect_session_underbilling_opportunities
from src.bilun.domain.prose_rules.yatak_icu_overlap import detect_yatak_icu_overlap
from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities
from src.bilun.domain.prose_rules.yenidogan_yatak import detect_yenidogan_yatak_opportunities

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUT, exist_ok=True)


def _keep(d: dict, keys) -> dict:
    return {k: d.get(k) for k in keys if k in d}


def direct(story: str, ctx) -> list[dict]:
    """Call the target rule the way the unit tests do; return its raw rows (trimmed)."""
    claims, procs = list(ctx.claims), list(ctx.procedure_lines)
    claim = claims[0]
    if story in ("S1", "S20"):
        # S20 is a day case: the care setting and the day-case flag as the billing strategy derives them
        codes = ("610131", "P610131") if story == "S1" else ("603840", "P603840")
        setting = "inpatient" if story == "S1" else infer_care_setting(claim)
        rows = []
        for line in procs:
            if line.procedure_code in codes:
                c = check_payment_method_compliance(
                    line.procedure_code, billed_as_package=line.procedure_category == "paket",
                    care_setting=setting, facility_tier=claim.facility_tier,
                    provider_type=claim.provider_type, as_of_date=line.procedure_date,
                    day_case=claim_is_day_case(claim))
                rows.append({"fn": "check_payment_method_compliance", "code": c.procedure_code,
                             "kind": c.kind, "mandated": c.mandated_method, "compliant": c.is_compliant,
                             "section": c.trace.sut_section, "detail": c.detail})
        for r in recommend_billing_strategy_from_claims(ctx).recommendations:
            if r.get("type") == "informational":
                continue
            rows.append({"fn": "recommend_billing_strategy_from_claims", **_keep(r, (
                "type", "procedure_code", "recommendation", "payment_method_kind", "current_billing",
                "package_total_try", "itemized_total_try", "savings_try", "sut_section_id", "detail"))})
        return rows
    if story in ("S2", "S47"):
        return [_keep(o, ("rule_id", "bed_days", "gross_bed_days", "daily_rate_try", "expected_yatak_try",
                          "actual_billed_try", "recoverable_uplift_try", "detail"))
                for o in detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={claim.claim_id})]
    if story == "S3":
        return [_keep(o, ("rule_id", "procedure_code", "procedure_puan", "anestezi_group", "anestezi_code",
                          "anestezi_puan", "katsayi", "expected_try", "actual_billed_try",
                          "recoverable_uplift_try", "detail"))
                for o in detect_anestezi_puani_opportunities(claims, procs)]
    if story == "S4":
        return [_keep(o, ("rule_id", "days", "puan", "expected_try", "actual_billed_try",
                          "recoverable_uplift_try", "detail"))
                for o in detect_refakatci_opportunities(claims, procs)]
    if story == "S5":
        return [_keep(v, ("rule_id", "severity", "material_code", "risk_amount", "material_outcome",
                          "sut_section", "message"))
                for v in check_material_bundling_for_context(ctx) if v.get("rule_id") == "3.1.1.(2).titubb_uts_incomplete"]
    if story in ("S6", "S17"):
        rows = []
        drug = {"S6": "PK-MERZ", "S17": "ARANESP"}[story]  # the drug line of the fault
        for dl in ctx.drug_lines:
            if not dl.drug_name.startswith(drug):
                continue
            res = evaluate_drug_indication_line_detailed(drug_line=dl, claim=claim, diagnoses=list(ctx.diagnoses))
            v = res.get("violation") or {}
            rows.append({"fn": "evaluate_drug_indication_line_detailed",
                         "applicability_status": res.get("applicability_status"),
                         "selected_rule_id": res.get("selected_rule_id"),
                         "eligible_icd10": res.get("eligible_icd10_codes_or_ranges"),
                         "observed_icd10": res.get("observed_icd10_codes"),
                         "violation_kind": v.get("violation_kind"), "severity": v.get("severity"),
                         "message_tr": v.get("message_tr")})
        for f in evaluate_drug_indication_findings(ctx.patient_id, ctx).findings:
            rows.append({"fn": "evaluate_drug_indication_findings", "drug": f.drug_name,
                         "finding_kind": f.finding_kind, "severity": f.severity,
                         "applicability_status": f.applicability_status})
        return rows
    if story == "S7":
        return [_keep(o, ("rule_id", "procedure_code", "procedure_name", "service_date", "source",
                          "list_price_try", "recoverable_gap_try", "price_methodology", "detail"))
                for o in detect_procedure_capture_gaps(claim, list(ctx.performed_procedure_lines), procs)]
    if story == "S8":
        f = analyze_claim_unbundling(claim, procs, same_incision=True)
        return [_keep(v, ("rule_id", "procedure_code", "primary_procedure_code", "expected_point_factor",
                          "expected_billed_try", "actual_billed_try", "risk_amount_try", "sut_section", "detail"))
                for v in f.session_violations]
    if story == "S9":
        # as recommend_session_uplift_from_claims calls it: no claim line carries the incision
        return [_keep(o, ("rule_id", "procedure_code", "primary_procedure_code", "session_date",
                          "expected_point_factor", "strict_point_factor", "lenient_point_factor",
                          "expected_billed_try", "strict_expected_billed_try",
                          "lenient_expected_billed_try", "actual_billed_try",
                          "recoverable_uplift_try", "review_uplift_try", "missing_facts",
                          "sut_section_id"))
                for o in detect_session_underbilling_opportunities(
                    procs, claim_id=claim.claim_id, cross_specialty=None, claim=claim)]
    if story == "S10":
        # the lab optimizer's unbundling rows, then the MEDULA playbook rows of the bill's rejection events
        rows = [{"fn": "optimize_lab_billing", **_keep(t, (  # no `detail`: it names the episode id
            "flag_type", "sut_code", "gazette_price", "savings_try"))}
            for t in _optimize_lab_billing_from_claims(ctx).flagged_tests]
        rows += [{"fn": "detect_medula_rejection_playbook_entries", **_keep(e, (
            "playbook_id", "sonuc_kodu", "medula_stage", "hata_mesaji", "related_procedure_code",
            "related_line_type", "sut_anchor", "rebill_permitted", "rebill_stage", "rule_id"))}
            for e in detect_medula_rejection_playbook_entries(claim, list(ctx.medula_rejection_events))]
        return rows
    if story == "S22":
        return [_keep(o, ("type", "trigger_procedure_code", "expected_addon_procedure_code", "session_date",
                          "addon_factor", "trigger_billed_try", "list_price_try", "actual_billed_try",
                          "recoverable_uplift_try", "price_methodology", "same_incision", "sut_section_id",
                          "rule_id"))
                for o in detect_missing_procedure_addon_opportunities(claim, procs)]
    if story == "S11":
        return [_keep(o, ("claim_id", "icu_days", "intermediate_package", "intermediate_days", "day_rate_puan",
                          "intermediate_puan_base", "ilave_oran_pct", "ilave_oran_reason", "total_puan",
                          "total_try", "actual_billed_try", "recoverable_uplift_try", "rule_id",
                          "sut_section_id"))
                for o in detect_icu_puani_opportunities(claims, procs)]
    if story == "S12":
        return [_keep(o, ("claim_id", "bed_code", "days", "bundled_days", "puan", "expected_try", "actual_billed_try",
                          "recoverable_uplift_try", "same_day_stay", "rooming_in", "rule_id", "sut_section_id"))
                for o in detect_yenidogan_yatak_opportunities(
                    claims, list(ctx.diagnoses), procedure_lines=procs, claim_ids_with_procs={claim.claim_id})]
    if story == "S14":
        # a cross-bill rule: the ICU bill is history, so read the whole history, as the report does
        return [_keep(o, ("type", "claim_id", "rule_id", "procedure_code", "overlap_date", "icu_claim_id",
                          "risk_amount_try", "sut_section_id"))
                for o in detect_yatak_icu_overlap(
                    list(ctx.history.claims), list(ctx.history.procedure_lines),
                    claim_ids_with_procs={claim.claim_id})]
    if story == "S40":
        # a cross-bill rule: the control of the same branch a week earlier is history, so read the whole history
        return [_keep(o, ("type", "claim_id", "rule_id", "procedure_code", "procedure_specialty_code",
                          "procedure_date", "prior_claim_id", "prior_procedure_date", "gap_days",
                          "severity", "sut_section_id"))
                for o in detect_duplicate_exam_10day(list(ctx.history.claims), list(ctx.history.procedure_lines))]
    if story == "S33":
        return [_keep(o, ("rule_id", "drug_name", "quantity", "severity", "sut_section_id", "detail"))
                for o in detect_drug_quantity_error(claims, tuple(ctx.drug_lines))]
    if story == "S34":
        return [_keep(o, ("rule_id", "procedure_code", "procedure_category", "is_package_included", "severity",
                          "sut_section_id", "detail"))
                for o in detect_vakabasi_wrong_method(claims, procs)]
    raise KeyError(story)


def prove(story: str) -> dict:
    builder = STORIES[story]
    out: dict = {"story": story}
    sig: dict = {}
    for variant in ("clean", "faulty"):
        bill = builder(variant)
        ctx = bill.ctx()
        rep, viol = run_engine(ctx)
        sig[variant] = ui_signals(rep, viol)
        out[variant] = {
            "total_billed": str(bill.total()),
            "rows": bill_rows(bill),
            "diagnoses": [(d.icd10_code, d.is_primary) for d in bill.dx],
            "performed": [(p.procedure_code, p.service_date.isoformat(), p.source) for p in bill.performed],
            "direct": direct(story, ctx),
            "report": {"sgk_uplift_try": rep.sgk_uplift_try, "audit_exposure_try": rep.audit_exposure_try,
                       "capture_gap_try": rep.capture_gap_try,
                       "compliance_adjustment_try": rep.compliance_adjustment_try,
                       "action_count": rep.action_count},
        }
    c, f = Counter(sig["clean"]), Counter(sig["faulty"])
    out["only_in_faulty"] = [list(x) for x in (f - c).elements()]
    out["only_in_clean"] = [list(x) for x in (c - f).elements()]
    out["noise_in_clean"] = [list(x) for x in sig["clean"]]
    with open(os.path.join(OUT, f"{story}.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    return out


def _print(out: dict) -> None:
    s = out["story"]
    print(f"\n######## {s}  clean total {out['clean']['total_billed']}  faulty total {out['faulty']['total_billed']}")
    for v in ("clean", "faulty"):
        print(f"  [{v}] direct:")
        for r in out[v]["direct"] or [{"(none)": "rule silent"}]:
            print("     ", r)
        print(f"  [{v}] report:", out[v]["report"])
    print("  ONLY IN FAULTY:")
    for x in out["only_in_faulty"]:
        print("     ", x)
    print("  ONLY IN CLEAN:")
    for x in out["only_in_clean"]:
        print("     ", x)
    hide = {"wavea", "validate"}
    print("  NOISE ON CLEAN (actions/blocks/scalars/compliance):")
    for x in out["noise_in_clean"]:
        if x[0] not in hide:
            print("     ", x)


_MONEY = ("sgk_uplift_try", "audit_exposure_try", "capture_gap_try", "compliance_adjustment_try")


def target_amount(story: str, rows: list[dict]) -> float | None:
    """The injected fault's amount from the direct rows (0.0 when it has none), None if silent."""
    def total(key: str) -> float | None:
        amount = sum(float(r.get(key) or 0.0) for r in rows)
        return round(amount, 2) if amount > 0 else None
    if story in ("S1", "S20"):
        if not any(r.get("compliant") is False for r in rows):
            return None
        return next((r["savings_try"] for r in rows if r.get("current_billing") == "itemized"), 0.0)
    if story in ("S2", "S3", "S4", "S9", "S11", "S12", "S22", "S47"):
        return total("recoverable_uplift_try")
    if story == "S10":
        return total("savings_try")
    if story == "S5":
        return total("risk_amount")
    if story in ("S6", "S17"):  # a drug-indication violation without money
        kind = {"S6": "indication_mismatch", "S17": "prescriber_specialty_mismatch"}[story]
        return 0.0 if any(r.get("violation_kind") == kind for r in rows) else None
    if story in ("S33", "S34", "S40"):  # a row without money: the finding is the row
        rule = {"S33": "tablo15_11_drug_quantity_error", "S34": "tablo15_3_vakabasi_wrong_method",
                "S40": "tablo15_2_duplicate_exam_10day"}[story]
        return 0.0 if any(r.get("rule_id") == rule for r in rows) else None
    return total("recoverable_gap_try" if story == "S7" else "risk_amount_try")


def summary(results: list[dict]) -> bool:
    """Every target fires on the faulty bill only, and every clean bill carries 0 TL."""
    ok = True
    print("\nstory | target on faulty | target on clean | clean money (report) | faulty money (report)")
    for out in results:
        s = out["story"]
        fault, clean = (target_amount(s, out[v]["direct"]) for v in ("faulty", "clean"))
        clean_money = {k: out["clean"]["report"][k] for k in _MONEY if out["clean"]["report"][k]}
        faulty_money = {k: out["faulty"]["report"][k] for k in _MONEY if out["faulty"]["report"][k]}
        good = fault is not None and clean is None and not clean_money
        ok &= good
        print(f"{s} | {fault} | {clean} | {clean_money or 0} | {faulty_money or 0} | {'OK' if good else 'FAIL'}")
    return ok


def default_stories() -> list[str]:
    """The stories `prove.py` proves with no argument: every story with a fault (a clean bill has no proof)."""
    return [s for s in STORIES if s not in CLEAN_ONLY]


if __name__ == "__main__":
    which = sys.argv[1:] or default_stories()
    results = [prove(s) for s in which]
    for out in results:
        _print(out)
    sys.exit(0 if summary(results) else 1)
