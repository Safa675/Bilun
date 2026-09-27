"""SUT gap-closing prose rules — cross-section claim-context gates.

Two rule sets live here, both encoding whole-claim (not line-level) billing
gates that close coverage gaps across §1.5, §1.6, §1.8, §2.2, §2.3, §2.5:

- ``gap_closing_misc`` (40 rules) — §1.5/§1.6 provider-contracting + §3/§4/§5
  cross-cutting no-pay/must-bill gates.
- ``gap_closing_treatment_2`` (44 rules) — §2.2 payment-method + §2.3/§2.5
  treatment-scoped bundling and overseas/emergency gates.

Conditions are predominantly boolean flags evaluated against a flat
``context`` dict (claim-level facts pre-computed by the adapter), with a few
``*_any`` set-membership predicates over claim fields (procedure_category,
diagnosis, facility_tier, provider_type). Rules whose conditions reference
data not present on the claim (``hours_since_onset``, ``stem_cell_type``,
``overseas_treatment_days``) are skipped at evaluation time rather than
guessing — they stay in the rule set for inventory/coverage but do not fire
on claims lacking that data.

``action.billable`` maps to a billable outcome; ``denial_tr``/``payment_tr``
carries the regulatory message.
"""

from __future__ import annotations

import json
from functools import lru_cache, cache
from typing import Any

from ..constants import _PROSE_RULES_DIR
from .facility_tier import normalize_facility_tier

_MISC_RULES_PATH = _PROSE_RULES_DIR / "gap_closing_misc.json"
_TREATMENT_RULES_PATH = _PROSE_RULES_DIR / "gap_closing_treatment_2.json"

# Condition keys that are NOT boolean flags but set/scalar predicates resolved
# against claim fields. Anything not in this set is treated as a boolean flag
# looked up via context.get(key).
# Order matters: longer suffixes MUST come first so _suffix_len matches
# "_not_any" before "_any" (otherwise "procedure_code_not_any" matches "_any"
# and yields base "procedure_code_not" — wrong). See audit finding #4.
_SET_PREDICATE_SUFFIXES = ("_not_any", "_not_in", "_any", "_in")
_SCALAR_FIELDS = {
    "procedure_category",
    "procedure_code",
    "payment_method",
    "payment_method_path",
    "provider_type",
    "provider_contract_status",
    "specialty",
    "visit_type",
    "care_setting",
    "treatment_setting",
    "patient_category",
    "anesthesia_type",
    "stage",
    "indication",
    "drug_category",
    "material_category",
    "facility_tier",
    "facility_tier_basamak",
    "facility_type",
    "expense_type",
    "test_type",
}


