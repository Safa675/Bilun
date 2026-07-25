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
    DeferralListResponse,
    ProseInventoryResponse,
    ProseRuleSourcesResponse,
    ProseRulesSourcesListResponse,
    RuleCatalogResponse,
    RuleClause,
    RuleDetailResponse,
    SectionClausesResponse,
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
    consolidate: bool = False,
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
        consolidate=consolidate,
    )


@router.get("/rules/sections/clauses", response_model=SectionClausesResponse)
def get_section_clauses(
    section_id: str,
    section_title: str | None = None,
    page: int = 1,
    per_page: int = 50,
):
    """In-force SUT clauses for one section (drill-down from the section rollup)."""
    if page < 1:
        raise ValidationError("page must be >= 1", page=page)
    if per_page < 1 or per_page > _MAX_PER_PAGE:
        raise ValidationError(
            f"per_page must be between 1 and {_MAX_PER_PAGE}", per_page=per_page
        )

    offset = (page - 1) * per_page
    clauses, clause_total = rules_catalog.list_section_clauses(
        section_id,
        section_title,
        limit=per_page,
        offset=offset,
    )
    total_pages = (clause_total + per_page - 1) // per_page if clause_total else 0

    return {
        "clauses": clauses,
        "clause_total": clause_total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "artifacts_available": rules_catalog.artifacts_available(),
    }


@router.get("/rules/prose-inventory", response_model=ProseInventoryResponse)
def get_prose_inventory():
    """Manifest of prose rule engines under ``data/gazette/prose_rules`` (expert surface)."""
    return rules_catalog.prose_inventory()


@router.get(
    "/rules/prose-rules/{rule_set_id}",
    response_model=ProseRulesSourcesListResponse,
)
def list_prose_rule_sources(
    rule_set_id: str,
    page: int = 1,
    per_page: int = _DEFAULT_PER_PAGE,
):
    """Prose JSON rules with ``gate_b_sources`` resolved to coordinates + snippets."""
    if page < 1:
        raise ValidationError("page must be >= 1", page=page)
    if per_page < 1 or per_page > _MAX_PER_PAGE:
        raise ValidationError(
            f"per_page must be between 1 and {_MAX_PER_PAGE}", per_page=per_page
        )
    offset = (page - 1) * per_page
    payload = rules_catalog.list_prose_rules_with_gate_b_sources(
        rule_set_id, limit=per_page, offset=offset
    )
    if payload is None:
        raise NotFoundError(f"Unknown prose rule_set_id: {rule_set_id}", rule_set_id=rule_set_id)
    total = int(payload.get("total") or 0)
    total_pages = (total + per_page - 1) // per_page if total else 0
    return {
        **payload,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


@router.get(
    "/rules/prose-rules/{rule_set_id}/{rule_id}",
    response_model=ProseRuleSourcesResponse,
)
def get_prose_rule_sources(rule_set_id: str, rule_id: str):
    """One prose rule's ``gate_b_sources`` as coordinates + text snippets."""
    detail = rules_catalog.resolve_prose_rule_gate_b_sources(rule_set_id, rule_id)
    if detail is None:
        raise NotFoundError(
            f"Unknown prose rule: {rule_set_id}/{rule_id}",
            rule_set_id=rule_set_id,
            rule_id=rule_id,
        )
    return detail


@router.get("/rules/deferrals", response_model=DeferralListResponse)
def list_deferrals(
    q: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = _DEFAULT_PER_PAGE,
):
    """Deferral-table review rows keyed by coordinate when known (Track D)."""
    if page < 1:
        raise ValidationError("page must be >= 1", page=page)
    if per_page < 1 or per_page > _MAX_PER_PAGE:
        raise ValidationError(
            f"per_page must be between 1 and {_MAX_PER_PAGE}", per_page=per_page
        )
    offset = (page - 1) * per_page
    rows, total = rules_catalog.list_deferrals(
        q=q, status=status, limit=per_page, offset=offset
    )
    total_pages = (total + per_page - 1) // per_page if total else 0
    return {
        "deferrals": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "artifacts_available": rules_catalog.artifacts_available(),
    }


@router.get("/rules/clauses", response_model=SectionClausesResponse)
def list_all_clauses(
    q: str | None = None,
    page: int = 1,
    per_page: int = 50,
    coverage_status: str | None = None,
    has_gap: bool | None = None,
    has_encoding: bool | None = None,
    primary_rule_id: str | None = None,
    exclude_non_algorithmic: bool = False,
    exclude_headings: bool = False,
):
    """Search across all in-force SUT clauses (global Hükümler browser)."""
    if page < 1:
        raise ValidationError("page must be >= 1", page=page)
    if per_page < 1 or per_page > _MAX_PER_PAGE:
        raise ValidationError(
            f"per_page must be between 1 and {_MAX_PER_PAGE}", per_page=per_page
        )

    offset = (page - 1) * per_page
    clauses, clause_total = rules_catalog.list_clauses(
        q=q,
        coverage_status=coverage_status,
        has_gap=has_gap,
        has_encoding=has_encoding,
        primary_rule_id=primary_rule_id,
        exclude_non_algorithmic=exclude_non_algorithmic,
        exclude_headings=exclude_headings,
        limit=per_page,
        offset=offset,
    )
    total_pages = (clause_total + per_page - 1) // per_page if clause_total else 0

    return {
        "clauses": clauses,
        "clause_total": clause_total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "artifacts_available": rules_catalog.artifacts_available(),
    }


@router.get("/rules/clauses/{clause_id}", response_model=RuleClause)
def get_single_clause(clause_id: str):
    """Single SUT clause by ``clause_id`` or unique ``clause_coordinate``."""
    clause = rules_catalog.get_clause(clause_id)
    if clause is None:
        raise NotFoundError(
            f"Unknown clause_id or clause_coordinate: {clause_id}",
            clause_id=clause_id,
        )
    return clause


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
