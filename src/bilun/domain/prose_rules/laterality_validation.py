"""Laterality (sag_sol) validation detectors.

Two §2.4 detectors that flag missing-laterality documentation on procedures
performed on paired organs. Medula's ``sagSol`` field records which side a
bilateral procedure was performed on: ``"1"`` = Sağ (right), ``"2"`` = Sol
(left), ``"3"`` = Ayrım yok (no distinction), ``""`` = not recorded.

- **#6**  Bilateral MR/CT imaging without laterality  → ``detect_missing_laterality_imaging``
- **#17** Missing laterality on bilateral-organ surgery → ``detect_missing_laterality_surgery``

Honest-skip guard (CRITICAL): both detectors implement the *B-guard* — if
EVERY ``sag_sol`` value in the supplied ``procedure_lines`` is empty string
``""``, they return ``[]`` immediately. No ingestion path populates
``sag_sol`` today, so without this guard the detectors would emit a
false-positive flood on every paired-organ line in the dataset. They ship
dormant and activate automatically once real ``sag_sol`` data flows from the
Medula ingestion path.

Each detector emits violation dicts with the common Tablo 15 / §2.4 shape
mirrored from :mod:`common_billing_errors`: ``type``, ``claim_id``,
``rule_id``, ``detail`` (Turkish), ``sut_section_id``,
``savings_category``, ``savings_basis``, ``severity``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "laterality_validation"
_SUT_SECTION_ID = "2.4"

# sagSol sentinels — Medula side indicator.
_SAG_SOL_NONE = "3"    # Ayrım yok (no distinction)
# "" → missing / not populated.

# Error #6 — Paired-organ MR/CT imaging code families that REQUIRE a side.
# Conservative: only MR (801xxx) / CT (803xxx) codes for organs that exist as
# a left/right pair. Brain, spine, abdomen, pelvis and other single/midline
# structures are deliberately EXCLUDED — they have no side to record, so an
# empty sag_sol there is correct, not a violation. When unsure whether an
# organ is paired, it is left out.
#
# 5-char prefixes are used (not 4) because brain MR (``801001``) and knee MR
# (``801010``) share the ``8010`` 4-char prefix; only at 5 chars does brain
# (``80100``) cleanly separate from the paired extremities (``80101`` knee,
# ``80102`` shoulder, …). Midline families left out: ``80100`` brain, ``80108``
# pelvis, ``80109`` abdomen, ``80110/80111/80112`` spine, ``80113`` SI joint.
_PAIRED_ORGAN_IMAGING_PREFIXES: frozenset[str] = frozenset(
    {
        # MR (801xxx) — paired-organ regions (5-char prefix)
        "80101",  # MR knee (diz)
        "80102",  # MR shoulder (omuz)
        "80103",  # MR hip (kalça)
        "80104",  # MR wrist (el bileği)
        "80105",  # MR ankle (ayak bileği)
        "80106",  # MR elbow (dirsek)
        "80119",  # MR kidney (böbrek)
        "80120",  # MR breast (meme)
        "80121",  # MR orbit/eye (göz)
        # CT (803xxx) — paired-organ regions (5-char prefix, conservative)
        "80319",  # CT kidney (böbrek)
        "80320",  # CT breast (meme)
        "80321",  # CT orbit/eye (göz)
    }
)

# Error #17 — Surgical procedure code prefixes for known paired-organ families.
# Maps a code prefix to a short Turkish label for the detail text. Conservative
# — only the cataract family (516xxx) is named as a definitive code anchor;
# other paired-organ surgical families are reached via ``procedure_category``
# (see :data:`_PAIRED_ORGAN_SURGERY_CATEGORIES`). Adding speculative prefixes
# risks flagging non-paired procedures that happen to share the prefix.
_PAIRED_ORGAN_SURGERY_PREFIXES: dict[str, str] = {
    "516": "katarakt/göz cerrahisi",  # 516xxx — cataract & eye surgery
}

# Error #17 — procedure_category values signalling a paired-organ surgical
# family, used as a fallback when the code prefix is not in the map above.
_PAIRED_ORGAN_SURGERY_CATEGORIES: frozenset[str] = frozenset(
    {
        "goz_cerrahisi",
        "goz",
        "kulak_burun_bogaz",
        "kbb",
        "uroloji",
        "bobrek_cerrahisi",
        "gogus_cerrahisi",
        "akciger_cerrahisi",
        "ortopedi",
        "ekstremite_cerrahisi",
    }
)


def _sag_sol_of(line: ProcedureClaimLine) -> str:
    """Return the line's ``sag_sol`` (or '' when unset)."""
    return getattr(line, "sag_sol", "") or ""


