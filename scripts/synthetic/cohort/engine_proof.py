"""Prove that the billing and prose-rules engine finds every showcase fault (S1..S9) on the committed dataset."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
from typing import Any

from src.bilun.domain.billing.claim_strategy import recommend_billing_strategy_from_claims
from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
from src.bilun.domain.billing.engine import analyze_claim
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.claims.config import SUTDataSourceConfigError
from src.bilun.domain.claims.dataset import ClaimTables, SUTClaimDataset
from src.bilun.domain.claims.dataset_builder import _enrich_material_regulatory_flags
from src.bilun.domain.claims.errors import ClaimValidationError
from src.bilun.domain.claims.loader import read_claim_tables
from src.bilun.domain.claims.parquet_reader import _read_parquet_table
from src.bilun.domain.claims.patient_context import (
    PatientClaimContext,
    build_patient_claim_context,
)
from src.bilun.domain.claims.schema import (
    CLAIM_DIAGNOSES,
    CLAIM_HEADERS,
    DRUG_CLAIM_LINES,
    EXPECTED_RULE_OUTPUTS,
    MATERIAL_CLAIM_LINES,
    MEDULA_REJECTION_EVENTS,
    OPTIONAL_CLAIM_TABLES,
    PATIENT_COPAY_PROFILES,
    PERFORMED_PROCEDURE_LINES,
    PROCEDURE_CLAIM_LINES,
    REQUIRED_CLAIM_TABLES,
)
from src.bilun.domain.prose_rules.anestezi_puani import detect_anestezi_puani_opportunities
from src.bilun.domain.prose_rules.drg_unbundling import analyze_claim_unbundling
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities
from src.bilun.domain.prose_rules.material_bundling import check_material_bundling_for_context
from src.bilun.domain.prose_rules.payment_method import check_payment_method_compliance
from src.bilun.domain.prose_rules.procedure_capture_gap import detect_procedure_capture_gaps
from src.bilun.domain.prose_rules.refakatci import detect_refakatci_opportunities
from src.bilun.domain.prose_rules.session_uplift import detect_session_underbilling_opportunities
from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

from scripts.synthetic.faults import FaultInjectionRecord

from .build import DEFAULT_OUT_DIR, REPO, BuildError, BuildResult, build_showcase
from .compose import ComposedClaim, money
from .ids import (
    DRUG_CLAIM_LINE_ID_RE,
    MATERIAL_LINE_ID_RE,
    PERFORMED_LINE_ID_RE,
    PROCEDURE_LINE_ID_RE,
)

PROOFS_RESULTS_DIR = REPO / "reports" / "synthetic-data" / "2026-10-15-showcase-proofs" / "results"
REPORT_SCALAR_KEYS: tuple[str, ...] = (
    "sgk_uplift_try",
    "audit_exposure_try",
    "capture_gap_try",
    "compliance_adjustment_try",
    "action_count",
)
_ZERO = Decimal("0.00")

_PROOF_PROC_ID_RE = re.compile(r"^C-SH\d{2}-P(\d+)$")
_PROOF_MAT_ID_RE = re.compile(r"^C-SH\d{2}-M(\d+)$")
_PROOF_DRUG_ID_RE = re.compile(r"^C-SH\d{2}-D(\d+)$")
_PROOF_PERF_ID_RE = re.compile(r"^C-SH\d{2}-EMR(\d+)$")
_PROOF_CLAIM_ID_RE = re.compile(r"C-SH\d{2}")
_PROOF_PATIENT_ID_RE = re.compile(r"\bSH-\d{2}\b")


@dataclass(frozen=True)
class ReportDivergence:
    """Documented divergence between full-report exposure and direct/record fault amount."""

    report_amount_try: str
    record_amount_try: str
    reason: str
    issue: str


KNOWN_REPORT_DIVERGENCES: dict[str, ReportDivergence] = {
    "S8": ReportDivergence(
        report_amount_try="3584.80",
        record_amount_try="5377.20",
        reason=(
            "No claim line carries the incision, so the report shows the lenient 50% reading "
            "and the record carries the same-incision 25% reading."
        ),
        issue="Safa675/Bilun#311 item 6",
    ),
    "S9": ReportDivergence(
        report_amount_try="151.60",
        record_amount_try="758.01",
        reason=(
            "No claim line carries the incision, so the report prices the uplift at the strictest "
            "reading (same incision, 30%) and the record carries the whole gap to the clean bill, "
            "which bills the separate-incision rate (50%)."
        ),
        issue="Safa675/Bilun#311 item 6",
    ),
}


@dataclass(frozen=True)
class StoryProof:
    """Engine proof comparison result for one showcase story (clean twin vs loaded faulty claim)."""

    story: str
    patient_id: str
    claim_id: str
    fault_id: str
    amount_try: str
    faulty_signals: tuple[tuple[Any, ...], ...]
    clean_signals: tuple[tuple[Any, ...], ...]
    only_in_faulty: tuple[tuple[Any, ...], ...]
    only_in_clean: tuple[tuple[Any, ...], ...]
    direct_faulty: list[dict[str, Any]]
    direct_clean: list[dict[str, Any]]
    mismatches: tuple[str, ...]
    note: str = ""


def _read_showcase_claim_tables(claims_dir: Path) -> ClaimTables:
    try:
        return read_claim_tables(claims_dir=claims_dir, mode="synthetic_demo")
    except SUTDataSourceConfigError:
        errors: list[str] = []
        required_rows = {
            spec.filename: _read_parquet_table(spec, claims_dir, errors)
            for spec in REQUIRED_CLAIM_TABLES
        }
        optional_rows: dict[str, tuple[dict[str, Any], ...]] = {}
        availability_flags: dict[str, bool] = {}
        for spec in OPTIONAL_CLAIM_TABLES:
            if spec.sets_availability_flag and (claims_dir / spec.filename).exists():
                availability_flags[spec.sets_availability_flag] = True
            optional_rows[spec.filename] = _read_parquet_table(spec, claims_dir, errors)
        if errors:
            raise ClaimValidationError(errors)
        return ClaimTables(
            headers=required_rows[CLAIM_HEADERS.filename],
            diagnoses=required_rows[CLAIM_DIAGNOSES.filename],
            procedures=required_rows[PROCEDURE_CLAIM_LINES.filename],
            materials=required_rows[MATERIAL_CLAIM_LINES.filename],
            drugs=required_rows[DRUG_CLAIM_LINES.filename],
            expected_outputs=required_rows[EXPECTED_RULE_OUTPUTS.filename],
            copay_profiles=optional_rows.get(PATIENT_COPAY_PROFILES.filename, ()),
            performed_procedures=optional_rows.get(PERFORMED_PROCEDURE_LINES.filename, ()),
            medula_rejections=optional_rows.get(MEDULA_REJECTION_EVENTS.filename, ()),
            medula_rejection_ingest_available=availability_flags.get(
                "medula_rejection_ingest_available", False
            ),
        )


def load_showcase_dataset(
    claims_dir: Path | str = DEFAULT_OUT_DIR / "sut" / "claims",
) -> SUTClaimDataset:
    """Load the showcase claim dataset from ``claims_dir`` without monkeypatching path guards."""
    resolved_dir = Path(claims_dir).resolve()
    tables = _read_showcase_claim_tables(resolved_dir)
    return SUTClaimDataset.from_rows(
        claim_headers=tables.headers,
        diagnoses=tables.diagnoses,
        procedure_lines=tables.procedures,
        material_lines=tables.materials,
        drug_lines=tables.drugs,
        expected_outputs=tables.expected_outputs,
        copay_profiles=tables.copay_profiles,
        performed_procedure_lines=tables.performed_procedures,
        medula_rejection_events=tables.medula_rejections,
        medula_rejection_ingest_available=tables.medula_rejection_ingest_available,
    )


def context_from_composed(claim: ComposedClaim) -> PatientClaimContext:
    """Build an in-memory ``PatientClaimContext`` from a ``ComposedClaim``.

    Mirrors ``Bill.ctx()`` in ``reports/synthetic-data/2026-10-15-showcase-proofs/harness.py``.
    """
    header = claim.header
    mats = _enrich_material_regulatory_flags(
        {m.material_line_id: m for m in claim.materials},
        {header.claim_id: header},
    )
    return PatientClaimContext(
        patient_id=header.patient_id,
        claims=(header,),
        procedure_lines=claim.procedures,
        material_lines=tuple(mats.values()),
        drug_lines=claim.drugs,
        diagnoses=claim.diagnoses,
        performed_procedure_lines=claim.performed,
        medula_rejection_events=(),
        medula_rejection_ingest_available=False,
    )


def _f(x: Any) -> float:
    """Round a numeric value to 2 decimals as a float (ported from showcase-proofs ``harness.py``)."""
    try:
        return round(float(x or 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


def ui_signals(rep: Any, viol: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    """Extract user-facing signal tuples from a billing report and validation list.

    Ported from ``reports/synthetic-data/2026-10-15-showcase-proofs/harness.py``.
    """
    out: list[tuple[Any, ...]] = []
    for a in rep.recommended_actions:
        tl = (
            a.get("sgk_uplift_try")
            or a.get("audit_risk_try")
            or a.get("compliance_savings_try")
            or a.get("billed_try")
            or 0.0
        )
        out.append(
            (
                "action",
                a.get("surface"),
                a.get("kind"),
                a.get("procedure_code") or a.get("material_code") or a.get("drug_name") or "",
                _f(tl),
            )
        )
    for name in ("anestezi_puani", "refakatci", "icu_puani", "yenidogan_yatak"):
        for r in getattr(rep, name).opportunities:
            amt = _f(r.get("recoverable_uplift_try"))
            if amt > 0:
                out.append(
                    (
                        "block",
                        name,
                        r.get("rule_id") or r.get("type"),
                        r.get("procedure_code") or r.get("anestezi_code") or "",
                        amt,
                    )
                )
    for scalar in ("audit_exposure_try", "capture_gap_try", "compliance_adjustment_try"):
        if _f(getattr(rep, scalar, 0.0)):
            out.append(("scalar", scalar, "", "", _f(getattr(rep, scalar))))
    for f in rep.claim_compliance.findings:
        out.append(
            (
                "compliance",
                f.get("rule_id"),
                f.get("severity"),
                f.get("procedure_code")
                or f.get("material_code")
                or f.get("drug_code")
                or f.get("line_id")
                or "",
                0.0,
            )
        )
    for blk in ("claim_reviews", "claim_advisories", "financial_findings"):
        for r in getattr(rep, blk).rows or []:
            out.append(
                (
                    "wavea",
                    blk,
                    r.get("rule_id") or r.get("family"),
                    "",
                    _f(r.get("amount_try") or r.get("risk_amount_try")),
                )
            )
    for v in viol:
        out.append(
            (
                "validate",
                v.get("rule"),
                v.get("rule_id") or v.get("violation_kind") or "",
                v.get("material_code") or v.get("procedure_code") or v.get("drug_name") or "",
                _f(v.get("risk_amount") or v.get("savings_try")),
            )
        )
    return out


def run_engine(ctx: PatientClaimContext) -> tuple[Any, list[dict[str, Any]]]:
    """Run ``compute_patient_billing_report`` and ``analyze_claim`` on ``ctx``.

    Ported from ``reports/synthetic-data/2026-10-15-showcase-proofs/harness.py``.
    """
    return (
        compute_patient_billing_report(ctx.patient_id, claim_context=ctx),
        analyze_claim(ctx),
    )


def _keep(d: Mapping[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    """Keep selected keys from ``d`` in order (ported from showcase-proofs ``prove.py``)."""
    return {k: d.get(k) for k in keys if k in d}


def normalize(obj: Any) -> Any:
    """Normalize ``obj`` through JSON round-trip with ``default=str`` as the proofs' JSON does."""
    return json.loads(json.dumps(obj, ensure_ascii=False, default=str))


