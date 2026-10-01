"""BILUN API — FastAPI application factory.

Creates the app, registers middleware, includes all BILUN route modules,
and wires up startup/shutdown events.

Usage:
    uvicorn src.bilun.api:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Ensure project root is on sys.path so ``from src import ...`` works
# when uvicorn is invoked as ``uvicorn src.bilun.api:app``.
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

import logging as _logging

_api_logger = _logging.getLogger("bilun.api")

from src.bilun.api import release_identity as _release_identity  # noqa: E402


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    try:
        from src.bilun.api.startup import startup as _startup_handler  # noqa: E402
    except Exception as _e:
        _api_logger.warning("Startup handler skipped: %s", _e)
        yield
        return

    await _startup_handler()
    yield


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="BILUN API", version="1.0.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Session gate and final public JSON boundary ───────────────────────────────
from src.bilun.api.access_middleware import SessionGateMiddleware  # noqa: E402

app.add_middleware(SessionGateMiddleware)
# Compression wraps the access layer: projection sees uncompressed JSON, and
# every explicit JSONResponse/error follows the same final public contract.
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Exception handlers ───────────────────────────────────────────────────────

from src.bilun.shared.exceptions import register_exception_handlers  # noqa: E402

register_exception_handlers(app)

# ── Routes ───────────────────────────────────────────────────────────────────

from src.bilun.api.routes import router as bilun_router  # noqa: E402

app.include_router(bilun_router)


# ── Health check ─────────────────────────────────────────────────────────────

from fastapi import Request, Response  # noqa: E402


@app.get("/health")
def health_check(request: Request = None) -> Response:
    """Return API health status.

    Checks:
      - BILUN database connection is reachable
      - BILUN cache has an active build and startup reported cache_ready
      - Active gazette version is surfaced for staleness visibility

    Returns HTTP 503 when the database is unreachable, there is no active
    build, or startup did not complete successfully.
    """
    import os
    from contextlib import closing
    from pathlib import Path

    db_path = Path(
        os.getenv(
            "BILUN_CACHE_DB_PATH",
            str(_PROJECT_ROOT / ".cache" / "bilun.duckdb"),
        )
    )

    db_ok = False
    active_build = None
    wavea_capability = None
    if db_path.exists():
        # Use closing() so the connection is released even if execute() raises
        # (audit H16: previously con.close() was only reached on the success
        # path, leaking a handle per /health probe on the error path).
        try:
            import duckdb

            with closing(duckdb.connect(str(db_path), read_only=True)) as con:
                row = con.execute(
                    "SELECT active_build_id FROM build_pointer_scopes WHERE scope = 'bilun'"
                ).fetchone()
                active_build = row[0] if row else None
                if active_build is not None:
                    try:
                        capability = con.execute(
                            "SELECT json_extract_string(payload_json, '$.capability') "
                            "FROM wavea_evidence_index WHERE build_id = ?",
                            [active_build],
                        ).fetchone()
                        wavea_capability = capability[0] if capability else None
                    except Exception:
                        # Older caches have no Wave A index. The existing
                        # database readiness contract still applies to them.
                        pass
            db_ok = True
        except Exception:
            pass

    # Surface the active gazette version (B-C7: staleness visibility).
    # The manifest's max effective_date is recomputed live so an operator
    # can compare it against what the running build expects. Full source-hash
    # comparison is a follow-up; this at least makes a stale gazette visible.
    active_gazette_version = _read_active_gazette_version_for_health()

    from src.bilun.api.startup import is_cache_ready  # noqa: E402

    cache_ready = is_cache_ready()
    wavea_receipt_sha256 = None
    if cache_ready and active_build is not None and wavea_capability == "draft":
        from src.bilun.api.wavea_activation import activation_for_build

        activation = activation_for_build(active_build)
        if activation is not None:
            wavea_capability = "complete-25-v1"
            wavea_receipt_sha256 = activation.receipt_sha256
    service_ready = db_ok and active_build is not None and cache_ready
    status_code = 200 if service_ready else 503
    status_label = "ok" if service_ready else "degraded"
    payload = {
        "status": status_label,
        "service": "bilun",
        "database_reachable": db_ok,
        "cache_ready": cache_ready,
        "active_build": active_build,
        "code_sha": (
            _release_identity.STARTUP_RELEASE_IDENTITY.code_sha
            if _release_identity.STARTUP_RELEASE_IDENTITY is not None
            else None
        ),
        "source_manifest_sha256": (
            _release_identity.STARTUP_RELEASE_IDENTITY.source_manifest_sha256
            if _release_identity.STARTUP_RELEASE_IDENTITY is not None
            else None
        ),
        "wavea_capability": wavea_capability,
        "active_gazette_version": active_gazette_version,
        "version": "1.0.0",
    }
    if wavea_receipt_sha256 is not None:
        payload["wavea_receipt_sha256"] = wavea_receipt_sha256
    # Direct Python callers are internal release-identity tests. Every HTTP
    # request gets an injected Request and must authenticate for detail.
    if request is not None:
        from src.bilun.api.health_access import health_details_allowed

        if not health_details_allowed(request):
            payload = {
                key: payload[key]
                for key in ("status", "service", "database_reachable", "cache_ready")
            }
    return Response(
        content=__import__("json").dumps(payload),
        media_type="application/json",
        status_code=status_code,
        headers={"Cache-Control": "private, no-store", "Vary": "Cookie, X-Bilun-Health-Token"},
    )


def _read_active_gazette_version_for_health() -> str | None:
    """Best-effort read of the manifest's latest effective_date.

    Returns None on any failure (missing manifest, parse error) so /health
    never 500s purely because the gazette manifest is unreadable.
    """
    import os
    from pathlib import Path

    try:
        import pandas as pd

        manifest = Path(
            os.getenv(
                "BILUN_GAZETTE_MANIFEST",
                str(_PROJECT_ROOT / "data" / "gazette" / "version_manifest.parquet"),
            )
        )
        if not manifest.exists():
            return None
        df = pd.read_parquet(manifest)
        latest = df["effective_date"].max()
        if latest is None or str(latest) == "nan":
            return None
        return str(latest)
    except Exception:
        return None
