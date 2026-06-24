"""MEDULA rejection triage queue endpoint."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Query

from src.bilun.api.schemas import MedulaRejectionQueueResponse
from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.claims.config import SUTDataSourceConfigError
from src.bilun.domain.claims.errors import ClaimValidationError
from src.bilun.domain.prose_rules.medula_rejection import match_playbook_template

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/medula-rejections", tags=["medula-rejections"])


def _normalize(text: str | None) -> str:
    return (text or "").casefold().strip()


def _load_dataset_with_fallback() -> Any | None:
    """Load the exact claim dataset, returning None when unavailable."""
    try:
        return load_sut_claim_dataset()
    except (ClaimValidationError, FileNotFoundError, OSError, SUTDataSourceConfigError, ValueError) as exc:
        logger.warning("MEDULA rejection queue cannot load claim dataset: %s", exc)
        return None


def _build_queue_row(event, claim, template: dict[str, Any] | None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "rejection_event_id": event.rejection_event_id,
        "patient_id": event.patient_id,
        "claim_id": event.claim_id,
        "episode_id": event.episode_id,
        "medula_stage": event.medula_stage,
        "sonuc_kodu": event.sonuc_kodu,
        "hata_mesaji": event.hata_mesaji,
        "related_procedure_code": event.related_procedure_code,
        "related_procedure_line_id": event.related_procedure_line_id,
        "related_line_type": event.related_line_type,
        "related_line_id": event.related_line_id,
        "rejection_timestamp": event.rejection_timestamp.isoformat() if event.rejection_timestamp else None,
        "playbook_matched": template is not None,
        "playbook_key": None,
        "sut_anchor": None,
        "rebill_permitted": None,
        "corrective_steps_tr": [],
    }
    if template is not None:
        row["playbook_key"] = template.get("playbook_key")
        row["sut_anchor"] = template.get("sut_anchor")
        row["rebill_permitted"] = bool(template.get("rebill_permitted"))
        row["corrective_steps_tr"] = list(template.get("corrective_steps_tr", []))
    return row


@router.get("/ingest-status")
def get_medula_rejection_ingest_status() -> dict[str, bool]:
    """Return whether MEDULA rejection event ingest is available."""
    dataset = _load_dataset_with_fallback()
    return {
        "ingest_available": bool(
            dataset is not None and dataset.medula_rejection_ingest_available
        ),
    }


@router.get("/queue", response_model=MedulaRejectionQueueResponse)
def get_medula_rejection_queue(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    sonuc_kodu: str | None = None,
    medula_stage: str | None = None,
    rebill_permitted: bool | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    """Return a cohort-level queue of ingested MEDULA rejections.

    Each row maps a rejection event to a corrective playbook template when one
    exists. The queue is operational guidance only — BILUN does not submit
    rebills to MEDULA.
    """
    dataset = _load_dataset_with_fallback()
    if dataset is None or not dataset.medula_rejection_ingest_available:
        return {
            "ingest_available": False,
            "rows": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
        }

    rows: list[dict[str, Any]] = []
    for event in dataset.medula_rejection_events.values():
        claim = dataset.claims.get(event.claim_id)
        if claim is None:
            continue
        template = match_playbook_template(event)
        row = _build_queue_row(event, claim, template)

        if sonuc_kodu is not None and _normalize(row["sonuc_kodu"]) != _normalize(sonuc_kodu):
            continue
        if medula_stage is not None and _normalize(row["medula_stage"]) != _normalize(medula_stage):
            continue
        if rebill_permitted is not None and row["rebill_permitted"] != rebill_permitted:
            continue
        if q:
            query = _normalize(q)
            searchable = " ".join(
                [
                    row["patient_id"],
                    row["claim_id"],
                    row["episode_id"],
                    row["sonuc_kodu"],
                    row["hata_mesaji"],
                ]
            )
            if query not in _normalize(searchable):
                continue
        rows.append(row)

    rows.sort(
        key=lambda r: (
            r["rejection_timestamp"] or "",
            r["claim_id"],
        ),
        reverse=True,
    )

    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = rows[start:end]

    return {
        "ingest_available": True,
        "rows": paginated,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