def canonicalize_text(
    value: Any,
    claim_id: str | None = None,
    patient_id: str | None = None,
) -> Any:
    """Replace cohort and proof claim/patient IDs inside strings throughout a JSON-like structure."""
    if isinstance(value, str):
        text = value
        if claim_id:
            text = text.replace(claim_id, "<claim>")
        text = _PROOF_CLAIM_ID_RE.sub("<claim>", text)
        if patient_id:
            text = text.replace(patient_id, "<patient>")
        text = _PROOF_PATIENT_ID_RE.sub("<patient>", text)
        return text
    if isinstance(value, list):
        return [canonicalize_text(item, claim_id, patient_id) for item in value]
    if isinstance(value, tuple):
        return tuple(canonicalize_text(item, claim_id, patient_id) for item in value)
    if isinstance(value, Mapping):
        return {k: canonicalize_text(v, claim_id, patient_id) for k, v in value.items()}
    return value


def _direct_rows_s1(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    claim = ctx.claims[0]
    rows: list[dict[str, Any]] = []
    for line in ctx.procedure_lines:
        if line.procedure_code in ("610131", "P610131"):
            c = check_payment_method_compliance(
                line.procedure_code,
                billed_as_package=line.procedure_category == "paket",
                care_setting="inpatient",
                facility_tier=claim.facility_tier,
                provider_type=claim.provider_type,
                as_of_date=line.procedure_date,
            )
            rows.append(
                {
                    "fn": "check_payment_method_compliance",
                    "code": c.procedure_code,
                    "kind": c.kind,
                    "mandated": c.mandated_method,
                    "compliant": c.is_compliant,
                    "section": c.trace.sut_section,
                    "detail": c.detail,
                }
            )
    for r in recommend_billing_strategy_from_claims(ctx).recommendations:
        if r.get("type") == "informational":
            continue
        rows.append(
            {
                "fn": "recommend_billing_strategy_from_claims",
                **_keep(
                    r,
                    (
                        "type",
                        "procedure_code",
                        "recommendation",
                        "payment_method_kind",
                        "current_billing",
                        "package_total_try",
                        "itemized_total_try",
                        "savings_try",
                        "sut_section_id",
                        "detail",
                    ),
                ),
            }
        )
    return rows


def _direct_rows_s2(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    claims, procs = list(ctx.claims), list(ctx.procedure_lines)
    claim = claims[0]
    return [
        _keep(
            o,
            (
                "rule_id",
                "bed_days",
                "gross_bed_days",
                "daily_rate_try",
                "expected_yatak_try",
                "actual_billed_try",
                "recoverable_uplift_try",
                "detail",
            ),
        )
        for o in detect_yatak_puani_opportunities(
            claims, procs, claim_ids_with_procs={claim.claim_id}
        )
    ]


def _direct_rows_s3(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    return [
        _keep(
            o,
            (
                "rule_id",
                "procedure_code",
                "procedure_puan",
                "anestezi_group",
                "anestezi_code",
                "anestezi_puan",
                "katsayi",
                "expected_try",
                "actual_billed_try",
                "recoverable_uplift_try",
                "detail",
            ),
        )
        for o in detect_anestezi_puani_opportunities(list(ctx.claims), list(ctx.procedure_lines))
    ]


def _direct_rows_s4(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    return [
        _keep(
            o,
            (
                "rule_id",
                "days",
                "puan",
                "expected_try",
                "actual_billed_try",
                "recoverable_uplift_try",
                "detail",
            ),
        )
        for o in detect_refakatci_opportunities(list(ctx.claims), list(ctx.procedure_lines))
    ]


def _direct_rows_s5(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    return [
        _keep(
            v,
            (
                "rule_id",
                "severity",
                "material_code",
                "risk_amount",
                "material_outcome",
                "sut_section",
                "message",
            ),
        )
        for v in check_material_bundling_for_context(ctx)
        if v.get("rule_id") == "3.1.1.(2).titubb_uts_incomplete"
    ]


def _direct_rows_s6(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    claim = ctx.claims[0]
    rows: list[dict[str, Any]] = []
    for dl in ctx.drug_lines:
        if not dl.drug_name.startswith("PK-MERZ"):
            continue
        res = evaluate_drug_indication_line_detailed(
            drug_line=dl, claim=claim, diagnoses=list(ctx.diagnoses)
        )
        v = res.get("violation") or {}
        rows.append(
            {
                "fn": "evaluate_drug_indication_line_detailed",
                "applicability_status": res.get("applicability_status"),
                "selected_rule_id": res.get("selected_rule_id"),
                "eligible_icd10": res.get("eligible_icd10_codes_or_ranges"),
                "observed_icd10": res.get("observed_icd10_codes"),
                "violation_kind": v.get("violation_kind"),
                "severity": v.get("severity"),
                "message_tr": v.get("message_tr"),
            }
        )
    for f in evaluate_drug_indication_findings(ctx.patient_id, ctx).findings:
        rows.append(
            {
                "fn": "evaluate_drug_indication_findings",
                "drug": f.drug_name,
                "finding_kind": f.finding_kind,
                "severity": f.severity,
                "applicability_status": f.applicability_status,
            }
        )
    return rows


def _direct_rows_s7(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    claim = ctx.claims[0]
    return [
        _keep(
            o,
            (
                "rule_id",
                "procedure_code",
                "procedure_name",
                "service_date",
                "source",
                "list_price_try",
                "recoverable_gap_try",
                "price_methodology",
                "detail",
            ),
        )
        for o in detect_procedure_capture_gaps(
            claim, list(ctx.performed_procedure_lines), list(ctx.procedure_lines)
        )
    ]


def _direct_rows_s8(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    finding = analyze_claim_unbundling(ctx.claims[0], list(ctx.procedure_lines), same_incision=True)
    return [
        _keep(
            v,
            (
                "rule_id",
                "procedure_code",
                "primary_procedure_code",
                "expected_point_factor",
                "expected_billed_try",
                "actual_billed_try",
                "risk_amount_try",
                "sut_section",
                "detail",
            ),
        )
        for v in finding.session_violations
    ]


def _direct_rows_s9(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    claim = ctx.claims[0]
    # As recommend_session_uplift_from_claims calls it: no claim line carries the incision.
    return [
        _keep(
            o,
            (
                "rule_id",
                "procedure_code",
                "primary_procedure_code",
                "session_date",
                "expected_point_factor",
                "strict_point_factor",
                "lenient_point_factor",
                "expected_billed_try",
                "strict_expected_billed_try",
                "lenient_expected_billed_try",
                "actual_billed_try",
                "recoverable_uplift_try",
                "review_uplift_try",
                "missing_facts",
                "sut_section_id",
            ),
        )
        for o in detect_session_underbilling_opportunities(
            list(ctx.procedure_lines),
            claim_id=claim.claim_id,
            cross_specialty=None,
            claim=claim,
        )
    ]


def _direct_rows_s11(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    return [
        _keep(
            o,
            (
                "claim_id",
                "icu_days",
                "intermediate_package",
                "intermediate_days",
                "day_rate_puan",
                "intermediate_puan_base",
                "ilave_oran_pct",
                "ilave_oran_reason",
                "total_puan",
                "total_try",
                "actual_billed_try",
                "recoverable_uplift_try",
                "rule_id",
                "sut_section_id",
            ),
        )
        for o in detect_icu_puani_opportunities(list(ctx.claims), list(ctx.procedure_lines))
    ]


_DIRECT_ROWS_BY_STORY: dict[str, Callable[[PatientClaimContext], list[dict[str, Any]]]] = {
    "S1": _direct_rows_s1,
    "S2": _direct_rows_s2,
    "S3": _direct_rows_s3,
    "S4": _direct_rows_s4,
    "S5": _direct_rows_s5,
    "S6": _direct_rows_s6,
    "S7": _direct_rows_s7,
    "S8": _direct_rows_s8,
    "S9": _direct_rows_s9,
    "S11": _direct_rows_s11,
}


def direct_rows(story: str, ctx: PatientClaimContext) -> list[dict[str, Any]]:
    """Run the target detector for ``story`` on ``ctx`` and return JSON-serialisable rows.

    Ported from ``direct(story, ctx)`` in ``reports/synthetic-data/2026-10-15-showcase-proofs/prove.py``.
    """
    return normalize(_DIRECT_ROWS_BY_STORY[story](ctx))


def _line_position_lookup(ctx: PatientClaimContext | None) -> dict[str, str]:
    if ctx is None:
        return {}
    lookup: dict[str, str] = {}
    for idx, p in enumerate(ctx.procedure_lines, start=1):
        lookup[p.procedure_line_id] = f"procedure_claim_lines:{idx}"
    for idx, m in enumerate(ctx.material_lines, start=1):
        lookup[m.material_line_id] = f"material_claim_lines:{idx}"
    for idx, d in enumerate(ctx.drug_lines, start=1):
        lookup[d.drug_claim_line_id] = f"drug_claim_lines:{idx}"
    for idx, pf in enumerate(ctx.performed_procedure_lines, start=1):
        lookup[pf.performed_line_id] = f"performed_procedure_lines:{idx}"
    return lookup


def _canonicalize_token(token: Any, lookup: Mapping[str, str]) -> Any:
    if not isinstance(token, str) or not token:
        return token
    if token in lookup:
        return lookup[token]
    if PROCEDURE_LINE_ID_RE.fullmatch(token):
        return f"procedure_claim_lines:{int(token.rsplit('-', 1)[-1])}"
    if MATERIAL_LINE_ID_RE.fullmatch(token):
        return f"material_claim_lines:{int(token.rsplit('-', 1)[-1])}"
    if DRUG_CLAIM_LINE_ID_RE.fullmatch(token):
        return f"drug_claim_lines:{int(token.rsplit('-', 1)[-1])}"
    if PERFORMED_LINE_ID_RE.fullmatch(token):
        return f"performed_procedure_lines:{int(token.rsplit('-', 1)[-1])}"
    for pattern, table in (
        (_PROOF_PROC_ID_RE, "procedure_claim_lines"),
        (_PROOF_MAT_ID_RE, "material_claim_lines"),
        (_PROOF_DRUG_ID_RE, "drug_claim_lines"),
        (_PROOF_PERF_ID_RE, "performed_procedure_lines"),
    ):
        match = pattern.fullmatch(token)
        if match:
            return f"{table}:{int(match.group(1))}"
    return token


def canonicalize_signal_tuple(
    sig: Sequence[Any],
    ctx: PatientClaimContext | None = None,
    *,
    claim_id: str | None = None,
    patient_id: str | None = None,
) -> tuple[Any, ...]:
    """Normalize a signal tuple, canonicalize line IDs, and canonicalize free-text claim/patient IDs."""
    norm = normalize(list(sig))
    lookup = _line_position_lookup(ctx)
    if not norm:
        return ()
    line_canon = (*(_canonicalize_token(item, lookup) for item in norm[:-1]), norm[-1])
    resolved_claim_id = claim_id or (
        ctx.claims[0].claim_id if ctx is not None and ctx.claims else None
    )
    resolved_patient_id = patient_id or (ctx.patient_id if ctx is not None else None)
    return canonicalize_text(line_canon, resolved_claim_id, resolved_patient_id)


def signal_counter(
    signals: Iterable[Sequence[Any]],
    ctx: PatientClaimContext | None = None,
    *,
    claim_id: str | None = None,
    patient_id: str | None = None,
) -> Counter[tuple[Any, ...]]:
    """Build a ``Counter`` of normalized, line-position and text-ID canonicalized signal tuples."""
    return Counter(
        canonicalize_signal_tuple(sig, ctx, claim_id=claim_id, patient_id=patient_id)
        for sig in signals
    )


def report_scalars(rep: Any) -> dict[str, Any]:
    """Extract the 5 report scalar values used by ``results/S<n>.json``."""
    return normalize({k: getattr(rep, k) for k in REPORT_SCALAR_KEYS})


def context_total_billed(ctx: PatientClaimContext) -> str:
    """Sum ``billed_amount_try`` across procedure, material and drug lines in ``ctx``."""
    total = (
        sum((p.billed_amount_try for p in ctx.procedure_lines), _ZERO)
        + sum((m.billed_amount_try for m in ctx.material_lines), _ZERO)
        + sum((d.billed_amount_try for d in ctx.drug_lines), _ZERO)
    )
    return f"{money(total):.2f}"


def target_signal_found(
    story: str,
    amount_try: str | float | Decimal,
    only_in_faulty: Iterable[Sequence[Any]],
) -> bool:
    """Return True if the expected fault signal (or a documented divergence amount) is in ``F - C``."""
    signals = list(only_in_faulty)
    expected_amt = _f(amount_try)
    if expected_amt > 0.0:
        if any(len(sig) > 0 and _f(sig[-1]) == expected_amt for sig in signals):
            return True
        divergence = KNOWN_REPORT_DIVERGENCES.get(story)
        if divergence is not None:
            div_amt = _f(divergence.report_amount_try)
            return any(len(sig) > 0 and _f(sig[-1]) == div_amt for sig in signals)
        return False
    if story == "S6":
        return any("drug_indication" in sig for sig in signals)
    return bool(signals)


def load_proof_json(story: str, results_dir: Path = PROOFS_RESULTS_DIR) -> dict[str, Any]:
    """Read ``results/<story>.json`` from the showcase proofs directory."""
    return json.loads((results_dir / f"{story}.json").read_text(encoding="utf-8"))


def prove_story(
    story: str,
    *,
    record: FaultInjectionRecord,
    faulty_ctx: PatientClaimContext,
    clean_ctx: PatientClaimContext,
    proof: Mapping[str, Any] | None = None,
) -> StoryProof:
    """Run the engine and target detectors on ``faulty_ctx`` and ``clean_ctx`` and compare with ``proof``."""
    proof_data = proof if proof is not None else load_proof_json(story)
    cid, pid = record.claim_id, record.patient_id

    f_rep, f_viol = run_engine(faulty_ctx)
    c_rep, c_viol = run_engine(clean_ctx)

    f_sigs = tuple(
        canonicalize_signal_tuple(s, faulty_ctx, claim_id=cid, patient_id=pid)
        for s in ui_signals(f_rep, f_viol)
    )
    c_sigs = tuple(
        canonicalize_signal_tuple(s, clean_ctx, claim_id=cid, patient_id=pid)
        for s in ui_signals(c_rep, c_viol)
    )

    f_counter: Counter[tuple[Any, ...]] = Counter(f_sigs)
    c_counter: Counter[tuple[Any, ...]] = Counter(c_sigs)

    only_f_counter = f_counter - c_counter
    only_c_counter = c_counter - f_counter

    only_in_faulty = tuple(only_f_counter.elements())
    only_in_clean = tuple(only_c_counter.elements())

    direct_faulty = canonicalize_text(direct_rows(story, faulty_ctx), cid, pid)
    direct_clean = canonicalize_text(direct_rows(story, clean_ctx), cid, pid)

    exp_noise = signal_counter(proof_data["noise_in_clean"], claim_id=cid, patient_id=pid)
    exp_only_f = signal_counter(proof_data["only_in_faulty"], claim_id=cid, patient_id=pid)
    exp_only_c = signal_counter(proof_data["only_in_clean"], claim_id=cid, patient_id=pid)

    mismatches: list[str] = []
    f_total = context_total_billed(faulty_ctx)
    exp_f_total = str(proof_data["faulty"]["total_billed"])
    if f_total != exp_f_total:
        mismatches.append(f"{story} faulty.total_billed: expected {exp_f_total!r}, got {f_total!r}")

    c_total = context_total_billed(clean_ctx)
    exp_c_total = str(proof_data["clean"]["total_billed"])
    if c_total != exp_c_total:
        mismatches.append(f"{story} clean.total_billed: expected {exp_c_total!r}, got {c_total!r}")

    if c_counter != exp_noise:
        mismatches.append(
            f"{story} noise_in_clean: expected {dict(exp_noise)!r}, got {dict(c_counter)!r}"
        )
    if only_f_counter != exp_only_f:
        mismatches.append(
            f"{story} only_in_faulty: expected {dict(exp_only_f)!r}, got {dict(only_f_counter)!r}"
        )
    if only_c_counter != exp_only_c:
        mismatches.append(
            f"{story} only_in_clean: expected {dict(exp_only_c)!r}, got {dict(only_c_counter)!r}"
        )

    exp_direct_f = canonicalize_text(normalize(proof_data["faulty"]["direct"]), cid, pid)
    if direct_faulty != exp_direct_f:
        mismatches.append(
            f"{story} faulty.direct: expected {exp_direct_f!r}, got {direct_faulty!r}"
        )

    exp_direct_c = canonicalize_text(normalize(proof_data["clean"]["direct"]), cid, pid)
    if direct_clean != exp_direct_c:
        mismatches.append(f"{story} clean.direct: expected {exp_direct_c!r}, got {direct_clean!r}")

    got_rep_f = report_scalars(f_rep)
    exp_rep_f = normalize(proof_data["faulty"]["report"])
    if got_rep_f != exp_rep_f:
        mismatches.append(f"{story} faulty.report: expected {exp_rep_f!r}, got {got_rep_f!r}")

    got_rep_c = report_scalars(c_rep)
    exp_rep_c = normalize(proof_data["clean"]["report"])
    if got_rep_c != exp_rep_c:
        mismatches.append(f"{story} clean.report: expected {exp_rep_c!r}, got {got_rep_c!r}")

    divergence = KNOWN_REPORT_DIVERGENCES.get(story)
    note = (
        f"report={divergence.report_amount_try} vs record={divergence.record_amount_try} "
        f"({divergence.issue}): {divergence.reason}"
        if divergence is not None
        else ""
    )

    return StoryProof(
        story=story,
        patient_id=record.patient_id,
        claim_id=record.claim_id,
        fault_id=record.fault_id,
        amount_try=record.amount_try,
        faulty_signals=f_sigs,
        clean_signals=c_sigs,
        only_in_faulty=only_in_faulty,
        only_in_clean=only_in_clean,
        direct_faulty=direct_faulty,
        direct_clean=direct_clean,
        mismatches=tuple(mismatches),
        note=note,
    )


def prove_showcase(
    build_result: BuildResult | None = None,
    *,
    dataset: SUTClaimDataset | None = None,
) -> tuple[StoryProof, ...]:
    """Prove every showcase story by loading the faulty claims from disk and clean twins in memory."""
    built = build_result if build_result is not None else build_showcase()
    loaded = dataset if dataset is not None else load_showcase_dataset()

    clean_by_claim = {c.header.claim_id: c for c in built.clean_claims}
    proofs: list[StoryProof] = []
    for rec in built.records:
        story = rec.story
        if story is None:
            raise BuildError(f"record {rec.injection_id} is missing a showcase story identifier")
        faulty_ctx = build_patient_claim_context(rec.patient_id, loaded)
        if faulty_ctx is None:
            raise BuildError(f"patient {rec.patient_id} not found in loaded showcase dataset")
        clean_claim = clean_by_claim.get(rec.claim_id)
        if clean_claim is None:
            raise BuildError(f"clean twin for claim {rec.claim_id} not found in build_result")
        clean_ctx = context_from_composed(clean_claim)
        proofs.append(
            prove_story(
                story,
                record=rec,
                faulty_ctx=faulty_ctx,
                clean_ctx=clean_ctx,
            )
        )
    return tuple(proofs)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m scripts.synthetic.cohort.engine_proof``."""
    _ = argv
    proofs = prove_showcase()
    for sp in proofs:
        found = target_signal_found(sp.story, sp.amount_try, sp.only_in_faulty)
        line = (
            f"{sp.story}  {sp.fault_id}  amount={sp.amount_try}  "
            f"found={found}  mismatches={len(sp.mismatches)}"
        )
        if sp.note:
            line = f"{line}  note: {sp.note}"
        print(line)
        for mismatch in sp.mismatches:
            print(f"  MISMATCH: {mismatch}", file=sys.stderr)
    return 1 if any(sp.mismatches for sp in proofs) else 0


if __name__ == "__main__":
    raise SystemExit(main())
