"""
src/bilun/domain/materials/exclusions.py
EK-3B-1 bundled consumables and EK-3B-2 non-reimbursable materials.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping
from typing import Literal, TYPE_CHECKING
from typing import Any

import pandas as pd

from ..claims.claim_type import claim_type_care_setting
from ..constants import EK3B1_BUNDLED_PATH, EK3B2_NON_REIMBURSABLE_PATH
from ..utils import _safe_str, turkish_lower, fuzzy_match_name, token_bound_substring_match

logger = logging.getLogger("ilay.sut_catalog")


@lru_cache(maxsize=1)
def get_non_reimbursable_materials() -> tuple[dict[str, Any], ...]:
    """Get the list of non-reimbursable materials from EK-3B-2.

    Returns:
        Tuple of dicts with keys: sira_no, material_name. (Tuple for
        hashability so ``@lru_cache`` can memoize — thread-safe by design,
        replacing the prior mutable-global + ``global`` pattern that raced
        under ``ThreadPoolExecutor`` cohort runs.)
    """
    if not EK3B2_NON_REIMBURSABLE_PATH.exists():
        logger.warning(
            "EK-3B-2 non-reimbursable catalog not found: %s",
            EK3B2_NON_REIMBURSABLE_PATH,
        )
        return ()

    try:
        df = pd.read_parquet(EK3B2_NON_REIMBURSABLE_PATH)
        records = tuple(
            {
                "sira_no": row.get("sira_no"),
                "material_name": _safe_str(row.get("material_name")),
            }
            for _, row in df.iterrows()
        )
        logger.info("EK-3B-2 non-reimbursable materials loaded: %d items", len(records))
        return records
    except Exception as e:
        logger.warning("Failed to load EK-3B-2 non-reimbursable materials: %s", e)
        return ()


@lru_cache(maxsize=1)
def get_bundled_consumables() -> tuple[dict[str, Any], ...]:
    """Get the list of consumables bundled into procedure prices from EK-3B-1.

    Returns:
        Tuple of dicts with keys: sira_no, item_name, description.
    """
    if not EK3B1_BUNDLED_PATH.exists():
        logger.warning("EK-3B-1 bundled consumables not found: %s", EK3B1_BUNDLED_PATH)
        return ()

    try:
        df = pd.read_parquet(EK3B1_BUNDLED_PATH)
        records = tuple(
            {
                "sira_no": row.get("sira_no"),
                "item_name": _safe_str(row.get("item_name")),
                "description": _safe_str(row.get("description")),
            }
            for _, row in df.iterrows()
        )
        logger.info("EK-3B-1 bundled consumables loaded: %d items", len(records))
        return records
    except Exception as e:
        logger.warning("Failed to load EK-3B-1 bundled consumables: %s", e)
        return ()


def _match_exclusion_candidate(
    material_name: str,
    exclusions: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str] | None:
    """Lexical candidate only: this does not decide annex applicability."""
    catalog = exclusions if exclusions is not None else get_non_reimbursable_materials()
    if not catalog:
        return None

    needle = turkish_lower(material_name.strip())
    if not needle:
        return None

    partial = None
    for entry in catalog:
        mat_name = turkish_lower((entry.get("material_name") or "").strip())
        if not mat_name:
            continue
        # A full source category inside the billed name can identify its
        # subtype. The reverse direction only suggests a partial identity:
        # "kateter" does not establish "İnflow kateter".
        if token_bound_substring_match(mat_name, needle):
            return entry, "name_substring"
        if token_bound_substring_match(needle, mat_name) and partial is None:
            partial = entry

    if partial is not None:
        return partial, "name_partial"

    fuzzy_candidates = [
        (turkish_lower((e.get("material_name") or "").strip()), e)
        for e in catalog
    ]
    fuzzy_candidates = [(n, e) for n, e in fuzzy_candidates if n]
    fuzzy = fuzzy_match_name(needle, fuzzy_candidates, threshold=0.80)
    return (fuzzy[1], "name_fuzzy") if fuzzy else None


def _match_bundled_candidate(
    material_name: str,
    *,
    material_code: str | None = None,
) -> tuple[dict[str, Any], str] | None:
    """Find a lexical EK-3B-1 candidate without certifying applicability.

    ``assess_bundled_material`` separately checks setting/use qualifiers and
    exceptions. Ambiguous and fuzzy candidates cannot become confirmed rows.

    Match priority:
    1. ``code_resolved`` — if ``material_code`` resolves to a catalog name via
       ``resolve_material_name_by_code``, that canonical name is matched first.
    2. ``name_substring`` — token-bound bidirectional substring match against
       the material's billed name.
    3. ``name_fuzzy`` — fuzzy match (threshold 0.80) as a last resort.

    Args:
        material_name: The material's billed name.
        material_code: Optional SUT material code; when present the catalog
            canonical name is resolved and tried first.

    Returns:
        ``(bundled_entry, match_kind)`` or ``None``.
    """
    bundled = get_bundled_consumables()
    if not bundled:
        return None

    # Build the normalized index once.
    bundled_index: list[tuple[str, dict[str, Any]]] = []
    for entry in bundled:
        entry_name = turkish_lower((entry.get("item_name") or "").strip())
        if entry_name:
            bundled_index.append((entry_name, entry))

    # Tier 1 — code-resolved canonical name.
    if material_code:
        from .catalog_lookup import resolve_material_name_by_code

        resolved = resolve_material_name_by_code(material_code)
        if resolved:
            matched = _match_bundled_index(resolved, bundled_index)
            if matched is not None:
                suffix = matched[1].removeprefix("name_")
                return matched[0], f"code_resolved_{suffix}" if suffix in {"fuzzy", "ambiguous"} else "code_resolved"

    # Tiers 2 & 3 — billed name.
    return _match_bundled_index(material_name, bundled_index)


def _match_bundled_index(
    needle_name: str,
    bundled_index: list[tuple[str, dict[str, Any]]],
) -> tuple[dict[str, Any], str] | None:
    """Token-bound substring + fuzzy match against a prebuilt bundled index."""
    needle = turkish_lower(needle_name.strip())
    if "eldiven" in needle:
        # Explicit nonsterile qualifiers are outside the source's sterile
        # exception; removing that adjective only assists candidate lookup.
        for qualifier in ("non-steril", "nonsteril", "steril olmayan"):
            needle = needle.replace(qualifier, "")
        needle = " ".join(needle.split())
    if not needle:
        return None
    matches = []
    for bundled_name, bundled_entry in bundled_index:
        if needle == bundled_name:
            return bundled_entry, "name_substring"
        if token_bound_substring_match(needle, bundled_name) or token_bound_substring_match(
            bundled_name, needle
        ):
            matches.append(bundled_entry)
    if matches:
        return matches[0], "name_ambiguous" if len(matches) > 1 else "name_substring"
    fuzzy = fuzzy_match_name(needle, bundled_index, threshold=0.80)
    if fuzzy:
        return fuzzy[1], "name_fuzzy"
    return None

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader


@dataclass(frozen=True)
class AnnexAssessment:
    """One immutable candidate and its independently checked applicability.

    Source: identical July/August 2026 SGK EK-3B workbooks, titled effective
    03.09.2022. This records annex meaning, not a service-interval attestation or
    proof that an unlisted product is otherwise payable under SUT.
    """

    status: Literal["matched", "not_matched", "unavailable"]
    entry: Mapping[str, Any] | None = None
    match_kind: str | None = None
    reason: str | None = None

    @property
    def matched(self) -> bool | None:
        return None if self.status == "unavailable" else self.status == "matched"


def _assessment(status, candidate=None, reason=None):
    return AnnexAssessment(
        status,
        MappingProxyType(dict(candidate[0])) if candidate else None,
        candidate[1] if candidate else None,
        reason,
    )


def _fold(text: str) -> str:
    return turkish_lower(text).translate(str.maketrans("çğıöşü", "cgiosu"))


def care_setting_from_header(header: ClaimHeader | None) -> str | None:
    """Only actual header setting; the legacy dict adapter invents outpatient.

    The setting of the claim type in the one vocabulary (claims/claim_type.py, #335);
    None for a type without one (koruyucu, meslek_hastaligi) or an unknown type.
    """
    if header is None or header.scenario_tag == "validate_claim_adapter":
        return None
    return claim_type_care_setting(header.claim_type)


def assess_bundled_material(
    material_name: str, *, material_code: str | None = None,
    care_setting: str | None = None, clinical_use: str | None = None,
) -> AnnexAssessment:
    if not material_name.strip() and not material_code:
        return _assessment("unavailable", reason="material_identity_required")
    if not get_bundled_consumables():
        return _assessment("unavailable", reason="annex_catalog_unavailable")
    candidate = _match_bundled_candidate(material_name, material_code=material_code)
    if candidate is None:
        return _assessment("not_matched")
    entry, kind = candidate
    label = _fold(str(entry.get("item_name") or ""))
    from .catalog_lookup import resolve_material_name_by_code

    resolved = resolve_material_name_by_code(material_code) if material_code else None
    name = _fold(" ".join(filter(None, (material_name, resolved))))
    if "fuzzy" in kind:
        return _assessment("unavailable", candidate, "annex_material_identity_fuzzy")
    if "ambiguous" in kind:
        return _assessment("unavailable", candidate, "annex_material_identity_ambiguous")
    if care_setting not in {"inpatient", "outpatient"}:
        care_setting = None
    # The phrase in the annex names an exception, not a positive glove match.
    if "eldiven" in label and "steril" in label:
        nonsterile = any(value in name for value in ("nonsteril", "non-steril", "steril olmayan"))
        if "steril" in name and not nonsterile:
            if "cerrahi" in name:
                return _assessment("not_matched", candidate, "surgical_sterile_glove_exception")
            return _assessment("unavailable", candidate, "surgical_sterile_glove_identity_required")
    if "enjektor" in label and "yatarak" in label:
        if care_setting is None:
            return _assessment("unavailable", candidate, "inpatient_care_setting_required")
        if care_setting != "inpatient":
            return _assessment("not_matched", candidate, "inpatient_only_annex_row")
    if "kan sekeri" in label and "idrar" in label:
        blood = "kan seker" in name or "glukoz" in name
        urine = "idrar" in name
        if blood == urine:
            return _assessment("unavailable", candidate, "blood_or_urine_strip_identity_required")
        if blood and care_setting is None:
            return _assessment("unavailable", candidate, "inpatient_care_setting_required")
        if blood and care_setting != "inpatient":
            return _assessment("not_matched", candidate, "inpatient_only_annex_row")
    required_use = (
        "dressing" if "oksijen" in label and "pansuman" in label else
        "dialysis_bathing" if "diyalizli" in label else
        "endoscopy" if "endoskobik" in label else None
    )
    if required_use is not None and clinical_use != required_use:
        return _assessment("unavailable", candidate, f"{required_use}_use_evidence_required")
    return _assessment("matched", candidate)


def assess_excluded_material(
    material_name: str, *, material_code: str | None = None,
    exclusions: list[dict[str, Any]] | None = None,
) -> AnnexAssessment:
    from .catalog_lookup import resolve_material_name_by_code

    if not material_name.strip() and not material_code:
        return _assessment("unavailable", reason="material_identity_required")
    if not (exclusions if exclusions is not None else get_non_reimbursable_materials()):
        return _assessment("unavailable", reason="annex_catalog_unavailable")
    lookup_name = resolve_material_name_by_code(material_code) if material_code else None
    candidate = _match_exclusion_candidate(lookup_name or material_name, exclusions)
    if candidate is None and lookup_name and lookup_name != material_name:
        candidate = _match_exclusion_candidate(material_name, exclusions)
    if candidate is None:
        return _assessment("not_matched")
    entry, kind = candidate
    if "fuzzy" in kind:
        return _assessment("unavailable", candidate, "annex_material_identity_fuzzy")
    if "viskosuplemantasyon" in _fold(str(entry.get("material_name") or "")):
        # The claim model does not prove the SUT/annex exception membership.
        return _assessment("unavailable", candidate, "sut_annex_exception_applicability_required")
    if kind == "name_partial":
        return _assessment("unavailable", candidate, "annex_material_identity_partial")
    return _assessment("matched", candidate)


def match_exclusion_entry(material_name: str, exclusions=None) -> dict[str, Any] | None:
    """Return a confirmed exclusion only; None does not certify reimbursability."""
    assessment = assess_excluded_material(material_name, exclusions=exclusions)
    return dict(assessment.entry) if assessment.matched is True else None


def match_bundled_material(material_name: str, *, material_code=None, care_setting=None):
    """Return a resolved EK-3B-1 match; never hide an unknown qualifier as true."""
    assessment = assess_bundled_material(material_name, material_code=material_code, care_setting=care_setting)
    return (dict(assessment.entry), assessment.match_kind) if assessment.matched is True else None


def is_material_reimbursable(material_name: str, *, material_code: str | None = None) -> bool | None:
    """Legacy non-exclusion indicator, NOT independent proof of SUT entitlement.

    None means a candidate's exclusion/exception applicability is unresolved.
    True means only that this EK-3B-2 check did not find a confirmed exclusion.
    """
    match = assess_excluded_material(material_name, material_code=material_code).matched
    return None if match is None else not match


def is_consumable_bundled(item_name: str, *, care_setting: str | None = None, material_code: str | None = None) -> bool | None:
    """True/False/None for EK-3B-1 scope; False is not permission to bill."""
    return assess_bundled_material(item_name, care_setting=care_setting, material_code=material_code).matched
