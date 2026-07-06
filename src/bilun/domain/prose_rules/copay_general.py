"""SUT §1.8 general copay rate evaluator."""

from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from ..constants import _PROSE_RULES_DIR
from .types import PatientCopayProfile

_RULE_SET_ID = "copay_general_1_8"
_RULES_PATH = _PROSE_RULES_DIR / "copay_general_1_8.json"


@lru_cache(maxsize=1)
def _load_copay_rules() -> dict:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _rate_for_profile(rule: dict, profile: PatientCopayProfile) -> float:
    rates = rule.get("rates", {})
    return float(rates.get(profile, rates.get("other", 0.2)))


@lru_cache(maxsize=1)
def _rules_by_service_type() -> dict[str, dict]:
    """Index copay rules by ``service_type`` (W2.1 refactor).

    Replaces the 4 hardcoded ``rule_id`` lookups with a single
    service_type-keyed dispatch. Each resolver knows its target service_type
    (``drug``, ``material``, ``ivf_treatment``, ``drug_prescription_flat``),
    so the lookup is O(1) and unblocks the 13 dormant rules structurally.

    Two rules share ``service_type: "material"`` — ``1.8.3.(1).protez_ortez``
    (external prosthesis/orthosis) and ``1.8.3.(2)`` (general materials). They
    carry identical rate tables, so the dispatch result is the same whichever
    is selected; we keep the FIRST (more specific, condition-gated) one and
    surface a one-time warning if a future rule change makes the duplicates
    diverge in rates. First-wins (not last-wins) so the condition-gated rule
    is the authoritative entry rather than silently overwritten.
    """
    rules = _load_copay_rules().get("rules", [])
    index: dict[str, dict] = {}
    seen_rates: dict[str, tuple] = {}
    for r in rules:
        st = r.get("service_type")
        if not st:
            continue
        rates = tuple(sorted((r.get("rates") or {}).items()))
        if st in index and seen_rates.get(st) and seen_rates[st] != rates:
            # Future divergence guard: if a rule edit makes two same-service_type
            # rules produce different rates, flag it so dispatch stays honest.
            import logging
            logging.getLogger(__name__).warning(
                "copay_general: duplicate service_type %r with divergent rates "
                "(kept %s, dropped %s) — resolve_*_copay_rate ignores the "
                "condition and returns a single rate; add condition-aware "
                "dispatch if the divergence is intentional.",
                st, index[st].get("rule_id"), r.get("rule_id"),
            )
        if st not in index:
            index[st] = r
            seen_rates[st] = rates
    return index


def _find_rule_by_service_type(service_type: str) -> dict | None:
    return _rules_by_service_type().get(service_type)


def resolve_drug_copay_rate(profile: PatientCopayProfile) -> float:
    """§1.8.2.(1) — drug copay percentage by patient income status."""
    drug_rule = _find_rule_by_service_type("drug")
    if drug_rule is None:
        return 0.2 if profile == "other" else 0.1
    return _rate_for_profile(drug_rule, profile)


def resolve_material_copay_rate(profile: PatientCopayProfile) -> float:
    """§1.8.3.(2) — prosthesis/orthosis material copay percentage."""
    material_rule = _find_rule_by_service_type("material")
    if material_rule is None:
        return 0.2 if profile == "other" else 0.1
    return _rate_for_profile(material_rule, profile)


def resolve_ivf_treatment_copay_rate(
    profile: PatientCopayProfile,
    *,
    attempt: int = 1,
) -> float:
    """§1.8.4.(1) — assisted reproduction treatment copay by attempt (1st/2nd/3rd)."""
    ivf_rule = _find_rule_by_service_type("ivf_treatment")
    if ivf_rule is None:
        defaults = {1: 0.3, 2: 0.25, 3: 0.2}
        return defaults.get(min(max(int(attempt), 1), 3), 0.2)

    attempt_key = str(min(max(int(attempt), 1), 3))
    by_attempt = ivf_rule.get("rates_by_attempt", {})
    attempt_rates = by_attempt.get(attempt_key, {})
    if profile in attempt_rates:
        return float(attempt_rates[profile])
    return float(attempt_rates.get("other", 0.3))


def resolve_ivf_drug_copay_rate(profile: PatientCopayProfile) -> float:
    """Backward-compatible alias — returns 1st-attempt §1.8.4.(1) treatment rate."""
    return resolve_ivf_treatment_copay_rate(profile, attempt=1)


def resolve_prescription_flat_fee_try(
    box_count: int,
    *,
    as_of: date | str | None = None,
) -> float:
    """§1.8.2.(2) — per-prescription flat copay fee by box count."""
    flat_rule = _find_rule_by_service_type("drug_prescription_flat")
    if flat_rule is None:
        return 0.0

    as_of_date = _coerce_date(as_of) or date.today()
    effective_from = _coerce_date(flat_rule.get("effective_from"))
    fee_key = (
        "fees_try"
        if effective_from is None or as_of_date >= effective_from
        else "legacy_fees_try"
    )
    fees = flat_rule.get(fee_key, flat_rule.get("fees_try", {}))
    base = float(fees.get("base_up_to_3_boxes", 3.76))
    extra = float(fees.get("per_extra_box", 1.25))

    count = max(int(box_count), 0)
    if count <= 0:
        return 0.0
    if count <= 3:
        return base
    return round(base + (count - 3) * extra, 2)


def _coerce_date(value: date | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def load_decision_table() -> dict:
    return _load_copay_rules()
