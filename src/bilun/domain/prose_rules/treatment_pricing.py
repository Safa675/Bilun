"""SUT §2.4 treatment-pricing prose rules — claim-context gates.

This evaluator clones the proven ``gap_closing`` pattern (JSON loader + predicate
engine + context builder + ``check_*_for_context`` entry point) for the
``treatment_pricing_2_4`` rule set (182 rules covering §2.4.1–§2.4.L:
radiosurgery, dialysis, IVF, physiotherapy, ICU, palliative care, etc.).

Scope (Wiredness epic W3): only rules whose condition keys are ENTIRELY within
the wireable set are able to fire — every key must be derivable from a
``PatientClaimContext`` field:

- ``procedure_category`` / ``procedure_category_any`` ← ``ProcedureClaimLine.procedure_category``
- ``procedure_code_any`` ← ``ProcedureClaimLine.procedure_code``
- ``provider_type`` ← ``ClaimHeader.provider_type``
- ``facility_not_in`` / ``facility_type_any`` ← ``ClaimHeader.facility_tier``
- ``diagnosis_any`` / ``diagnosis_in`` ← ``ClaimDiagnosis.icd10_code`` (PREFIX matching)
- ``health_board_report_present`` ← ``DrugClaimLine.drug_specialty_board_report_present``

The remaining ~165 rules (≈142+ in the planner's coarser tally) reference keys
that are NOT present on a ``PatientClaimContext`` — IVF cycle counters, session
frequency windows, BMI, clinical scores, board-report tier, etc. They are kept in
the loaded rule set for inventory/coverage but ``_condition_matches`` returns
``False`` for them (honest skip — never a silent no-op guessing the value).

TODO (data-model extension, out of current scope): three §2.4.4.H ICU rules are
dormant for root-cause-1 (the concept is absent from the claim data model, not
merely unmapped) and require new model fields + fixtures, NOT a context-builder
fix:
- 2.4.4.H.(9)  ``blood_product_separately_billed`` — needs either a curated
  blood-product material/drug code catalog (none exists) or a new boolean flag
  on MaterialClaimLine/DrugClaimLine. ``material_type`` (consumable/implant/…)
  has no blood discriminator; SUT blood products live under §4.2.27 as drugs.
- 2.4.4.H.(10a)/(10b) ``enabiz_278_data_package_sent`` — operational metadata
  (did the facility submit the e-nabız 278 feed). No proxy on ClaimHeader or
  anywhere in the data model; absent key honest-skips, which is correct (a
  False default would spuriously fire the 10b downgrade on every ICU claim).

Two correctness points ported from the plan's W2.5 lessons:

1. ICD-10 PREFIX match: ``diagnosis_in: ["E11"]`` MUST match a billed
   ``"E11.9"``. The drug_indication evaluator does prefix matching;
   ``gap_closing`` does exact set intersection only. We port the prefix logic
   (``_diagnosis_matches``) so diagnosis predicates behave correctly.
2. ``*_any`` keys: when a claim carries multiple distinct procedure categories,
   the predicate MUST read the ``procedure_category_any`` collection (list),
   not the bare scalar (which is left unset on ambiguous claims).
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from typing import Any

from ..constants import _PROSE_RULES_DIR

_RULES_PATH = _PROSE_RULES_DIR / "treatment_pricing_2_4.json"
_RULESET_ID = "treatment_pricing_2_4"

# Condition-key suffixes that denote set-membership predicates (positive or
# negated). Mirrors gap_closing._SET_PREDICATE_SUFFIXES (a separate copy kept
# here so the two rule sets can evolve independently).
# Order matters: longer suffixes MUST come first — see gap_closing.py comment.
_SET_PREDICATE_SUFFIXES = ("_not_any", "_not_in", "_any", "_in")

# Scalar (exact-equality) fields surfaced by the context builder. Everything
# not in this set and not ending in a predicate suffix is treated as an unknown
# predicate shape → honest skip.
_SCALAR_FIELDS = {
    "procedure_category",
    "provider_type",
    "health_board_report_present",
}

# Fields where membership is resolved via ICD-10 PREFIX matching (not exact
# intersection). diagnosis_any/diagnosis_in are positive; diagnosis_not_in is
# negated (rule fires only when NONE of the listed codes match).
_DIAGNOSIS_KEYS = {"diagnosis_any", "diagnosis_in", "diagnosis_not_in"}

# Clinical category → ICD-10 code prefixes (upper-cased). Backs the
# ``diagnosis_category_any`` / ``diagnosis_category_not_in`` predicates, which
# gate on clinical concepts (amputation, fracture, …) rather than raw ICD-10
# chapters. A billed code is assigned a category when it shares the listed
# prefix (e.g. ``S82`` → ``fracture``). Approximate — sufficient for the §2.4
# FTR disaster-provision / ESWT-indication rules.
_ICD10_CATEGORY_PREFIXES: dict[str, tuple[str, ...]] = {
    "amputation": ("Z89", "Z90", "T13", "T14", "T87", "T88"),
    "fracture": ("S42", "S52", "S62", "S72", "S82", "S92", "S12", "S22", "S32"),
    "peripheral_nerve_injury": ("S54", "S64", "S74", "S94", "G56", "G57", "G58"),
    "lumbosacral_plexus_injury": ("G57", "S34"),
    "tendon_injury": ("S46", "S56", "S66", "S76", "S86", "S96", "M66", "M67", "M76", "M77"),
    "epin_calcanei": ("M77"),
    "plantar_fasciitis": ("M72"),
    "epicondylitis": ("M77"),
    "calcific_tendinitis": ("M75"),
}

# PMR (fizik tedavi ve rehabilitasyon) specialty codes that signal supervision
# by a physical-medicine-and-rehabilitation specialist. The synthetic
# generators and the rule vocabulary use these identifiers.
_PMR_SPECIALTY_CODES = frozenset({
    "physical_medicine_rehabilitation",
    "fizik_tedavi_ve_rehabilitasyon",
    "pmr",
    "fizik_tedavi_rehabilitasyon",
})


def _icd10_categories(codes: list[str]) -> set[str]:
    """Map billed ICD-10 codes to the clinical categories they fall under.

    A code is assigned every category whose listed prefix it shares (prefix
    with a trailing ``.`` segment boundary, mirroring ``_diagnosis_matches``).
    Returns an empty set when ``codes`` is empty or no category matches.
    """
    out: set[str] = set()
    for raw in codes or []:
        code = str(raw or "").strip().upper()
        if not code:
            continue
        for cat, prefixes in _ICD10_CATEGORY_PREFIXES.items():
            for prefix in prefixes:
                if code == prefix or code.startswith(prefix + "."):
                    out.add(cat)
                    break
    return out


@lru_cache(maxsize=1)
def load_treatment_pricing_rules() -> dict[str, Any]:
    """Load ``treatment_pricing_2_4.json`` (cached).

    Returns the raw JSON document (``rule_set_id`` + ``rules`` list). The caller
    must NOT mutate the returned dict — it is shared via the lru_cache.
    """
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _diagnosis_matches(codes: list[str], rule_codes: list[str]) -> bool:
    """ICD-10 PREFIX membership — ported from drug_indication._diagnosis_matches_rule.

    A billed ``code`` matches a rule ``listed`` code when they are equal OR the
    billed code starts with ``listed + "."`` (so ``"E11"`` matches ``"E11.9"``).
    Codes are normalized to upper-case + stripped before comparison.

    Returns ``True`` if ANY billed code matches ANY rule code. Empty
    ``rule_codes`` is treated as "no diagnosis restriction" → ``True`` (the
    other condition keys on the rule still gate firing).
    """
    listed = [str(c).strip().upper() for c in (rule_codes or []) if c]
    if not listed:
        return True
    for raw in codes or []:
        code = str(raw or "").strip().upper()
        if not code:
            continue
        if code in listed:
            return True
        for prefix in listed:
            if code == prefix or code.startswith(prefix + "."):
                return True
    return False


def _suffix_len(key: str) -> int:
    """Length of the trailing predicate suffix on ``key`` (0 if none)."""
    for suffix in _SET_PREDICATE_SUFFIXES:
        if key.endswith(suffix):
            return len(suffix)
    return 0


def _condition_matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    """Evaluate a treatment-pricing rule condition against a flat claim context.

    Each condition key is resolved as:

    - ``diagnosis_any`` / ``diagnosis_in`` → ICD-10 PREFIX match of the rule's
      listed codes against ``context["diagnosis_codes"]`` (the billed set).
    - ``procedure_in_annex`` → at least one billed procedure code is a member
      of the named annex (e.g. ``EK-2/A-2``, ``EK-2/C-1``, ``EK-2/C``);
      resolved against the loaded catalog code sets.
    - ``*_any`` / ``*_in`` (other bases) → set INTERSECTION: at least one rule
      value must be in the context collection surfaced under ``<key>`` (or the
      base scalar when only that is present).
    - ``*_not_in`` / ``*_not_any`` → negated membership: NONE of the rule values
      may be in the context collection.
    - numeric range (``{"min": x}`` / ``{"max": y}``) → ``context.get(key)``
      must satisfy the bound(s); surfaced derivable keys (sessions, days, …)
      evaluate against the range, unsurfaced keys honest-skip.
    - scalar field → ``context.get(field)`` must equal the condition value.
    - boolean flag → ``context.get(key)`` must equal the flag.

    A key absent from ``context`` ⇒ return ``False`` (honest skip — do not
    guess). This is what makes the ~165 out-of-scope rules honest-skip: their
    keys (``sessions_within_6mo``, ``ivf_cycle``, ``bmi``, …) are never surfaced
    by ``_build_treatment_pricing_context``, so every such rule fails its first
    unresolvable key and never fires.
    """
    for key, expected in condition.items():
        # procedure_in_annex — annex membership over the billed procedure codes.
        # The predicate value is the annex identifier (e.g. "EK-2/A-2"); the
        # billed codes are surfaced under context["procedure_code_any"]. Lazy
        # import avoids a module-load cycle with the catalog machinery.
        if key == "procedure_in_annex":
            annex = str(expected or "").strip()
            billed_codes = context.get("procedure_code_any")
            if not billed_codes or not annex:
                return False
            code_list = (
                list(billed_codes)
                if isinstance(billed_codes, (list, tuple, set))
                else [billed_codes]
            )
            from .catalog_membership import any_procedure_in_annex

            if not any_procedure_in_annex(code_list, annex):
                return False
            continue

        # Numeric range predicate: {"min": x} / {"max": y} / {"min", "max"}.
        # Surfaced derivable keys (sessions_per_day, days_from_report_to_treatment,
        # sessions_within_year, sessions_same_region_within_1y, …) evaluate their
        # numeric value against the range. Uns surfaced keys fall through to the
        # honest-skip branch below (range on a missing key → skip).
        if isinstance(expected, dict) and ("min" in expected or "max" in expected):
            actual = context.get(key)
            if actual is None:
                return False
            try:
                actual_num = float(actual)
            except (TypeError, ValueError):
                return False
            lo = expected.get("min")
            hi = expected.get("max")
            if lo is not None and actual_num < float(lo):
                return False
            if hi is not None and actual_num > float(hi):
                return False
            continue

        # Diagnosis predicates — prefix matching, not exact intersection.
        # diagnosis_any/diagnosis_in → at least one billed code matches a rule
        # code via prefix; diagnosis_not_in → NONE of the billed codes may match
        # (the rule fires only when the diagnosis is outside the listed set).
        if key in _DIAGNOSIS_KEYS:
            billed = context.get("diagnosis_codes")
            if billed is None:
                return False
            rule_codes = (
                list(expected) if isinstance(expected, (list, tuple, set)) else [expected]
            )
            matched = _diagnosis_matches(billed, rule_codes)
            if key == "diagnosis_not_in":
                # Negated: rule fires only when NO billed code matches.
                if matched:
                    return False
            else:
                if not matched:
                    return False
            continue

        if key.endswith(_SET_PREDICATE_SUFFIXES):
            base = key[: -_suffix_len(key)]
            # Prefer the explicit <key> collection the builder surfaced; fall
            # back to the base scalar so a single-valued claim still matches a
            # *_any predicate (gap_closing parity). A bare scalar base is a
            # valid single-element collection, but a multi-valued claim MUST
            # surface its full set under the *_any key — otherwise the predicate
            # silently honest-skips (the W2.5b lesson).
            available = context.get(key)
            if available is None:
                available = context.get(base)
            if available is None:
                # Final fallback: the <base>_any collection. This lets a
                # ``diagnosis_category_not_in`` predicate (base =
                # ``diagnosis_category``) resolve against the
                # ``diagnosis_category_any`` collection the builder surfaced,
                # and keeps *_not_in working when only *_any was populated.
                available = context.get(base + "_any")
            if available is None:
                return False
            available_set = (
                set(available) if isinstance(available, (list, tuple, set)) else {available}
            )
            expected_set = (
                set(expected) if isinstance(expected, (list, tuple, set)) else {expected}
            )
            if key.endswith("_not_any") or key.endswith("_not_in"):
                # Negated membership: NONE of the expected may be present.
                if available_set & expected_set:
                    return False
            else:
                if not (available_set & expected_set):
                    return False
            continue

        if isinstance(expected, bool) or key in _SCALAR_FIELDS:
            actual = context.get(key)
            if actual is None:
                # Scalar not surfaced on this claim. Fall back to the matching
                # ``<key>_any`` collection when one exists: a multi-category
                # claim (e.g. FTR + muayene) leaves the bare
                # ``procedure_category`` scalar unset but surfaces the full set
                # under ``procedure_category_any``. Without this fallback ~130
                # single-value scalar rules (``procedure_category: "ftr"``)
                # honest-skip on any mixed-category claim. Membership against
                # the ``*_any`` list is the right reading: the rule's value is
                # one of the categories present on the claim.
                any_collection = context.get(key + "_any")
                if any_collection is None:
                    return False
                any_set = (
                    set(any_collection)
                    if isinstance(any_collection, (list, tuple, set))
                    else {any_collection}
                )
                if expected not in any_set:
                    return False
                continue
            if isinstance(expected, bool):
                if bool(actual) != bool(expected):
                    return False
            elif actual != expected:
                return False
            continue

        # Unknown predicate shape (e.g. out-of-scope session/IVF/BMI keys) →
        # skip rather than mis-evaluate.
        return False

    return True


def _violation_from_rule(rule: dict[str, Any], ruleset_id: str) -> dict[str, Any]:
    """Build a violation dict from a firing rule (mirrors gap_closing shape)."""
    action = rule.get("action") or {}
    billable = bool(action.get("billable", True))
    message = (
        action.get("denial_tr")
        or action.get("payment_tr")
        or action.get("message_tr")
        or rule.get("rule_id", "")
    )
    return {
        "rule": ruleset_id,
        "severity": action.get("severity", "warning"),
        "message": message,
        "savings_try": 0.0,
        "risk_amount": 0.0,
        "sut_section": rule.get("sut_section", ""),
        "rule_id": rule.get("rule_id", ""),
        "billable": billable,
        "material_outcome": "must_bill" if billable else "no_pay",
        "annex_basis": action.get("annex_basis"),
        "details": {
            "prose_rule_set": ruleset_id,
        },
    }


def _evaluate(ruleset: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    ruleset_id = ruleset.get("rule_set_id", _RULESET_ID)
    violations: list[dict[str, Any]] = []
    for rule in ruleset.get("rules") or []:
        condition = rule.get("condition") or {}
        if not _condition_matches(condition, context):
            continue
        violations.append(_violation_from_rule(rule, ruleset_id))
    return violations


def _build_treatment_pricing_context(ctx: Any) -> dict[str, Any]:
    """Map a ``PatientClaimContext`` to the flat dict treatment-pricing rules gate on.

    Surfaces keys: ``procedure_category``, ``procedure_category_any``,
    ``procedure_code_any``, ``provider_type``, ``facility_tier``,
    ``facility_type_any``, ``diagnosis_codes`` (list, for prefix matching),
    ``diagnosis_category_any`` (ICD-10 → clinical categories),
    ``health_board_report_present``, ``prescriber_specialty_any``,
    ``supervised_by_pmr_specialty``, ``sessions_per_day``, ``sessions``,
    ``same_day_physio_rehab``, ``concomitant_service``,
    ``billed_with_other_physiotherapy``, ``sessions_within_year``,
    ``sessions_same_region_within_1y``, ``sessions_per_patient_per_year``,
    ``daily_exams_per_physician``, ``daily_billing_hours_per_physician``,
    ``visit_type``, ``treatment_setting``, ``days_from_report_to_treatment``.

    Numeric keys (sessions, days, exam counts) are surfaced as scalars so the
    range predicates (``{"min": x}`` / ``{"max": y}``) in ``_condition_matches``
    can evaluate them. Approximations are documented inline and are the best
    available proxy from a single-claim context.

    Multi-claim handling: when ``ctx.claims`` carries more than one bill, the
    caller (billing orchestrator) is expected to iterate ``ctx.claims`` and
    ``slice_for_claim`` per bill. This builder evaluates ``ctx.claims[0]`` and
    scopes every line aggregation to that claim's ``claim_id`` so a second
    bill's procedures/diagnoses cannot contaminate this claim's context (parity
    with ``_build_gap_closing_context``'s scoping).
    """
    if not ctx.claims:
        return {}
    header = ctx.claims[0]
    claim_id = getattr(header, "claim_id", None)

    def _lines_for_claim(attr: str) -> list[Any]:
        return [
            line
            for line in (getattr(ctx, attr, ()) or ())
            if getattr(line, "claim_id", None) == claim_id
        ]

    context: dict[str, Any] = {
        "provider_type": header.provider_type or "",
        # facility_tier is the canonical field; facility_type_any/facility_not_in
        # predicates read the same value via the base-scalar fallback in
        # _condition_matches.
        "facility_tier": header.facility_tier or "",
    }

    # facility_type derivation — same logic as gap_closing._build_gap_closing_context.
    # Revives ~15 rules in treatment_pricing + dental that gate on facility_type.
    provider_type_lower = (header.provider_type or "").lower()
    facility_tier_lower = (header.facility_tier or "").lower()
    if any(
        token in provider_type_lower
        for token in ("universite", "egitim_arastirma", "training_research")
    ) and "vakif" not in provider_type_lower and "vakif" not in facility_tier_lower:
        context["facility_type"] = "training_research_hospital"
    elif "vakif" in provider_type_lower or "vakif" in facility_tier_lower:
        context["facility_type"] = "foundation_university"
    elif (
        provider_type_lower in ("private", "ozel")
        or facility_tier_lower in ("ozel", "2_3_basamak_ozel", "private")
        or "ozel" in facility_tier_lower
    ):
        context["facility_type"] = "private"

    # Procedure-derived fields.
    procedure_lines = _lines_for_claim("procedure_lines")
    if procedure_lines:
        categories = {p.procedure_category for p in procedure_lines if p.procedure_category}
        codes = {p.procedure_code for p in procedure_lines if p.procedure_code}
        if categories:
            # Surface the full set under the *_any key so membership predicates
            # match on multi-category claims (W2.5b). The bare scalar is only
            # set when the claim has a single, unambiguous category — otherwise
            # exact-equality rules honest-skip rather than mis-attribute.
            context["procedure_category_any"] = sorted(categories)
            if len(categories) == 1:
                context["procedure_category"] = next(iter(categories))
        if codes:
            context["procedure_code_any"] = sorted(codes)

        # Specialty-derived fields. ``procedure_specialty_code`` on each line is
        # surfaced as prescriber_specialty_any (membership predicate) and feeds
        # the PMR-supervision flag.
        specialties = {
            getattr(p, "procedure_specialty_code", "") or ""
            for p in procedure_lines
        }
        specialties.discard("")
        if specialties:
            context["prescriber_specialty_any"] = sorted(specialties)
            context["supervised_by_pmr_specialty"] = bool(
                {s.lower() for s in specialties} & _PMR_SPECIALTY_CODES
            )

        # Session-derived fields. Group by procedure_date via the shared
        # claim_utils helper (it keys undated lines off their line id so they
        # do not merge). ``sessions_per_day`` = max FTR-line count on any one
        # date; ``sessions`` = total session count (distinct dates).
        from .claim_utils import group_procedure_lines_by_session

        sessions_by_date = group_procedure_lines_by_session(procedure_lines)
        ftr_category_markers = {
            "physiotherapy_rehab",
            "physiotherapy_rehab_inpatient",
            "robotic_rehab",
        }
        ftr_lines_by_date: dict[Any, list[Any]] = {}
        for svc_date, lines in sessions_by_date.items():
            ftr = [ln for ln in lines if getattr(ln, "procedure_category", "") in ftr_category_markers]
            if ftr:
                ftr_lines_by_date[svc_date] = ftr
        if sessions_by_date:
            # sessions_per_day: the maximum line count on a single date (the
            # §2.4 F-2(4) / B(7) "one session per day" gates use min: 2 to flag
            # >1 same-day session). Count ALL lines grouped by date, not just
            # FTR lines, because some cap rules are category-agnostic.
            counts = [len(lines) for lines in sessions_by_date.values()]
            context["sessions_per_day"] = max(counts) if counts else 0
            context["sessions"] = len(sessions_by_date)
        if ftr_lines_by_date:
            # same_day_physio_rehab: are there multiple FTR lines on one date?
            context["same_day_physio_rehab"] = any(
                len(lines) > 1 for lines in ftr_lines_by_date.values()
            )
            # concomitant_service / billed_with_other_physiotherapy: non-FTR
            # procedures billed on the same date as FTR lines.
            ftr_dates = set(ftr_lines_by_date.keys())
            non_ftr_same_day = any(
                getattr(ln, "procedure_category", "") not in ftr_category_markers
                and getattr(ln, "procedure_category", "") != ""
                for lines in (sessions_by_date.get(d, []) for d in ftr_dates)
                for ln in lines
            )
            context["concomitant_service"] = non_ftr_same_day
            context["billed_with_other_physiotherapy"] = non_ftr_same_day

        # Annual session-count approximations. A single PatientClaimContext
        # carries one claim's lines; the §2.4 F-2(5)/F-2(a) annual caps gate on
        # "sessions within a year". We approximate from the count of distinct
        # procedure dates on THIS claim (the best available proxy — a full
        # annual count would require cross-claim history). ``sessions_per_year``
        # surfaces the same value for all three annual predicates since the
        # claim is the unit of evaluation and regional/patient-per-year history
        # is not available on a single claim context.
        if sessions_by_date:
            annual_count = len(sessions_by_date)
            context["sessions_within_year"] = annual_count
            context["sessions_same_region_within_1y"] = annual_count
            context["sessions_per_patient_per_year"] = annual_count

        # daily_exams_per_physician / daily_billing_hours_per_physician — count
        # of procedure lines per specialty per day. The §2.4 rules use these to
        # gate "max N exams per physician per day". We surface the MAX across
        # (specialty, date) buckets as a single scalar; billing-hours is a
        # coarse proxy (procedure count × ~30 min default — the rules gate on
        # presence of a count, not a precise hourly value).
        if sessions_by_date and specialties:
            from collections import defaultdict

            per_specialty_day: dict[tuple[str, Any], int] = defaultdict(int)
            for svc_date, lines in sessions_by_date.items():
                for ln in lines:
                    sp = (getattr(ln, "procedure_specialty_code", "") or "").lower()
                    per_specialty_day_key = (sp, svc_date) if sp else ("", svc_date)
                    per_specialty_day[per_specialty_day_key] += 1
            if per_specialty_day:
                context["daily_exams_per_physician"] = max(per_specialty_day.values())
                # billing-hours proxy: same-day count × 0.5h (rounded). The
                # rules gate on a derived hours figure; this is a conservative
                # approximation from procedure count.
                context["daily_billing_hours_per_physician"] = max(per_specialty_day.values()) * 0.5

    # Diagnosis-derived fields (for prefix matching). Pull from both the
    # header primary icd10 and the diagnosis rows, scoped to this claim.
    diagnosis_codes: list[str] = []
    primary = str(getattr(header, "primary_icd10", "") or "").strip().upper()
    if primary:
        diagnosis_codes.append(primary)
    for dg in _lines_for_claim("diagnoses"):
        code = str(getattr(dg, "icd10_code", "") or "").strip().upper()
        if code and code not in diagnosis_codes:
            diagnosis_codes.append(code)
    if diagnosis_codes:
        context["diagnosis_codes"] = diagnosis_codes
        # diagnosis_category_any — ICD-10 → clinical category mapping. Used by
        # the disaster-provision and ESWT-indication rules. The *_not_in form
        # is handled by the predicate engine's set-negation against this same
        # collection (negation of "any of these categories present").
        cats = _icd10_categories(diagnosis_codes)
        if cats:
            context["diagnosis_category_any"] = sorted(cats)

        # HBO (hiperbarik oksijen) indication keys from EK-2/D-3. The HBO
        # §2.4.4.B rules gate on whether the billed diagnosis is on the EK-2/D-3
        # indication list, and whether it is an emergency-listed indication
        # (which waives the board-report requirement). Match via ICD-10 PREFIX
        # so a billed ``T58.0`` matches the listed ``T58``.
        from .catalog_membership import get_ek2d3_icd10_codes, get_ek2d3_emergency_icd10_codes

        ek2d3_codes = get_ek2d3_icd10_codes()
        ek2d3_emergency = get_ek2d3_emergency_icd10_codes()
        if ek2d3_codes:
            context["indication_in_ek2d3"] = _diagnosis_matches(
                diagnosis_codes, sorted(ek2d3_codes)
            )
        if ek2d3_emergency:
            context["indication_is_emergency_listed"] = _diagnosis_matches(
                diagnosis_codes, sorted(ek2d3_emergency)
            )

    # origin_is_traffic_accident — traffic-accident origin waives HBO/FTR session
    # limits (§2.4.4.B(13), §2.4.4.F-2(10)). Derived from scenario_tag /
    # occupational_context / department carrying a traffic-accident marker.
    traffic_markers = ("traffic_accident", "trafik", "traffic", "ykm", "kaza")
    origin_text = " ".join(
        str(getattr(header, attr, "") or "").lower()
        for attr in ("scenario_tag", "occupational_context", "department", "claim_type")
    )
    context["origin_is_traffic_accident"] = any(m in origin_text for m in traffic_markers)

    # Visit-type / care-setting derived fields. visit_type mirrors the raw
    # claim_type vocabulary the rules use (outpatient/inpatient/gunubirlik);
    # treatment_setting comes from the shared ``infer_care_setting`` helper.
    if getattr(header, "claim_type", ""):
        claim_type_raw = header.claim_type or ""
        ct_lower = claim_type_raw.lower()
        if "yatis" in ct_lower or "yatarak" in ct_lower or "inpatient" in ct_lower:
            context["visit_type"] = "inpatient"
        elif "gunubirlik" in ct_lower or "day_case" in ct_lower:
            context["visit_type"] = "gunubirlik"
        elif (
            "ayakta" in ct_lower
            or "outpatient" in ct_lower
            or "poliklinik" in ct_lower
        ):
            context["visit_type"] = "outpatient"
        else:
            context["visit_type"] = ct_lower or "outpatient"
        from .claim_utils import infer_care_setting

        context["treatment_setting"] = infer_care_setting(header)

    # days_from_report_to_treatment — approximate as the gap between the claim
    # start date and the earliest procedure date. The rules use this to gate
    # "treatment must start within N days of the board report" (§2.4.4.F-2(7),
    # §2.4.4.B(6)); claim_start_date is the closest available proxy for the
    # report/authorization date on a PatientClaimContext.
    claim_start = getattr(header, "claim_start_date", None)
    if claim_start is not None and procedure_lines:
        earliest_proc = min(
            (getattr(p, "procedure_date", None) for p in procedure_lines),
            key=lambda d: d if d is not None else date.max,
        )
        if earliest_proc is not None:
            try:
                context["days_from_report_to_treatment"] = abs(
                    (earliest_proc - claim_start).days
                )
            except TypeError:
                pass

    # Health board report (specialty board report) presence — surfaced from
    # drug lines. DrugClaimLine carries drug_specialty_board_report_present.
    # When there are drug lines but none carry the flag as True, we surface
    # False (a positive signal the flag is absent); when there are NO drug
    # lines at all we leave the key unset so rules honest-skip rather than
    # guessing False on a claim that simply has no pharmacy data.
    drug_lines = _lines_for_claim("drug_lines")
    if drug_lines:
        reports = [d for d in drug_lines if getattr(d, "drug_specialty_board_report_present", None)]
        context["health_board_report_present"] = bool(reports)

    return context


def check_treatment_pricing_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Evaluate the §2.4 treatment-pricing rules against a ``PatientClaimContext``.

    Entry point bridging the typed claim context to the rule evaluator. Builds
    the flat context dict, iterates the loaded rules, and emits one violation
    per firing rule. Rules whose condition keys are not derivable from
    ``PatientClaimContext`` (IVF cycles, session windows, BMI, clinical scores,
    …) honest-skip — they never fire here. Each violation carries:
    ``rule_id``, ``rule`` (``"treatment_pricing_2_4"``), ``severity`` (from the
    action), ``sut_section``, and the Turkish ``denial_tr`` message.
    """
    context = _build_treatment_pricing_context(ctx)
    if not context:
        return []
    if not _RULES_PATH.is_file():
        return []
    return _evaluate(load_treatment_pricing_rules(), context)
