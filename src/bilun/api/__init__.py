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
      - Active gazette version is surfaced for staleness visibility
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
    if db_path.exists():
        # Use closing() so the connection is released even if execute() raises
        # (audit H16: previously con.close() was only reached on the success
        # path, leaking a handle per /health probe on the error path).
        try:
            import duckdb

            with closing(duckdb.connect(str(db_path))) as con:
                row = con.execute(
                    "SELECT active_build_id FROM build_pointer_scopes "
                    "WHERE scope = 'bilun'"
                ).fetchone()
                active_build = row[0] if row else None
            db_ok = True
        except Exception:
            pass

    # Surface the active gazette version (B-C7: staleness visibility).
    # The manifest's max effective_date is recomputed live so an operator
    # can compare it against what the running build expects. Full source-hash
    # comparison is a follow-up; this at least makes a stale gazette visible.
    active_gazette_version = _read_active_gazette_version_for_health()

    status_code = 200 if db_ok else 503
    payload = {
        "status": "ok" if db_ok else "degraded",
        "service": "bilun",
        "database_reachable": db_ok,
        "active_build": active_build,
        "active_gazette_version": active_gazette_version,
        "version": "1.0.0",
    }
    return Response(
        content=__import__("json").dumps(payload),
        media_type="application/json",
        status_code=status_code,
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