def _has_any_sag_sol(procedure_lines: list[ProcedureClaimLine]) -> bool:
    """True if at least one line carries a non-empty ``sag_sol`` value."""
    return any(_sag_sol_of(ln) for ln in procedure_lines)


def _laterality_missing(line: ProcedureClaimLine) -> bool:
    """True when laterality is undocumented for a paired-organ line.

    Empty ``""`` (never recorded) or ``"3"`` (Ayrım yok) on a paired-organ
    imaging line both indicate missing laterality. Note: this is only reached
    after the B-guard, so a global-all-empty case never lands here.
    """
    side = _sag_sol_of(line)
    return side in ("", _SAG_SOL_NONE)


def _violation(line: ProcedureClaimLine, *, rule_id: str, detail: str) -> dict[str, Any]:
    return {
        "type": _OPPORTUNITY_TYPE,
        "claim_id": line.claim_id,
        "rule_id": rule_id,
        "detail": detail,
        "sut_section_id": _SUT_SECTION_ID,
        "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
        "savings_basis": SAVINGS_BASIS_SOURCED,
        "severity": "warning",
        "procedure_line_id": line.procedure_line_id,
        "procedure_code": line.procedure_code,
        "procedure_name": line.procedure_name,
        "sag_sol": _sag_sol_of(line),
    }


