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
from src.bilun.domain.turkish_fold import TurkishFold, fold_turkish

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/medula-rejections", tags=["medula-rejections"])


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


def _facet_values(rows: list[dict[str, Any]], key: str) -> list[str]:
    values = {str(row.get(key) or "") for row in rows}
    return sorted(value for value in values if value)


def _queue_stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "n_events": len(rows),
        "n_matched": sum(1 for row in rows if row.get("playbook_matched")),
        "n_rebill_permitted": sum(1 for row in rows if row.get("rebill_permitted") is True),
    }


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
    playbook_matched: bool | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    """Return a cohort-level queue of ingested MEDULA rejections.

    Each row maps a rejection event to a corrective playbook template when one
    exists. The queue is operational guidance only — BILUN does not submit
    rebills to MEDULA.
    """
    empty_facets = {"sonuc_kodu": [], "medula_stage": []}
    empty_stats = {"n_events": 0, "n_matched": 0, "n_rebill_permitted": 0}
    dataset = _load_dataset_with_fallback()
    if dataset is None or not dataset.medula_rejection_ingest_available:
        return {
            "ingest_available": False,
            "rows": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "facets": empty_facets,
            "stats": empty_stats,
        }

    all_rows: list[dict[str, Any]] = []
    for event in dataset.medula_rejection_events.values():
        claim = dataset.claims.get(event.claim_id)
        if claim is None:
            continue
        template = match_playbook_template(event)
        all_rows.append(_build_queue_row(event, claim, template))

    facets = {
        "sonuc_kodu": _facet_values(all_rows, "sonuc_kodu"),
        "medula_stage": _facet_values(all_rows, "medula_stage"),
    }
    stats = _queue_stats(all_rows)

    rows: list[dict[str, Any]] = []
    for row in all_rows:
        if sonuc_kodu is not None and fold_turkish(
            row["sonuc_kodu"] or "", TurkishFold.CASEFOLD, strip=True
        ) != fold_turkish(sonuc_kodu or "", TurkishFold.CASEFOLD, strip=True):
            continue
        if medula_stage is not None and fold_turkish(
            row["medula_stage"] or "", TurkishFold.CASEFOLD, strip=True
        ) != fold_turkish(medula_stage or "", TurkishFold.CASEFOLD, strip=True):
            continue
        if rebill_permitted is not None and row["rebill_permitted"] != rebill_permitted:
            continue
        if playbook_matched is not None and bool(row["playbook_matched"]) != playbook_matched:
            continue
        if q:
            query = fold_turkish(q or "", TurkishFold.CASEFOLD, strip=True)
            searchable = " ".join(
                [
                    row["patient_id"],
                    row["claim_id"],
                    row["episode_id"],
                    row["sonuc_kodu"],
                    row["hata_mesaji"],
                ]
            )
            if query not in fold_turkish(searchable or "", TurkishFold.CASEFOLD, strip=True):
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
        "facets": facets,
        "stats": stats,
    }
