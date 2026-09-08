"""SUT build and gazette metadata for BILUN chatbot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST_PATH = _PROJECT_ROOT / "data" / "gazette" / "version_manifest.parquet"


def _read_active_gazette_version() -> str | None:
    """Return the latest effective_date from the gazette manifest, or None.

    The manifest is the source of truth for which SUT tebliği is active.
    Read defensively so a missing/corrupt manifest never breaks the chatbot.
    """
    try:
        df = pd.read_parquet(_MANIFEST_PATH)
        if "effective_date" not in df.columns:
            return None
        dates = df["effective_date"].dropna().astype(str)
        if dates.empty:
            return None
        latest = dates.max()
        return str(latest) if latest else None
    except Exception:
        return None


def get_chat_model_context(active_build_id: str | None = None) -> dict[str, Any]:
    """Return live SUT metadata for BILUN (no IHP ML artifact references)."""
    return {
        "product": "BILUN",
        "build_id": active_build_id,
        "gazette_version": _read_active_gazette_version(),
        "claim_dataset": "synthetic_demo",
        "rule_engines": {
            "active": ["copay_exemptions", "temporal_price_validation"],
            "gated": [
                "surcharge_eligibility",
                "copay_rate_eligibility",
                "drg_unbundling",
            ],
        },
        # The 17 per-patient billing analyzers assembled by
        # compute_patient_billing_report (src/bilun/domain/billing/patient_report.py).
        "billing_algorithms": [
            "lab",
            "copay",
            "strategy",
            "session_uplift",
            "drg_uplift",
            "blood_uplift",
            "material_uplift",
            "procedure_addon_uplift",
            "procedure_capture_gap",
            "drg_package_adequacy",
            "gazette_repricing",
            "medula_rejection_playbook",
            "claim_submission_checklist",
            "drug_indication",
            "care_setting_review",
            "materials_precheck",
            "audit_exposure",
        ],
    }
