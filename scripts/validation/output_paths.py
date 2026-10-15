"""Where the ILAY validation harness keeps its outputs: never inside this repo.

The harness outputs are derived from real ILAY hospital prescriptions; the
violation logs carry pseudonymized patient and visit IDs. Under KVKK they stay
outside every repository, in ``$BILUN_ILAY_VALIDATION_DIR`` (default
``~/bilun-local/ilay-validation``). See
``plans/security/2026-10-14-remove-ilay-real-data-plan.md``.
"""

from __future__ import annotations

import os
from pathlib import Path

BILUN_ROOT = Path(__file__).resolve().parents[2]
ENV_VAR = "BILUN_ILAY_VALIDATION_DIR"
DEFAULT_DIR = Path.home() / "bilun-local" / "ilay-validation"


def validation_root() -> Path:
    """Return the output root, refusing any location inside the Bilun repo."""
    raw = os.environ.get(ENV_VAR, "").strip()
    root = (Path(raw).expanduser() if raw else DEFAULT_DIR).resolve()
    if root == BILUN_ROOT or BILUN_ROOT in root.parents:
        raise SystemExit(
            f"{ENV_VAR}={root} is inside the Bilun repo; real-data outputs must "
            "stay outside every repository (KVKK)."
        )
    return root


def logs_dir() -> Path:
    """Violation logs and per-rule summaries."""
    return validation_root() / "ilay_validation"


def golden_dir() -> Path:
    """Golden JSON cases built from the violation logs (local use only)."""
    return validation_root() / "golden_ilay"
