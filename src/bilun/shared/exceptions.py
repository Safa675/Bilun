"""Domain-level API exceptions and the global handler for BILUN.

Defines a small ``BilunAPIError`` hierarchy so endpoint code can raise semantic
errors (``PatientNotFound``, ``NotFoundError``) instead of building an
``HTTPException`` with a hand-rolled detail dict at every site.

Wire-up:
    from src.bilun.shared.exceptions import BilunAPIError, register_exception_handlers
    register_exception_handlers(app)

Wire format (consistent across all subclasses)::

    {
        "error":   "<error_code>",       # short machine-readable slug
        "message": "<human message>",
        "context": { ...optional fields... },
    }
"""

from __future__ import annotations

from typing import Any

import duckdb
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class BilunAPIError(Exception):
    """Base class for BILUN API errors.

    Subclasses set ``status_code`` and ``error_code`` as class attributes.
    The instance carries a human ``message`` and an optional ``context``
    dict for additional fields the client may want.
    """

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = context


class PatientNotFound(BilunAPIError):
    """Raised when a patient_id has no record in the active scored data."""

    status_code = 404
    error_code = "patient_not_found"


class NotFoundError(BilunAPIError):
    """Generic 404 for non-patient resources (procedure codes, cached
    payloads, gazette artifacts, etc.). Use ``PatientNotFound`` for
    patient-id lookups specifically."""

    status_code = 404
    error_code = "not_found"


class ValidationError(BilunAPIError):
    """Raised when request input fails domain-level validation.

    Maps to HTTP 400 (Bad Request).
    """

    status_code = 400
    error_code = "validation_error"


class ServiceUnavailableError(BilunAPIError):
    """Generic 503 — a downstream artifact, model, or service isn't ready."""

    status_code = 503
    error_code = "service_unavailable"


class RateLimitError(BilunAPIError):
    """Raised when a per-client rate limit has been exceeded (429)."""

    status_code = 429
    error_code = "rate_limit_exceeded"


# ------------------------------------------------------------------
# Wire-up
# ------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Register the single BilunAPIError handler on the FastAPI app."""

    @app.exception_handler(BilunAPIError)
    async def _api_error_handler(_request: Request, exc: BilunAPIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "context": exc.context,
            },
        )

    @app.exception_handler(duckdb.IOException)
    async def _duckdb_io_error_handler(_request: Request, exc: duckdb.IOException) -> JSONResponse:
        message = str(exc)
        if "Could not set lock on file" in message:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "service_unavailable",
                    "message": (
                        "BILUN cache database is currently locked by another process. "
                        "Stop duplicate backend/cache-builder processes and retry."
                    ),
                    "context": {"detail": message},
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": message,
                "context": {},
            },
        )
