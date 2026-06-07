"""MEDULA rejection → corrective rebill playbook mapping."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from src.bilun.domain.constants import _DATA_DIR
from src.bilun.domain.prose_rules.types import SAVINGS_CATEGORY_MEDULA_PLAYBOOK

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, MedulaRejectionEvent

_PLAYBOOK_PATH = _DATA_DIR / "medula" / "rejection_playbook.json"
_RULE_SET_ID = "medula_rejection_playbook"
_OPPORTUNITY_TYPE = "medula_rejection_playbook"


@lru_cache(maxsize=1)
def load_medula_rejection_playbook() -> dict[str, Any]:
    with _PLAYBOOK_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _normalize(text: str) -> str:
    return text.casefold().strip()


def _message_matches(event: MedulaRejectionEvent, keywords: list[str]) -> bool:
    if not keywords:
        return True
    message = _normalize(event.hata_mesaji)
    return any(_normalize(keyword) in message for keyword in keywords)


def match_playbook_template(event: MedulaRejectionEvent) -> dict[str, Any] | None:
    """Return the first playbook template matching a MEDULA rejection event."""
    playbook = load_medula_rejection_playbook()
    sonuc = _normalize(event.sonuc_kodu)
    stage = _normalize(event.medula_stage)

    for entry in playbook.get("entries", []):
        if _normalize(str(entry.get("sonuc_kodu", ""))) != sonuc:
            continue
        allowed_stages = {
            _normalize(str(value)) for value in entry.get("medula_stages", [])
        }
        if allowed_stages and stage not in allowed_stages:
            continue
        if not _message_matches(event, list(entry.get("hata_mesaji_keywords", []))):
            continue
        return entry
    return None


def build_medula_playbook_entry(
    claim: ClaimHeader,
    event: MedulaRejectionEvent,
    template: dict[str, Any],
) -> dict[str, Any]:
    """Build a billing-report playbook row from a matched template."""
    return {
        "playbook_id": template.get("playbook_key", event.rejection_event_id),
        "rejection_event_id": event.rejection_event_id,
        "claim_id": claim.claim_id,
        "patient_id": claim.patient_id,
        "episode_id": claim.episode_id,
        "medula_stage": event.medula_stage,
        "sonuc_kodu": event.sonuc_kodu,
        "hata_kodu": event.hata_kodu,
        "hata_mesaji": event.hata_mesaji,
        "related_procedure_code": event.related_procedure_code,
        "related_procedure_line_id": event.related_procedure_line_id,
        "sut_anchor": template.get("sut_anchor", ""),
        "problem_summary_tr": template.get("problem_summary_tr", ""),
        "problem_summary_en": template.get("problem_summary_en", ""),
        "corrective_steps_tr": list(template.get("corrective_steps_tr", [])),
        "corrective_steps_en": list(template.get("corrective_steps_en", [])),
        "rebill_permitted": bool(template.get("rebill_permitted", False)),
        "rebill_stage": template.get("rebill_stage", ""),
        "opportunity_type": _OPPORTUNITY_TYPE,
        "recommendation_kind": "corrective_rebill_template",
        "included_in_sgk_total": False,
        "savings_category": SAVINGS_CATEGORY_MEDULA_PLAYBOOK,
        "rule_set_id": _RULE_SET_ID,
        "rule_id": f"medula_playbook.{template.get('playbook_key', event.sonuc_kodu)}",
        "scenario_tag": claim.scenario_tag,
    }


def detect_medula_rejection_playbook_entries(
    claim: ClaimHeader,
    events: list[MedulaRejectionEvent],
) -> list[dict[str, Any]]:
    """Map MEDULA rejection events on a claim to corrective rebill playbook rows."""
    playbook = load_medula_rejection_playbook()
    if not playbook.get("entries"):
        return []

    entries: list[dict[str, Any]] = []
    for event in events:
        if event.claim_id != claim.claim_id:
            continue
        template = match_playbook_template(event)
        if template is None:
            continue
        entries.append(build_medula_playbook_entry(claim, event, template))
    return entries
