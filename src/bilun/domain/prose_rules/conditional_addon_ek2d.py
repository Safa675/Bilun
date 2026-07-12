"""EK-2/D conditional add-on billing detector (SUT EK-2/D-4 & EK-2/D-5).

Two intraoperative add-on procedures are **separately billable only when the
primary surgical procedure performed in the same claim/session is on the
matching EK-2/D allow-list**:

* ``P703365`` — *İntraoperatif nöromonitorizasyon* — allowed only when a
  procedure on the **EK-2/D-4** list (67 procedures, sourced from
  ``data/gazette/snapshots/asof_2026-01-31/EK-2D-4.parquet``) is also billed.
* ``P614981`` — *İntraoperatif nöronavigasyon* — allowed only when a
  procedure on the **EK-2/D-5** list (29 procedures, sourced from
  ``data/gazette/prose_rules/ek2d5_neuronavigation_codes.json``) is also billed.

When the add-on is billed but **no** qualifying primary procedure from the
relevant list is present on the same claim, the add-on is over-billed and a
violation/opportunity is emitted.

The detector mirrors the shape of other prose-rule evaluators (see
``anestezi_puani.py`` and ``procedure_addon_uplift.py``): it takes a flat
``claims`` list and ``procedure_lines`` list, groups lines by claim, and for
each qualifying add-on line checks whether any sibling line on the same claim
is on the required allow-list.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from src.bilun.domain.constants import _PROSE_RULES_DIR, _PROJECT_ROOT
from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_AUDIT_EXPOSURE,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

# ─── Add-on procedure codes ──────────────────────────────────────────────────
# P703365 — İntraoperatif nöromonitorizasyon (EK-2/D-4 gated)
_NEUROMONITORING_CODE = normalize_procedure_code("P703365")
# P614981 — İntraoperatif nöronavigasyon (EK-2/D-5 gated)
_NEURONAVIGATION_CODE = normalize_procedure_code("P614981")

_OPPORTUNITY_TYPE = "conditional_addon_ek2d"
_RULE_SET_ID = "conditional_addon_ek2d"
_RULE_ID_D4 = "conditional_addon_ek2d_neuromonitoring"
_RULE_ID_D5 = "conditional_addon_ek2d_neuronavigation"
_SUT_SECTION_ID = "EK-2/D"

# D-4 snapshot path (EK-2/D-4 procedures permitting separate neuromonitoring).
# Resolves dynamically to the latest asof snapshot directory.


def _resolve_latest_snapshot_dir() -> Path:
    """Find the latest asof snapshot directory under data/gazette/snapshots/."""
    snapshots_root = _PROJECT_ROOT / "data" / "gazette" / "snapshots"
    if not snapshots_root.exists():
        return snapshots_root / "asof_2026-01-31"
    asof_dirs = sorted(
        d for d in snapshots_root.iterdir() if d.is_dir() and d.name.startswith("asof_")
    )
    return asof_dirs[-1] if asof_dirs else snapshots_root / "asof_2026-01-31"


_D4_PARQUET_PATH = _resolve_latest_snapshot_dir() / "EK-2D-4.parquet"
# D-5 seed path (EK-2/D-5 procedures permitting separate neuronavigation).
_D5_SEED_PATH = _PROSE_RULES_DIR / "ek2d5_neuronavigation_codes.json"


# ─── D-4 loader (parquet) ────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def load_ek2d4_code_set() -> frozenset[str]:
    """Return the normalized EK-2/B codes from the EK-2/D-4 parquet snapshot.

    The parquet stores the procedures with EK-2/B codes in the ``Unnamed: 1``
    column; the header row is skipped. Returns an empty set when the file is
    missing or unreadable (honest skip — detector emits nothing).
    """
    if not _D4_PARQUET_PATH.is_file():
        return frozenset()
    try:
        import polars as pl

        df = pl.read_parquet(_D4_PARQUET_PATH)
    except Exception:
        return frozenset()

    ek2b_col = "Unnamed: 1"
    if ek2b_col not in df.columns:
        return frozenset()

    rows = df.filter(
        df[ek2b_col].is_not_null() & (df[ek2b_col] != "EK-2/B Kodu")
    )
    codes: set[str] = set()
    for value in rows[ek2b_col].to_list():
        normalized = normalize_procedure_code(str(value))
        if normalized:
            codes.add(normalized)
    return frozenset(codes)


# ─── D-5 loader (JSON seed) ──────────────────────────────────────────────────
@lru_cache(maxsize=1)
def load_ek2d5_code_set() -> frozenset[str]:
    """Return the normalized EK-2/B codes from the EK-2/D-5 JSON seed.

    Follows the pattern of ``ek2c_prose_drg_locked.load_prose_drg_locked_code_set``.
    """
    if not _D5_SEED_PATH.is_file():
        return frozenset()
    try:
        payload = json.loads(_D5_SEED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    raw = payload.get("normalized_codes") or []
    return frozenset(
        normalize_procedure_code(str(code)) for code in raw if str(code).strip()
    ) - {""}


# ─── Detector ────────────────────────────────────────────────────────────────
def detect_conditional_addon_ek2d_opportunities(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    """Detect EK-2/D conditional add-on procedures billed without a qualifying primary.

    For each procedure line that is one of the gated add-ons (P703365
    neuromonitoring or P614981 neuronavigation), checks whether ANY sibling
    procedure line on the same claim is on the corresponding allow-list
    (EK-2/D-4 or EK-2/D-5). If not, the add-on was billed without a
    qualifying primary procedure → emit a violation.

    Skipped (honest, no violation emitted):
      - No gated add-on lines present.
      - Add-on line present but a qualifying primary is also billed.
      - Empty allow-lists (missing data files → detector emits nothing).

    Args:
        claims: ClaimHeaders to evaluate.
        procedure_lines: Procedure claim lines to evaluate against.

    Returns:
        Opportunity/violation dicts carrying: type, claim_id, rule_id, detail,
        sut_section_id, savings_category, savings_basis (plus add-on-specific
        fields).
    """
    if not procedure_lines:
        return []

    d4_codes = load_ek2d4_code_set()
    d5_codes = load_ek2d5_code_set()
    # If neither list loaded, there is nothing to enforce.
    if not d4_codes and not d5_codes:
        return []

    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}

    # Group procedure lines by claim_id once.
    lines_by_claim: dict[str, list[ProcedureClaimLine]] = {}
    for line in procedure_lines:
        lines_by_claim.setdefault(line.claim_id, []).append(line)

    opportunities: list[dict[str, Any]] = []

    for claim_id, claim_lines in lines_by_claim.items():
        claim = claims_by_id.get(claim_id)
        if claim is None:
            # Lines without a matching claim header cannot be evaluated.
            continue

        # Pre-compute normalized sibling codes once per claim.
        sibling_codes: set[str] = {
            normalize_procedure_code(line.procedure_code) for line in claim_lines
        }

        for line in claim_lines:
            code = normalize_procedure_code(line.procedure_code)

            # ── P703365: neuromonitoring gated by EK-2/D-4 ─────────────────
            if code == _NEUROMONITORING_CODE and d4_codes:
                # A qualifying primary is any OTHER line on the same claim
                # (the add-on itself is never on D-4) whose code is in D-4.
                if not (sibling_codes - {code}) & d4_codes:
                    opportunities.append(
                        _build_violation(
                            claim=claim,
                            line=line,
                            addon_code=_NEUROMONITORING_CODE,
                            list_name="EK-2/D-4",
                            rule_id=_RULE_ID_D4,
                        )
                    )

            # ── P614981: neuronavigation gated by EK-2/D-5 ─────────────────
            if code == _NEURONAVIGATION_CODE and d5_codes:
                if not (sibling_codes - {code}) & d5_codes:
                    opportunities.append(
                        _build_violation(
                            claim=claim,
                            line=line,
                            addon_code=_NEURONAVIGATION_CODE,
                            list_name="EK-2/D-5",
                            rule_id=_RULE_ID_D5,
                        )
                    )

    return opportunities


def _build_violation(
    *,
    claim: ClaimHeader,
    line: ProcedureClaimLine,
    addon_code: str,
    list_name: str,
    rule_id: str,
) -> dict[str, Any]:
    """Construct one violation/opportunity dict for a mis-billed conditional add-on."""
    addon_name_tr = {
        _NEUROMONITORING_CODE: "İntraoperatif nöromonitorizasyon",
        _NEURONAVIGATION_CODE: "İntraoperatif nöronavigasyon",
    }.get(addon_code, addon_code)

    detail = (
        f"{addon_code} ({addon_name_tr}) ayrıca faturalanmıştır, ancak aynı "
        f"talepte {list_name} listesindeki hiçbir esas işlem bulunmamaktadır. "
        f"Bu ek işlem yalnızca {list_name} listesindeki bir işlemle birlikte "
        f"yapıldığında ayrıca faturalanabilir (EK-2/D)."
    )

    return {
        "type": _OPPORTUNITY_TYPE,
        "claim_id": claim.claim_id,
        "procedure_line_id": line.procedure_line_id,
        "procedure_code": addon_code,
        "procedure_name": line.procedure_name or addon_name_tr,
        "addon_code": addon_code,
        "required_list": list_name,
        "rule_id": rule_id,
        "rule_set_id": _RULE_SET_ID,
        "sut_section_id": _SUT_SECTION_ID,
        "savings_category": SAVINGS_CATEGORY_AUDIT_EXPOSURE,
        "savings_basis": SAVINGS_BASIS_SOURCED,
        "detail": detail,
    }