@lru_cache(maxsize=1)
def load_gap_closing_misc_rules() -> dict[str, Any]:
    with _MISC_RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_gap_closing_treatment_rules() -> dict[str, Any]:
    with _TREATMENT_RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _condition_matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    """Evaluate a gap-closing rule condition against a flat claim context.

    Each condition key is resolved as:
    - boolean flag → ``context.get(key)`` must equal the condition value;
    - ``*_any`` predicate → at least one claim value in the set must be present
      in the context's collection for that base field;
    - ``procedure_in_annex`` → at least one billed procedure code is a member
      of the named annex (e.g. ``EK-2/A-2``, ``EK-2/C-1``, ``EK-2/C``,
      ``EK-2/B``); resolved against the loaded catalog code sets.
    - scalar field → ``context.get(field)`` must equal the condition value.

    Keys absent from ``context`` cause the rule to be skipped (returns False)
    rather than firing on missing data — this is the honesty guard.
    """
    for key, expected in condition.items():
        # procedure_in_annex — annex membership over the billed procedure codes.
        # The predicate value is the annex identifier (e.g. "EK-2/A-2"); the
        # billed codes are surfaced under context["procedure_code_any"]. We
        # import the resolver lazily to avoid a module-load cycle (catalog
        # membership pulls in heavy catalog machinery).
        if key == "procedure_in_annex":
            annex = str(expected or "").strip()
            billed_codes = context.get("procedure_code_any") or context.get("procedure_code")
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

        if key.endswith(_SET_PREDICATE_SUFFIXES):
            base = key[: -_suffix_len(key)]
            # Prefer the explicit <base>_any / <base>_in collection when the
            # context builder supplied one; fall back to the base field so a
            # single-valued claim still matches. A bare scalar base field is
            # a valid (single-element) collection, but a multi-valued claim
            # MUST surface its full set under the *_any key — otherwise rules
            # like procedure_category_any silently honest-skip on claims that
            # genuinely carry the listed category.
            available = context.get(key)
            if available is None:
                available = context.get(base)
            if available is None:
                return False
            # Normalize to a set for membership testing regardless of shape.
            available_set = (
                set(available) if isinstance(available, (list, tuple, set))
                else {available}
            )
            expected_set = (
                set(expected) if isinstance(expected, (list, tuple, set))
                else {expected}
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
                # Scalar field not surfaced on this claim. For a scalar predicate
                # like ``procedure_category`` that has an ``*_any`` collection
                # counterpart (e.g. ``procedure_category_any``), fall back to
                # membership testing against that collection. This is the
                # multi-category scalar fallback: when a claim carries mixed
                # categories the builder leaves the scalar unset (it cannot pick
                # one truthfully) but surfaces the full set under ``*_any``, so a
                # rule asking ``procedure_category == 'ftr'`` should still match
                # if 'ftr' is in the claim's category set. Without this fallback
                # ~80 rules honest-skip on any multi-category claim.
                any_collection = context.get(f"{key}_any")
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
            if bool(actual) != bool(expected) if isinstance(expected, bool) else actual != expected:
                return False
            continue

        # Unknown predicate shape → skip rather than mis-evaluate.
        return False

    return True


def _suffix_len(key: str) -> int:
    for suffix in _SET_PREDICATE_SUFFIXES:
        if key.endswith(suffix):
            return len(suffix)
    return 0


def _violation_from_rule(
    rule: dict[str, Any],
    ruleset_id: str,
) -> dict[str, Any]:
    action = rule.get("action") or {}
    billable = bool(action.get("billable", True))
    message = action.get("denial_tr") or action.get("payment_tr") or action.get("message_tr") or rule.get("rule_id", "")
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


def check_gap_closing_misc(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate the §1.5/§1.6/§3-§6 gap-closing rules against a claim context."""
    if not _MISC_RULES_PATH.is_file():
        return []
    return _evaluate(load_gap_closing_misc_rules(), context)


def check_gap_closing_treatment(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate the §2.2/§2.3/§2.5 treatment gap-closing rules against a claim context."""
    if not _TREATMENT_RULES_PATH.is_file():
        return []
    return _evaluate(load_gap_closing_treatment_rules(), context)


def _evaluate(ruleset: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    ruleset_id = ruleset.get("rule_set_id", "")
    violations: list[dict[str, Any]] = []
    for rule in ruleset.get("rules") or []:
        condition = rule.get("condition") or {}
        if not _condition_matches(condition, context):
            continue
        violations.append(_violation_from_rule(rule, ruleset_id))
    return violations


def _derive_payment_method_path(
    header: Any,
    procedures: list[Any],
    *,
    care_setting: str,
) -> str | None:
    """Derive the §2.2.2.B claim-level payment *path* the gap-closing rules gate on.

    The rules use a different vocabulary from the procedure-level
    ``package``/``itemized`` decision: ``diagnosis_based`` = tanıya dayalı
    (EK-2/C DRG package path), ``fee_for_service`` = hizmet başına (EK-2/B
    itemized path). These map cleanly onto the claim-aggregated
    ``PaymentMethodKind`` already computed by ``care_setting_review`` /
    ``claim_strategy``:

    - ``DRG_MANDATORY`` / ``DRG_OVERRIDABLE`` → ``diagnosis_based``
      (both are EK-2/C package paths; overridable still bills as package
      unless the third-tier override is exercised)
    - ``ITEMIZED`` → ``fee_for_service``

    Returns ``None`` when there are no classifiable procedure lines or the
    kind cannot be resolved — the caller MUST leave ``payment_method`` unset
    in that case so ``_condition_matches`` honesty-skips rather than guessing.
    """
    if procedures:
        # Local import to avoid an import cycle: care_setting_review imports
        # from this package's neighbors and would otherwise pull in heavy
        # catalog machinery at module load time.
        from .care_setting_review import _resolve_claim_kind

        kind = _resolve_claim_kind(header, procedures, care_setting=care_setting)
        if kind in {"DRG_MANDATORY", "DRG_OVERRIDABLE"}:
            return "diagnosis_based"
        if kind == "ITEMIZED":
            return "fee_for_service"
        # MISSING_INPUTS / NOT_IN_SUT / None → fall through to the header signal.
    # Header-only fallback: package_candidate=True is a weaker but real signal
    # that a DRG package line is present on the claim (set by the synthetic
    # generators when an EK-2/C package line exists).
    if getattr(header, "package_candidate", None) is True:
        return "diagnosis_based"
    return None


@cache
def _build_gap_closing_context(ctx: Any) -> dict[str, Any]:
    """Build the flat claim-context dict from a PatientClaimContext.

    Maps ``ClaimHeader`` fields + derives the most common gap-closing flags
    from existing claim data. Many of the ~118 condition keys will be absent
    (honest skip via ``_condition_matches``). The keys surfaced here cover the
    most frequent conditions: ``procedure_category``, ``is_emergency``,
    ``care_setting``, ``payment_method``, ``facility_*``, ``procedure_code_any``,

    Memoized: ``PatientClaimContext`` is frozen/hashable, and ``analyze_claim``
    invokes this builder up to 3× per claim (misc + treatment + payment-method
    traceability) with the same ``ctx``. The cached dict is treated read-only by
    all consumers (``_condition_matches`` / ``check_*`` only call ``.get()``).
    Clear via ``_build_gap_closing_context.cache_clear()`` in tests that mutate
    claim data.
    ``drug_category``, ``health_report_present``.
    """
    if not ctx.claims:
        return {}
    header = ctx.claims[0]
    # Scope line aggregations to the first claim only. A PatientClaimContext
    # can carry multiple bills for one patient; aggregating every line while
    # reading header fields from claims[0] would let a second bill's
    # procedures/drugs/materials contaminate this claim's derived flags
    # (procedure_category_any, payment_method, drug_category, ...). This
    # mirrors the claim-scoping the material_uplift wrapper applies.
    claim_id = getattr(header, "claim_id", None)

    def _lines_for_claim(attr: str) -> list[Any]:
        return [
            line for line in (getattr(ctx, attr, ()) or ())
            if getattr(line, "claim_id", None) == claim_id
        ]

    context: dict[str, Any] = {
        "facility_tier": header.facility_tier or "",
        "provider_type": header.provider_type or "",
        "claim_type": header.claim_type or "",
    }
    # SUT §2.1.2.A/§2.2.2 use yatan-hasta/yatarak terminology. Recognize
    # yatarak just like claim_utils.infer_care_setting and treatment_pricing;
    # leaking that raw token silently fails authored inpatient predicates.
    # Preserve other legacy fallbacks; their metadata gates handle unknowns.
    claim_type_lower = (header.claim_type or "").lower()
    if any(token in claim_type_lower for token in ("yatis", "yatarak", "inpatient")):
        context["care_setting"] = "inpatient"
    elif (
        "ayakta" in claim_type_lower
        or "outpatient" in claim_type_lower
        or "poliklinik" in claim_type_lower
        or "gunubirlik" in claim_type_lower
    ):
        context["care_setting"] = "outpatient"
    else:
        context["care_setting"] = claim_type_lower or "outpatient"
    # Emergency: department or scenario_tag carries emergency signal.
    dept = (header.department or "").lower()
    tag = (header.scenario_tag or "").lower()
    context["is_emergency"] = (
        "acil" in dept or "emergency" in dept or "acil" in tag or "emergency" in tag
    )
    # Facility contracting: uncontracted if provider_type indicates it.
    # The Turkish contracted/uncontracted marker is "sozlesmesiz" (single s);
    # the synthetic generators use exactly this spelling — see
    # scripts/synthetic/gen/materials_flags.py ("acil_sozlesmesiz_kurum").
    context["facility_uncontracted"] = header.provider_type in ("uncontracted", "sozlesmesiz")
    context["facility_contracted"] = header.provider_type not in ("uncontracted", "sozlesmesiz", "")
    # Health report: drug lines carry board-report presence.
    drug_lines = _lines_for_claim("drug_lines")
    if drug_lines:
        reports = [d for d in drug_lines if d.drug_specialty_board_report_present]
        context["health_report_present"] = bool(reports)
    # Procedure-derived fields.
    procedure_lines = _lines_for_claim("procedure_lines")
    if procedure_lines:
        categories = {p.procedure_category for p in procedure_lines if p.procedure_category}
        codes = {p.procedure_code for p in procedure_lines if p.procedure_code}
        # Surface BOTH shapes so every predicate form can match:
        # - the bare scalar field (procedure_category / procedure_code) is read
        #   by exact-equality rules (11 gap-closing rules use bare
        #   procedure_category); when the claim has multiple distinct values we
        #   cannot pick one truthfully, so we leave it unset and let those rules
        #   honest-skip rather than mis-attribute.
        # - the *_any collection key is read by membership predicates
        #   (procedure_category_any / procedure_code_any); it carries the full
        #   set so any listed value matches.
        if categories:
            context["procedure_category_any"] = sorted(categories)
            if len(categories) == 1:
                context["procedure_category"] = next(iter(categories))
        if codes:
            context["procedure_code_any"] = sorted(codes)
            if len(codes) == 1:
                context["procedure_code"] = next(iter(codes))
            # Specialty surfacing — future-proofing for rules that gate on
            # the billing specialty. No current gap_closing rule references
            # this key, but treatment_pricing + fatura_inceleme already surface it.
            specialties = {
                getattr(p, "procedure_specialty_code", "") or ""
                for p in procedure_lines
            }
            specialties.discard("")
            if specialties:
                context["specialty_any"] = sorted(specialties)
                if len(specialties) == 1:
                    context["specialty"] = next(iter(specialties))
            # §1.9.1.(1) extra-fee-scope gate: EK-2/A is the outpatient
            # VISIT-FEE annex (not a procedure list — the catalog resolver
            # for "EK-2/A" deliberately returns an empty set, see
            # catalog_membership.codes_in_annex). A billed procedure is
            # therefore NOT bundled into the EK-2/A visit fee, so the
            # ``service_not_in_ek2a_bundled: true`` condition is satisfied
            # whenever the claim carries any procedure code. Lazy import to
            # avoid pulling heavy catalog machinery at module load.
            from .catalog_membership import any_procedure_in_annex

            context["service_not_in_ek2a_bundled"] = not any_procedure_in_annex(
                sorted(codes), "EK-2/A"
            )
    # Payment method (§2.2.2.B path): derived from the claim-aggregated
    # PaymentMethodKind, NOT from package_candidate directly. The kind-based
    # derivation is the canonical SUT §2.2 evaluator's output; package_candidate
    # is only a header-level fallback. See _derive_payment_method_path.
    payment_method = _derive_payment_method_path(
        header, procedure_lines, care_setting=context["care_setting"]
    )
    if payment_method is not None:
        context["payment_method"] = payment_method
        # ``payment_method_path`` is the payment_method_2_2.json vocabulary for
        # the same §2.2.2.B path decision: ``itemized`` == EK-2/B fee-for-service
        # (itemized billing). The DRG/diagnosis_based path has no single
        # ``payment_method_path`` token the rules use, so it is left unset and
        # those rules honest-skip. Surfacing ``itemized`` here unblocks the
        # §2.2.2.A / §2.2.1.B-2.(2) itemized-basis traceability rules.
        if payment_method == "fee_for_service":
            context["payment_method_path"] = "itemized"
    # ───────────────────────────────────────────────────────────────────────
    # §2.2 context keys reused by the payment_method traceability pass
    # (payment_method_2_2.json). All derived from EXISTING header/line fields
    # — no new data is invented. Keys that genuinely need cross-claim or
    # clinical data the claim model does not carry (visit_sequence,
    # same_specialty_repeat_days_lt, line_type, contract_status cross-claim
    # lookups, etc.) are intentionally left unset so ``_condition_matches``
    # honest-skips the rules that reference them rather than guessing.
    # ───────────────────────────────────────────────────────────────────────
    # provider_contract_status: provider_type is a SUT-contracting signal.
    #   sozlesmeli/contracted → "contracted"; sozlesmesiz/uncontracted →
    #   "uncontracted". The 2.2.(8)/2.2.(12) rules gate on "contracted".
    if header.provider_type in ("sozlesmeli", "contracted", "private"):
        context["provider_contract_status"] = "contracted"
    elif header.provider_type in ("uncontracted", "sozlesmesiz"):
        context["provider_contract_status"] = "uncontracted"
    # visit_type: the day-case marker "gunubirlik" surfaces directly from
    # claim_type (SUT §2.2.2.(4)/(5) gunubirlik no day-bed / companion-fee
    # rules). Other visit types (telehealth, followup) require line-level data
    # the model does not carry → left unset (honest skip).
    if "gunubirlik" in claim_type_lower:
        context["visit_type"] = "gunubirlik"
    # facility_type: training/research hospitals (universite / egitim_arastirma
    # provider types) are the §2.2.1.B-1.c / §2.2.2.A(6) / §2.2.1.B-2.(4) gate.
    # Private (ozel/private provider types, 2_3_basamak_ozel tier) and
    # foundation-university (vakif / universite_vakif) facility types gate the
    # §1.9.1.(1) extra-fee-scope rule.
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
    # facility_tier_basamak: resolved via the facility_tier normalizer (2 or 3).
    #   The 2.2.2.(2) override rule gates on basamak == 3. Only surfaced when the
    #   tier resolves (basamak is not None); unresolved tiers honest-skip.
    tier_context = normalize_facility_tier(
        header.facility_tier, provider_type=header.provider_type
    )
    if tier_context.basamak is not None:
        context["facility_tier_basamak"] = tier_context.basamak
    # emergency_excluded: the §2.2.1.B-4 same-specialty repeat rules EXCLUDE
    # emergency claims from the no-visit-fee gate. When the claim IS an
    # emergency, ``emergency_excluded`` must be True for those rules; we cannot
    # truthfully assert the negative ("this claim is definitely non-emergency")
    # from header data alone, so we only surface True and otherwise leave the key
    # absent (honest skip) rather than emitting a wrong False.
    if context["is_emergency"]:
        context["emergency_excluded"] = True
    # Drug-derived fields. Surface the full set under ``drug_category_any``
    # (membership predicates) and the bare scalar only when the claim has a
    # single category (exact-equality rules); see the procedure_category note
    # above for the multi-value honesty contract.
    if drug_lines:
        drug_categories = set()
        for d in drug_lines:
            cat = getattr(d, "drug_category", None) or ""
            if cat:
                drug_categories.add(cat)
        if drug_categories:
            context["drug_category_any"] = sorted(drug_categories)
            if len(drug_categories) == 1:
                context["drug_category"] = next(iter(drug_categories))
    # Material-derived fields. Same scalar/``*_any`` contract as drugs/procedures.
    material_lines = _lines_for_claim("material_lines")
    if material_lines:
        material_categories = {m.specialty_category for m in material_lines if m.specialty_category}
        if material_categories:
            context["material_category_any"] = sorted(material_categories)
            if len(material_categories) == 1:
                context["material_category"] = next(iter(material_categories))
    return context


def check_gap_closing_misc_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Evaluate §1.5/§1.6/§3-§6 gap-closing rules against a PatientClaimContext.

    Wiredness epic W1.3 — bridges the gap_closing evaluator (which takes a flat
    dict) to the typed PatientClaimContext via ``_build_gap_closing_context``.

    Contract — single-claim context: the builder evaluates ``ctx.claims[0]``
    only. ``analyze_claim`` is invoked from two places: the ``/validate-claim``
    dict adapter (inherently single-claim) and the billing orchestrator, which
    calls it once per claim via ``slice_for_claim`` (see ``lab_bill_merge.py``
    and ``build_bill_claim_context``). A whole-patient ``PatientClaimContext``
    carrying multiple claims is never passed here in production; callers that
    need every claim evaluated must iterate ``ctx.claims`` and slice. The
    The material_uplift wrapper shares this contract.
    """
    context = _build_gap_closing_context(ctx)
    if not context:
        return []
    return check_gap_closing_misc(context)


def check_gap_closing_treatment_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Evaluate §2.2/§2.3/§2.5 treatment gap-closing rules against a PatientClaimContext.

    Wiredness epic W1.3 — bridges the gap_closing evaluator to the typed context.
    """
    context = _build_gap_closing_context(ctx)
    if not context:
        return []
    return check_gap_closing_treatment(context)
