"""EK-3C-1 material pre-authorization evaluator (Phase 3.4, rule "Encode 2").

This module exposes ``check_material_preauth_for_context(ctx)`` — a prose-rule
evaluator that flags material claim lines requiring medical-board
pre-authorization before SGK submission (SUT §3.1.2).

DESIGN DECISION (Phase 3.4 — option (b) over option (a))
-------------------------------------------------------
Two evaluator shapes were considered:

  (a) A NEW JSON rule set under ``data/gazette/prose_rules/`` mirroring the
      EK-3C-1 list as rules, plus a loader + membership check.
  (b) A direct membership check that reuses the EXISTING
      ``_get_ek3c1_preauth()`` parquet loader and iterates
      ``ctx.material_lines``.

Option (b) is chosen deliberately. The EK-3C-1 catalog IS the rule — it is a
closed membership list of SUT codes that require pre-auth. Re-encoding those
506 rows as a JSON rule set would duplicate the curated parquet verbatim and
create a second source of truth that can drift from the gazette curation.
The "JSON-rule-driven" intent of the roadmap is satisfied by treating the
loader output as the rule set: the EK-3C-1 list is the rule, and the
membership test (``code in preauth_codes``) is the generic evaluator.

This mirrors how ``claim_materials.precheck_materials_from_claims`` already
consumes the loader at ``claim_materials.py:142-181`` (membership test plus
the per-line ``requires_pre_auth`` OR-branch). The evaluator here surfaces the
SAME finding as a stand-alone violation dict so it can be wired into
``analyze_claim`` like the §3.1/§3.3 prose engines, without touching the
shared ``claim_materials.py`` pipeline.

Severity is ``"warning"`` — pre-auth is a *review flag*, not a hard denial: a
missing board decision blocks submission but does not, on its own, establish
that the material is non-reimbursable.
"""

from __future__ import annotations

from typing import Any

from src.bilun.domain.billing.materials import _get_ek3c1_preauth

# SUT section this rule belongs to (mirrors the bundling/exclusion engines).
_SUT_SECTION = "3.1.2"

# Re-stated locally so the message is stable even if the shared note string
# in claim_materials.py is reworded (that file is shared/read-only).
_MESSAGE = (
    "EK-3C-1 — tıbbi uygunluk (medical appropriateness) required before SGK "
    "submission (§3.1.2)"
)


def _preauth_codes() -> dict[str, dict[str, Any]]:
    """Materialize the EK-3C-1 catalog as a {sut_code: entry} lookup.

    Mirrors the membership index built at ``claim_materials.py:142`` so this
    evaluator and the shared pre-check agree on exactly the same code set.
    """
    return {item["sut_code"]: item for item in _get_ek3c1_preauth()}


def check_material_preauth_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Flag material lines that require EK-3C-1 pre-authorization.

    A line is flagged when EITHER holds (mirroring the OR-branch at
    ``claim_materials.py:167``):

      * its ``material_code`` is a member of the EK-3C-1 catalog, OR
      * its ``requires_pre_auth`` flag is ``True`` (per-line override set by
        the upstream parser/enricher).

    Returns one violation dict per flagged line. Pre-auth is a review flag,
    not a hard denial, so ``severity`` is ``"warning"`` and ``savings_try`` is
    ``0.0`` (no deterministic recovery until the board decision is known).
    """
    violations: list[dict[str, Any]] = []
    if not getattr(ctx, "material_lines", ()):
        return violations

    preauth_codes = _preauth_codes()

    for line in ctx.material_lines:
        code = str(getattr(line, "material_code", "") or "").strip()
        requires_pre_auth = bool(getattr(line, "requires_pre_auth", False))

        in_catalog = bool(code) and code in preauth_codes
        if not in_catalog and not requires_pre_auth:
            continue

        catalog_entry = preauth_codes.get(code, {})
        material_name = (
            str(getattr(line, "material_name", "") or "").strip()
            or str(catalog_entry.get("material_name", "") or "").strip()
            or code
            or "—"
        )
        billed = float(getattr(line, "billed_amount_try", 0.0) or 0.0)

        reason = "catalog_membership" if in_catalog else "line_flag"
        violations.append(
            {
                "rule": "material_preauth_ek3c1",
                "severity": "warning",
                "material_name": material_name,
                "material_code": code,
                "message": _MESSAGE,
                "savings_try": 0.0,
                "risk_amount": billed,
                "sut_section": _SUT_SECTION,
                "rule_id": "ek3c1_preauth_required",
                "material_outcome": "review_required",
                "claim_id": getattr(line, "claim_id", None),
                "details": {
                    "source": reason,
                    "requires_pre_auth_flag": requires_pre_auth,
                    "in_ek3c1_catalog": in_catalog,
                },
            }
        )

    return violations
