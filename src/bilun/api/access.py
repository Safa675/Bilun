"""Trusted identities and an explicit method/route permission registry.

Display preferences are deliberately absent from this boundary. A new route is
unavailable until it is classified here, even to an authenticated developer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from starlette.requests import Request

from .auth import COOKIE_NAME, resolve_user_role

Access = Literal["public", "billing", "developer"]


def is_public_billing_enabled() -> bool:
    return os.getenv("BILUN_PUBLIC_BILLING_ENABLED", "").strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Identity:
    authenticated: bool = False
    username: str | None = None
    role: str = "billing_officer"
    capabilities: tuple[str, ...] = ()
    expires_at: int | None = None


def identity_from_request(request: Request) -> Identity:
    cached = getattr(request.state, "bilun_identity", None)
    if isinstance(cached, Identity):
        return cached
    import src.bilun.api as _api
    claims = _api.verify_session_token(request.cookies.get(COOKIE_NAME, ""))
    username = claims.username if hasattr(claims, "username") else (claims if isinstance(claims, str) else None)
    role = resolve_user_role(username)
    capabilities = ("billing", "developer", "repository") if claims and role == "dev" else (
        ("billing",) if claims or is_public_billing_enabled() else ()
    )
    expires_at = getattr(claims, "expires_at", None)
    return Identity(
        authenticated=claims is not None,
        username=username,
        role=role,
        capabilities=capabilities,
        expires_at=expires_at,
    )


def has_developer_access(identity: Identity) -> bool:
    return identity.authenticated and "developer" in identity.capabilities


ROUTE_POLICY: dict[tuple[str, str], Access] = {}


def _register(access: Access, method: str, *paths: str) -> None:
    for path in paths:
        ROUTE_POLICY[(method, path)] = access


_register("public", "GET", "/health", "/api/auth/me")
_register("public", "POST", "/api/auth/login", "/api/auth/logout")
_register(
    "billing", "GET",
    "/api/patients", "/api/patients/search", "/api/patient/{patient_id}/outcome",
    "/api/patients/{patient_id}/claims", "/api/patients/{patient_id}/claims/{claim_id}",
    "/api/billing-report/{patient_id}", "/api/billing-report/{patient_id}/bills/{claim_id}",
    "/api/patient/{patient_id}/optimization",
    "/api/patient/{patient_id}/bills/{claim_id}/optimization",
    "/api/optimization-summary", "/api/revenue-recovery", "/api/patient-alerts",
    "/api/compliance-index", "/api/medula-rejections/ingest-status", "/api/medula-rejections/queue",
    "/api/procedure/{code}", "/api/material/{code}/pricing", "/api/visit-pricing",
    "/api/price-history/{code}", "/api/lab-prices", "/api/drugs", "/api/materials/by-specialty",
    "/api/bundled-consumables", "/api/rules/clauses/{clause_id}",
    "/api/wavea-evidence-index", "/api/wavea-evidence/{patient_id}", "/api/wavea-evidence-rows",
)
_register(
    "billing", "POST", "/api/compliance-index", "/api/wavea-evidence-index",
    "/api/wavea-evidence-rows", "/api/validate-claim", "/api/chat",
)
_register(
    "developer", "GET", "/api/rules", "/api/rules/{rule_id}", "/api/rules/sections",
    "/api/rules/sections/clauses", "/api/rules/prose-inventory",
    "/api/rules/prose-rules/{rule_set_id}", "/api/rules/prose-rules/{rule_set_id}/{rule_id}",
    "/api/rules/deferrals", "/api/rules/clauses", "/docs", "/docs/oauth2-redirect",
    "/redoc", "/openapi.json",
)
_register("developer", "POST", "/api/validate-claim/legacy", "/api/weekly-brief")
_register("developer", "HEAD", "/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json")
