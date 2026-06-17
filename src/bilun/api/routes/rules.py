"""SUT rule database endpoints — `/rules`, `/rules/{rule_id}`.

Serves the rule catalog (index of every :data:`RULE_REGISTRY` entry with its
regulatory sources + implementation coverage) and per-rule drill-down into the
actual extracted SUT clause text. Clause data is read from the offline-built
coverage matrix; when that artifact is absent the catalog still lists every
rule (with zero clause counts) and detail returns no clause text.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.bilun.api.schemas import (
    ProseInventoryResponse,
    RuleCatalogResponse,
    RuleDetailResponse,
    SectionRollupResponse,
)
from src.bilun.domain.sut import rules_catalog
from src.bilun.shared.exceptions import NotFoundError, ValidationError

router = APIRouter()

_MAX_PER_PAGE = 200
_DEFAULT_PER_PAGE = 50


@router.get("/rules", response_model=RuleCatalogResponse)
def get_rule_catalog():
    """Catalog index of every SUT rule with sources, coverage status, and clause counts."""
    rules = rules_catalog.list_rules()
    return {
        "rules": rules,
        "total": len(rules),
        "artifacts_available": rules_catalog.artifacts_available(),
        "fact_check": rules_catalog.fact_check_summary(),
        "coverage_summary": rules_catalog.coverage_summary(),
    }


@router.get("/rules/sections", response_model=SectionRollupResponse)
def get_rule_sections(
    page: int = 1,
    per_page: int = _DEFAULT_PER_PAGE,
    q: str | None = None,
    min_gap_count: int | None = None,
):
    """Paginated SUT section rollup with coverage gap counts (expert surface)."""
    if page < 1:
        raise ValidationError("page must be >= 1", page=page)
    if per_page < 1 or per_page > _MAX_PER_PAGE:
        raise ValidationError(
            f"per_page must be between 1 and {_MAX_PER_PAGE}", per_page=per_page
        )
    if min_gap_count is not None and min_gap_count < 0:
        raise ValidationError(
            "min_gap_count must be >= 0", min_gap_count=min_gap_count
        )

    return rules_catalog.list_sections(
        page=page,
        per_page=per_page,
        query=q,
        min_gap_count=min_gap_count,
    )


@router.get("/rules/prose-inventory", response_model=ProseInventoryResponse)
def get_prose_inventory():
    """Manifest of prose rule engines under ``data/gazette/prose_rules`` (expert surface)."""
    return rules_catalog.prose_inventory()


@router.get("/rules/{rule_id}", response_model=RuleDetailResponse)
def get_rule_detail(rule_id: str, page: int = 1, per_page: int = 50):
    """Rule metadata + paginated extracted SUT clause text (the rule's sources)."""
    if not rules_catalog.rule_exists(rule_id):
        raise NotFoundError(f"Unknown SUT rule_id: {rule_id}", rule_id=rule_id)

    if page < 1:
        raise ValidationError("page must be >= 1", page=page)
    if per_page < 1 or per_page > _MAX_PER_PAGE:
        raise ValidationError(
            f"per_page must be between 1 and {_MAX_PER_PAGE}", per_page=per_page
        )

    summary = next(
        (r for r in rules_catalog.list_rules() if r["rule_id"] == rule_id), None
    )

    offset = (page - 1) * per_page
    clauses, clause_total = rules_catalog.get_rule_clauses(
        rule_id, limit=per_page, offset=offset
    )
    total_pages = (clause_total + per_page - 1) // per_page if clause_total else 0

    return {
        "rule": summary,
        "clauses": clauses,
        "clause_total": clause_total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "artifacts_available": rules_catalog.artifacts_available(),
    }
