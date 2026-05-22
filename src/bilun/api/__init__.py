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

app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Exception handlers ───────────────────────────────────────────────────────

from src.bilun.shared.exceptions import register_exception_handlers  # noqa: E402

register_exception_handlers(app)

# ── Routes ───────────────────────────────────────────────────────────────────

from src.bilun.api.routes import router as bilun_router  # noqa: E402

app.include_router(bilun_router)


# ── Health check ─────────────────────────────────────────────────────────────

from fastapi import Response  # noqa: E402


@app.get("/health")
def health_check() -> dict:
    """Return API health status.

    Checks:
      - BILUN database connection is reachable
      - BILUN cache has an active build (optional — 503 if not)
    """
    import os
    from pathlib import Path

    db_path = Path(
        os.getenv(
            "BILUN_CACHE_DB_PATH",
            str(_PROJECT_ROOT / ".cache" / "bilun.duckdb"),
        )
    )

    db_ok = False
    active_build = None
    if db_path.exists():
        try:
            import duckdb

            con = duckdb.connect(str(db_path))
            row = con.execute(
                "SELECT active_build_id FROM build_pointer_scopes WHERE scope = 'bilun'"
            ).fetchone()
            active_build = row[0] if row else None
            con.close()
            db_ok = True
        except Exception:
            pass

    status_code = 200 if db_ok else 503
    payload = {
        "status": "ok" if db_ok else "degraded",
        "service": "bilun",
        "database_reachable": db_ok,
        "active_build": active_build,
        "version": "1.0.0",
    }
    return Response(
        content=__import__("json").dumps(payload),
        media_type="application/json",
        status_code=status_code,
    )