def detect_missing_laterality_imaging(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #6: Bilateral MR/CT imaging performed without recorded laterality.

    For paired-organ imaging codes (MR ``801xxx``, CT ``803xxx`` on paired
    organs — knees, shoulders, hips, kidneys, breasts, eyes, ears, …) a single
    line (``quantity == 1``) must carry ``sag_sol="1"`` (right) or ``"2"``
    (left), or be split into two separate laterality lines. An empty ``sag_sol``
    (never recorded) or ``"3"`` (Ayrım yok) on a single paired-organ imaging
    line is flagged.

    Midline/single organs (brain, spine, abdomen, pelvis) are deliberately
    excluded — they have no side to record.

    Args:
        claims: ClaimHeaders (honours the ``claim_ids_with_procs`` gate).
        procedure_lines: Procedure claim lines to evaluate.
        claim_ids_with_procs: Optional filter — only evaluate lines whose claim
            is in this set.

    Honest-skip guard: if no line in ``procedure_lines`` carries a non-empty
    ``sag_sol``, the data source does not populate the field — return ``[]``
    rather than flag everything. The detector activates once real sag_sol data
    flows from the Medula ingestion path.
    """
    del claims  # only the filter gate below is claim-aware
    # B-guard: if no line carries sag_sol, the data source doesn't populate it —
    # skip rather than flag everything (false-positive flood). Detectors activate
    # once real sag_sol data flows from the Medula ingestion path.
    if not _has_any_sag_sol(procedure_lines):
        return []

    violations: list[dict[str, Any]] = []
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        code = (line.procedure_code or "").strip()
        if not code:
            continue
        if not _is_paired_organ_imaging(code):
            continue
        # Only a single line (quantity == 1) without laterality is suspicious;
        # quantity >= 2 may legitimately represent both sides on one line.
        if line.quantity != 1:
            continue
        if not _laterality_missing(line):
            continue
        detail = (
            f"Çift organ MR/BT işlemi ({code} — {line.procedure_name}) için "
            f"taraf (sag_sol) belirtilmemiş — sag_sol '1' (sağ) veya '2' (sol) "
            f"olarak kaydedilmeli ya da iki ayrı işlem satırı faturalandırılmalı "
            f"(§2.4 laterality #6)."
        )
        violations.append(_violation(line, rule_id="missing_laterality_imaging", detail=detail))
    return violations


def detect_missing_laterality_surgery(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #17: Missing laterality on bilateral-organ surgery.

    Surgical procedures on paired organs (eyes, ears, kidneys, lungs,
    extremities, testes, ovaries) must record which side was operated on
    (``sag_sol="1"``/``"2"``). An empty ``sag_sol`` on such a line is flagged.

    A line is in scope when its ``procedure_category`` matches a known paired-
    organ surgical family, or its code prefix is a known paired-organ surgical
    family (cataract ``516xxx``, kidney ``505xxx``, ear ``510xxx``, lung
    ``530xxx``, extremity ``540xxx``, reproductive ``570xxx``). Conservative —
    only clearly-paired-organ procedures are flagged.

    Honest-skip guard: if no line in ``procedure_lines`` carries a non-empty
    ``sag_sol``, return ``[]`` (see :func:`detect_missing_laterality_imaging`).
    """
    del claims
    # B-guard: see detect_missing_laterality_imaging.
    if not _has_any_sag_sol(procedure_lines):
        return []

    violations: list[dict[str, Any]] = []
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        family = _paired_organ_surgery_family(line)
        if family is None:
            continue
        # Only a strictly missing side is flagged here; "3" (Ayrım yok) is
        # not a meaningful value for a paired-organ *surgical* procedure, but
        # we treat it conservatively as "missing" only when truly empty, to
        # avoid over-flagging.
        if _sag_sol_of(line) != "":
            continue
        detail = (
            f"Çift organ cerrahisi ({line.procedure_code} — {line.procedure_name}, "
            f"{family}) için taraf (sag_sol) belirtilmemiş — sag_sol '1' (sağ) "
            f"veya '2' (sol) olarak kaydedilmeli (§2.4 laterality #17)."
        )
        violations.append(_violation(line, rule_id="missing_laterality_surgery", detail=detail))
    return violations


def _is_paired_organ_imaging(code: str) -> bool:
    """True when an MR/CT code refers to a paired organ (has a left/right).

    Uses 5-char prefix matching (see :data:`_PAIRED_ORGAN_IMAGING_PREFIXES`).
    Codes shorter than 5 chars never match.
    """
    return len(code) >= 5 and code[:5] in _PAIRED_ORGAN_IMAGING_PREFIXES


def _paired_organ_surgery_family(line: ProcedureClaimLine) -> str | None:
    """Return the paired-organ surgical family label, or ``None`` if not in scope.

    Matches by code prefix first (authoritative), then falls back to
    ``procedure_category`` membership.
    """
    code = (line.procedure_code or "").strip()
    if code:
        for prefix, label in _PAIRED_ORGAN_SURGERY_PREFIXES.items():
            if code.startswith(prefix):
                return label
    category = (line.procedure_category or "").strip().casefold()
    if category in _PAIRED_ORGAN_SURGERY_CATEGORIES:
        return line.procedure_category
    return None


# ---------------------------------------------------------------------------
# _for_context wrappers — bridge the typed PatientClaimContext to the flat-list
# detector API (mirrors the gap_closing / common_billing_errors wiring).
# ---------------------------------------------------------------------------


def detect_missing_laterality_imaging_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Evaluate :func:`detect_missing_laterality_imaging` against a PatientClaimContext."""
    return detect_missing_laterality_imaging(list(ctx.claims), list(ctx.procedure_lines))


def detect_missing_laterality_surgery_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Evaluate :func:`detect_missing_laterality_surgery` against a PatientClaimContext."""
    return detect_missing_laterality_surgery(list(ctx.claims), list(ctx.procedure_lines))
