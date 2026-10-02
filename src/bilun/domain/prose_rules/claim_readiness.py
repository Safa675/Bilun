"""Proactive claim submission checklist — narrow MEDULA rejection risk triggers."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from src.bilun.domain.constants import _DATA_DIR
from src.bilun.domain.prose_rules.medula_rejection import load_medula_rejection_playbook
from src.bilun.domain.prose_rules.types import SAVINGS_CATEGORY_MEDULA_PLAYBOOK

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine, MaterialClaimLine
    from src.bilun.domain.claims.patient_context import PatientClaimContext

_TRIGGERS_PATH = _DATA_DIR / "medula" / "claim_readiness_triggers.json"
_RULE_SET_ID = "claim_submission_checklist"
_OPPORTUNITY_TYPE = "claim_submission_checklist"


@lru_cache(maxsize=1)
def load_claim_readiness_triggers() -> dict[str, Any]:
    with _TRIGGERS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _playbook_by_key() -> dict[str, dict[str, Any]]:
    playbook = load_medula_rejection_playbook()
    return {
        str(entry.get("playbook_key", "")): entry
        for entry in playbook.get("entries", [])
        if entry.get("playbook_key")
    }


def _line_field_value(line: Any, field: str) -> Any:
    return getattr(line, field, None)


def _match_signal(line: Any, signal: dict[str, Any]) -> bool:
    if "all_of" in signal:
        return all(_match_signal(line, part) for part in signal["all_of"])
    if "any_of" in signal:
        return any(_match_signal(line, part) for part in signal["any_of"])

    field = str(signal.get("field", ""))
    expected = signal.get("equals")
    actual = _line_field_value(line, field)
    if expected is None and "equals" in signal:
        return actual is None
    return actual == expected


def _claim_rejection_codes(claim_id: str, ctx: PatientClaimContext) -> set[str]:
    return {
        str(event.sonuc_kodu).strip()
        for event in ctx.medula_rejection_events
        if event.claim_id == claim_id and event.sonuc_kodu
    }


def _build_checklist_item(
    claim: ClaimHeader,
    *,
    trigger: dict[str, Any],
    line: DrugClaimLine | MaterialClaimLine,
    line_type: str,
    template: dict[str, Any] | None,
) -> dict[str, Any]:
    playbook_key = str(trigger.get("playbook_key") or "")
    sonuc = str(trigger.get("sonuc_kodu_risk") or "")
    line_id = getattr(
        line, "drug_claim_line_id" if line_type == "drug" else "material_line_id", "",
    )
    # New scoped identities cannot inherit the old blank-suffix readiness key.
    identity = (claim.patient_id, claim.claim_id, trigger.get("trigger_key") or playbook_key,
                line_type, line_id)
    return {
        "checklist_id": "claim_readiness:" + ":".join(
            quote(str(value), safe="") for value in identity
        ),
        "trigger_key": trigger.get("trigger_key", ""),
        "playbook_key": playbook_key,
        "sonuc_kodu_risk": sonuc,
        "severity": trigger.get("severity", "warning"),
        "claim_id": claim.claim_id,
        "patient_id": claim.patient_id,
        "episode_id": claim.episode_id,
        "line_type": line_type,
        "line_id": line_id,
        "line_code": getattr(
            line,
            "drug_code" if line_type == "drug" else "material_code",
            "",
        ),
        "line_name": getattr(
            line,
            "drug_name" if line_type == "drug" else "material_name",
            "",
        ),
        "reminder_tr": trigger.get("reminder_tr", ""),
        "reminder_en": trigger.get("reminder_en", ""),
        "sut_anchor": (template or {}).get("sut_anchor", ""),
        "preventive_steps_tr": list((template or {}).get("corrective_steps_tr") or []),
        "preventive_steps_en": list((template or {}).get("corrective_steps_en") or []),
        "recommendation_kind": "proactive_submission_checklist",
        "included_in_sgk_total": False,
        "savings_category": SAVINGS_CATEGORY_MEDULA_PLAYBOOK,
        "rule_set_id": _RULE_SET_ID,
        "rule_id": f"claim_readiness.{trigger.get('trigger_key', sonuc)}",
        "scenario_tag": claim.scenario_tag,
    }


def detect_claim_readiness_items(
    claim: ClaimHeader,
    ctx: PatientClaimContext,
) -> list[dict[str, Any]]:
    """Return proactive checklist rows for one claim when claim-shape signals match."""
    triggers = load_claim_readiness_triggers().get("triggers") or []
    if not triggers:
        return []

    existing_codes = _claim_rejection_codes(claim.claim_id, ctx)
    templates = _playbook_by_key()
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for trigger in triggers:
        sonuc = str(trigger.get("sonuc_kodu_risk") or "")
        if sonuc and sonuc in existing_codes:
            continue

        line_type = str(trigger.get("line_type") or "")
        signal = trigger.get("signal") or {}
        lines: tuple[Any, ...]
        if line_type == "drug":
            lines = tuple(
                line for line in ctx.drug_lines if line.claim_id == claim.claim_id
            )
        elif line_type == "material":
            lines = tuple(
                line for line in ctx.material_lines if line.claim_id == claim.claim_id
            )
        else:
            continue

        template = templates.get(str(trigger.get("playbook_key") or ""))
        for line in lines:
            if not _match_signal(line, signal):
                continue
            item = _build_checklist_item(
                claim,
                trigger=trigger,
                line=line,
                line_type=line_type,
                template=template,
            )
            dedupe_key = item["checklist_id"]
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            items.append(item)

    return items


def detect_claim_readiness_for_context(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    """Aggregate proactive checklist rows across all claims in a patient context."""
    items: list[dict[str, Any]] = []
    for claim in ctx.claims:
        items.extend(detect_claim_readiness_items(claim, ctx))
    return items
