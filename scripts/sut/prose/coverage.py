"""Build SUT prose → domain coverage matrix."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from .classify import classify_clauses
from .manifest_index import encoded_like_clause_ids, load_drug_bucket_clause_ids
from .rule_registry import RULE_BY_ID, RULE_REGISTRY, CoverageStatus

_IN_FORCE_ONLY = True

_DRUG_INDICATION_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"
)
_ANTI_VEGF_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "data/gazette/prose_manifests/L4.33_anti_vegf_4.2.33_manifest.json"
)
_DRUG_4213_4216_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "data/gazette/prose_manifests/L4.2_drug_indication_4213_4216_manifest.json"
)
_DRUG_4217_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "data/gazette/prose_manifests/L4.2_drug_indication_4217_manifest.json"
)
_DRUG_4219_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "data/gazette/prose_manifests/L4.2_drug_indication_4219_manifest.json"
)
_MANIFEST_DIR = Path(__file__).resolve().parents[3] / "data/gazette/prose_manifests"
_DRUG_INDICATION_RULES_JSON = (
    Path(__file__).resolve().parents[3] / "data/gazette/prose_rules/drug_indication_prose.json"
)
_PAYMENT_METHOD_22_MANIFEST = "L2.2_payment_method_encoded_manifest.json"
_SESSION_PRICING_22_MANIFEST = "L2.2_session_pricing_2_2_2_B_encoded_manifest.json"
_DEFINITIONS_2_6_MANIFEST = "L2.6_definitions_manifest.json"
_TREATMENT_PRICING_2_4_MANIFEST = "L2.4_treatment_pricing_wave2_manifest.json"
_WAVE2_MANIFESTS: dict[str, str] = {
    # §2.6 definitions/scope clauses encode runtime-billing gates.
    "definitions": _DEFINITIONS_2_6_MANIFEST,
    # §2.4 treatment-package pricing (incl. §2.4.4) wave encodes.
    "pricing_ek2b": _TREATMENT_PRICING_2_4_MANIFEST,
    "gazette_repricing": "L2.2_gazette_repricing_encoded_manifest.json",
    "procedure_pairing": "L2.2_procedure_pairing_encoded_manifest.json",
    "material_pairing": "L3.1_material_pairing_encoded_manifest.json",
    "payment_method_package": _PAYMENT_METHOD_22_MANIFEST,
    "payment_method_itemized": _PAYMENT_METHOD_22_MANIFEST,
    "payment_method_tier_override": _PAYMENT_METHOD_22_MANIFEST,
    "drg_unbundling": _SESSION_PRICING_22_MANIFEST,
    "copay_rate_general": "L1.8_copay_exemption_encoded_manifest.json",
    "copay_exemption_ek1a": "L1.8_copay_exemption_encoded_manifest.json",
    "copay_exemption_visit_type": "L1.8_copay_exemption_encoded_manifest.json",
    "copay_exemption_ek4d": "L1.8_copay_exemption_encoded_manifest.json",
}
_PROSE_MANIFESTS: dict[str, str] = {
    "material_bundling_prose": "L1.4_material_bundling_encoded_manifest.json",
    "specialty_materials_prose": "L4.4_specialty_prose_encoded_manifest.json",
    "dental_2_4_1": "dental_2_4_1_manifest.json",
    "gap_closing_misc": "gap_closing_misc_manifest.json",
}

def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


def _has_actionable_signal(row: pd.Series) -> bool:
    """True when the clause plausibly needs a billing rule mapping (not pure reference)."""
    deontic_modality = _optional_str(row.get("deontic_modality"))
    annex_refs = _json_list(str(row.get("annex_refs", "[]")))
    clause_type = str(row.get("clause_type") or "")
    has_normative_or_annex = bool(deontic_modality or annex_refs)
    # Structural / navigational rows (chapter titles, section headings, RG lines,
    # short prose labels like "Genel Hükümler") are reference unless they carry
    # deontic or annex signals — fixes C000002 false missing/gap.
    if clause_type in {"chapter", "section_heading", "amendment", "prose"}:
        return has_normative_or_annex
    # numbered_item falls through here (not in either set). Its result is
    # `has_normative_or_annex` — identical to the prose branch above — so the
    # reclassification from prose is behavior-preserving for coverage gating.
    return bool(has_normative_or_annex or clause_type in {"fikra", "bent"})


def _load_encoded_clause_ids(manifest_name: str) -> frozenset[str]:
    path = _MANIFEST_DIR / manifest_name
    if not path.is_file():
        return frozenset()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _manifest_clause_ids_from_payload(payload)


def _manifest_clause_ids_from_payload(payload: dict[str, Any]) -> frozenset[str]:
    return encoded_like_clause_ids(payload)


def _load_drug_indication_emr_blocked_clause_ids() -> frozenset[str]:
    """Clause IDs genuinely EMR-blocked across all §4.2 drug manifests."""
    return load_drug_bucket_clause_ids(status="emr_blocked", manifest_dir=_MANIFEST_DIR)


def _load_drug_indication_tier_c_deferred_clause_ids() -> frozenset[str]:
    """Tier-C deferred clause IDs — honest deferral removes algorithmic gap."""
    return load_drug_bucket_clause_ids(status="tier_c_deferred", manifest_dir=_MANIFEST_DIR)


def _is_structural_gap_excluded(row: pd.Series) -> bool:
    """Structural/nav rows without normative signal are not encode debt."""
    clause_type = str(row.get("clause_type") or "")
    deontic_modality = _optional_str(row.get("deontic_modality"))
    if clause_type in {"chapter", "section_heading", "amendment"} and not deontic_modality:
        return True
    is_heading = row.get("is_heading")
    if is_heading is True and not deontic_modality:
        return True
    return False


def _load_gate_b_sources_from_rules_json(path: Path) -> frozenset[str]:
    if not path.is_file():
        return frozenset()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    ids: set[str] = set()
    for rule in payload.get("rules") or []:
        ids.update(str(c) for c in (rule.get("gate_b_sources") or []) if c)
    return frozenset(ids)


def _load_drug_indication_encoded_clause_ids() -> frozenset[str]:
    """Encoded clause IDs for the merged drug_indication corpus.

    Phase 6 simplification: derive the encoded set directly from rule JSON
    gate_b_sources (the single source of truth), supplemented by manifests
    for sections whose rules haven't been fully encoded yet.
    """
    # Primary: derive from rules JSON gate_b_sources (canonical source of truth)
    encoded: frozenset[str] = frozenset()
    if _DRUG_INDICATION_RULES_JSON.is_file():
        try:
            payload = json.loads(_DRUG_INDICATION_RULES_JSON.read_text(encoding="utf-8"))
            rule_encoded = frozenset(
                str(cid)
                for rule in (payload.get("rules") or [])
                for cid in (rule.get("gate_b_sources") or [])
            )
            encoded |= rule_encoded
        except (json.JSONDecodeError, OSError):
            pass

    # Supplement: anti-VEGF corpus (separate JSON)
    anti_vegf_rules = _DRUG_INDICATION_RULES_JSON.parent / "anti_vegf_prose.json"
    if anti_vegf_rules.is_file():
        try:
            av_payload = json.loads(anti_vegf_rules.read_text(encoding="utf-8"))
            encoded |= frozenset(
                str(cid)
                for rule in (av_payload.get("rules") or [])
                for cid in (rule.get("gate_b_sources") or [])
            )
        except (json.JSONDecodeError, OSError):
            pass

    # Supplement: R6 deontic-wave manifests (sections whose rules aren't in the
    # main JSON yet — these are still manifest-tracked only)
    for name in (
        "L4.2_drug_indication_4_2_14_wave2_manifest.json",
        "L4.2_drug_indication_rheum_biologics_manifest.json",
        "L4.2_drug_indication_small_mid_manifest.json",
        "L4.2_drug_indication_metabolic_mid_manifest.json",
        "L4_drug_ek4a_r6_manifest.json",
        "L4.2_drug_indication_eye_mid_b_r6_manifest.json",
        "L4.2_drug_indication_eye_mid_a_r6_manifest.json",
        "L4.2_drug_indication_tail_a_r6_manifest.json",
        "L4.2_drug_indication_tail_b_r6_manifest.json",
    ):
        path = _MANIFEST_DIR / name
        if path.is_file():
            encoded |= _manifest_clause_ids_from_payload(
                json.loads(path.read_text(encoding="utf-8"))
            )
    encoded |= _load_gate_b_sources_from_rules_json(_DRUG_INDICATION_RULES_JSON)
    return encoded


def _load_wave2_encoded_clause_ids(rule_id: str) -> frozenset[str]:
    manifest_name = _WAVE2_MANIFESTS.get(rule_id)
    if not manifest_name:
        return frozenset()
    return _load_encoded_clause_ids(manifest_name)


def _section_22_manifest_encoding(clause_id: str, section_id: str) -> bool:
    """§2.2 Gate B encode is honest even when classification picks another motor."""
    if not section_id.startswith("2.2"):
        return False
    if clause_id in _load_encoded_clause_ids(_PAYMENT_METHOD_22_MANIFEST):
        return True
    return clause_id in _load_encoded_clause_ids(_SESSION_PRICING_22_MANIFEST)


# --- R6 deontic-wave section overrides (2026-06-29) -------------------------
# These clauses are encoded in their own dedicated manifests, but the
# classifier sometimes routes them to a different primary motor than the one
# the manifest is keyed to (e.g. NO_PAY drug clauses → exclusion_ek3b2,
# §3.3 → specialty_materials fallback). The overrides ensure has_rule_encoding
# reflects the encode regardless of the classification motor.


def _section_2_4_4_manifest_encoding(clause_id: str, section_id: str) -> bool:
    """§2.4 treatment-pricing wave encodes (incl. §2.4.4)."""
    if not section_id.startswith("2.4"):
        return False
    return (clause_id in _load_encoded_clause_ids(_TREATMENT_PRICING_2_4_MANIFEST)
            or clause_id in _load_encoded_clause_ids("L2.4_treatment_pricing_r6_rest_manifest.json"))


def _section_3_3_specialty_encoding(clause_id: str, section_id: str) -> bool:
    """§3.3 specialty-materials wave encodes."""
    if not section_id.startswith("3.3"):
        return False
    return clause_id in _load_encoded_clause_ids("L4.4_specialty_prose_encoded_manifest.json")


def _section_drug_indication_wave_encoding(clause_id: str, section_id: str) -> bool:
    """§4.2 drug-indication wave encodes (oncology/rheum/small-mid/metabolic).

    Catches clauses the classifier routes to exclusion_ek3b2/material_exclusion
    instead of drug_indication_prose. Also covers §4.1/4.3-4.7 drug provisions
    (drug_ek4a motor) encoded in the r6 wave.
    """
    if section_id.startswith("4.2"):
        return clause_id in _load_drug_indication_encoded_clause_ids()
    if section_id.startswith(("4.1", "4.3", "4.4", "4.5", "4.6", "4.7")):
        return clause_id in _load_encoded_clause_ids("L4_drug_ek4a_r6_manifest.json")
    return False


def _section_definitions_2_6_encoding(clause_id: str, section_id: str) -> bool:
    """§2.6 definitions encodes (non_algorithmic but runtime-relevant)."""
    if not section_id.startswith("2.6"):
        return False
    return clause_id in _load_encoded_clause_ids(_DEFINITIONS_2_6_MANIFEST)


def _section_r6_misc_encoding(clause_id: str, section_id: str) -> bool:
    """R6 wave encodes across §1.5-1.10 (referral/surcharge), §2.2/2.3/2.5
    (payment/pricing), §5.x/§6.x (billing docs / misc), §3.x leftover materials.

    These clauses classify under non-algorithmic or fallback motors, so the
    dedicated r6 manifests must be checked via section-scoped overrides.
    """
    if section_id.startswith(("1.5", "1.6", "1.7", "1.9", "1.10")):
        return clause_id in _load_encoded_clause_ids("L_r6_referral_encoded_manifest.json")
    if section_id.startswith(("5.", "6.", "1.8", "1.1", "1.11")):
        return clause_id in _load_encoded_clause_ids("L_r6_billing_def_encoded_manifest.json")
    if section_id.startswith(("2.2", "2.3", "2.5")):
        return clause_id in _load_encoded_clause_ids("L2_payment_pricing_r6_manifest.json")
    if section_id.startswith(("3.1", "3.2")):
        return clause_id in _load_encoded_clause_ids("L_r6_specialty_leftover_manifest.json")
    return False

_STATUS_RANK: dict[str, int] = {
    "implemented": 0,
    "partial": 1,
    "needs_claim_lines": 2,
    "missing": 3,
    "non_algorithmic": 4,
}


def _json_list(raw: str) -> list[str]:
    if not raw or raw == "[]":
        return []
    return json.loads(raw)


def _enrich_with_coverage(classified: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    encoded_clause_ids = _load_drug_indication_encoded_clause_ids()
    emr_blocked_ids = _load_drug_indication_emr_blocked_clause_ids()
    tier_c_deferred_ids = _load_drug_indication_tier_c_deferred_clause_ids()

    for _, row in classified.iterrows():
        primary_rule_id = row.get("primary_rule_id")
        matched_rule_ids = _json_list(str(row.get("matched_rule_ids", "[]")))

        if primary_rule_id and primary_rule_id in RULE_BY_ID:
            primary = RULE_BY_ID[primary_rule_id]
            primary_status: CoverageStatus = primary.coverage_status
            primary_category = primary.rule_category
            primary_modules = list(primary.domain_modules)
            coverage_notes = primary.description
        elif matched_rule_ids:
            primary_status = "missing"
            primary_category = "unmapped"
            primary_modules = []
            coverage_notes = "Matched registry entry not found"
        else:
            primary_status = "missing"
            primary_category = "unclassified"
            primary_modules = []
            coverage_notes = "No rule category matched"

        all_statuses: list[str] = []
        all_modules: set[str] = set()
        all_categories: set[str] = set()

        for rule_id in matched_rule_ids:
            entry = RULE_BY_ID.get(rule_id)
            if not entry:
                continue
            all_statuses.append(entry.coverage_status)
            all_categories.add(entry.rule_category)
            all_modules.update(entry.domain_modules)

        if all_statuses:
            worst_status = max(all_statuses, key=lambda s: _STATUS_RANK.get(s, 99))
        else:
            worst_status = primary_status

        has_actionable_signal = _has_actionable_signal(row)

        if primary_category == "unclassified" and not has_actionable_signal:
            primary_status = "non_algorithmic"
            worst_status = "non_algorithmic"
            coverage_notes = "Administrative or definitional text without billing rule signals"
        elif primary_category == "unclassified" and has_actionable_signal:
            primary_status = "missing"
            worst_status = "missing"
            coverage_notes = "Actionable SUT rule text with no mapped domain implementation"

        has_algorithmic_gap = (
            primary_status in {"partial", "missing", "needs_claim_lines"}
            and primary_status != "non_algorithmic"
        )
        clause_id = str(row.get("clause_id") or "")
        if _is_structural_gap_excluded(row):
            has_algorithmic_gap = False
        elif clause_id in emr_blocked_ids or clause_id in tier_c_deferred_ids:
            has_algorithmic_gap = False
        if primary_rule_id == "drug_indication_prose":
            has_rule_encoding = clause_id in encoded_clause_ids
        elif primary_rule_id in _WAVE2_MANIFESTS:
            has_rule_encoding = clause_id in _load_wave2_encoded_clause_ids(primary_rule_id)
        elif primary_rule_id in _PROSE_MANIFESTS:
            manifest_name = _PROSE_MANIFESTS[primary_rule_id]
            has_rule_encoding = clause_id in _load_encoded_clause_ids(manifest_name)
        else:
            has_rule_encoding = False

        section_id = str(row.get("section_id") or "")
        if not has_rule_encoding:
            # Section-specific overrides: reflect encodes whose manifest motor
            # differs from the classifier's primary_rule_id.
            for _override in (
                _section_22_manifest_encoding,
                _section_2_4_4_manifest_encoding,
                _section_3_3_specialty_encoding,
                _section_drug_indication_wave_encoding,
                _section_definitions_2_6_encoding,
                _section_r6_misc_encoding,
            ):
                if _override(clause_id, section_id):
                    has_rule_encoding = True
                    break

        rows.append(
            {
                **row.to_dict(),
                "primary_rule_category": primary_category,
                "coverage_status": primary_status,
                "worst_coverage_status": worst_status,
                "domain_modules": json.dumps(sorted(all_modules or primary_modules), ensure_ascii=False),
                "matched_rule_categories": json.dumps(sorted(all_categories), ensure_ascii=False),
                "coverage_notes": coverage_notes,
                "has_algorithmic_gap": has_algorithmic_gap,
                "has_rule_encoding": has_rule_encoding,
                "emr_blocked": clause_id in emr_blocked_ids,
            }
        )

    return pd.DataFrame(rows)


def build_coverage_summary(coverage: pd.DataFrame) -> pd.DataFrame:
    if coverage.empty:
        return pd.DataFrame()

    agg_spec: dict[str, Any] = {
        "clause_count": ("clause_id", "count"),
        "sections": ("section_id", lambda s: sorted({x for x in s.dropna().unique()})),
        "sample_text": ("in_force_text", "first")
        if "in_force_text" in coverage.columns
        else ("text_tr", "first"),
        "gap_clause_count": ("has_algorithmic_gap", "sum"),
    }
    if "has_rule_encoding" in coverage.columns:
        agg_spec["encoded_clause_count"] = ("has_rule_encoding", "sum")

    grouped = (
        coverage.groupby(["primary_rule_id", "primary_rule_category", "coverage_status"], dropna=False)
        .agg(**agg_spec)
        .reset_index()
    )

    if "encoded_clause_count" in grouped.columns:
        grouped["encoded_clause_count"] = grouped["encoded_clause_count"].astype(int)
        grouped["unencoded_gap_clause_count"] = (
            grouped["gap_clause_count"] - grouped["encoded_clause_count"]
        ).clip(lower=0).astype(int)
    grouped["gap_clause_count"] = grouped["gap_clause_count"].astype(int)

    grouped["sample_sections"] = grouped["sections"].apply(lambda xs: json.dumps(xs[:8], ensure_ascii=False))
    grouped["domain_modules"] = grouped["primary_rule_id"].apply(
        lambda rule_id: json.dumps(
            list(RULE_BY_ID[rule_id].domain_modules) if rule_id in RULE_BY_ID else [],
            ensure_ascii=False,
        )
    )
    grouped["description"] = grouped["primary_rule_id"].apply(
        lambda rule_id: RULE_BY_ID[rule_id].description if rule_id in RULE_BY_ID else ""
    )
    grouped = grouped.drop(columns=["sections"])
    grouped = grouped.sort_values(["coverage_status", "clause_count"], ascending=[True, False])
    return grouped


def build_section_summary(coverage: pd.DataFrame) -> pd.DataFrame:
    if coverage.empty:
        return pd.DataFrame()

    def _worst_status(statuses: pd.Series) -> str:
        values = [s for s in statuses.dropna().unique()]
        if not values:
            return "missing"
        return max(values, key=lambda s: _STATUS_RANK.get(str(s), 99))

    grouped = (
        coverage[coverage["section_id"].notna()]
        .groupby(["section_id", "section_title"], dropna=False)
        .agg(
            clause_count=("clause_id", "count"),
            worst_coverage_status=("worst_coverage_status", _worst_status),
            gap_clause_count=("has_algorithmic_gap", "sum"),
            primary_categories=("primary_rule_category", lambda s: sorted(set(s.dropna()))),
        )
        .reset_index()
    )
    grouped["primary_categories"] = grouped["primary_categories"].apply(
        lambda xs: json.dumps(xs, ensure_ascii=False)
    )
    grouped = grouped.sort_values(["worst_coverage_status", "gap_clause_count"], ascending=[True, False])
    return grouped


def build_registry_coverage_summary(coverage: pd.DataFrame) -> pd.DataFrame:
    """One row per registry rule showing whether any clause mapped to it."""
    classified_ids = set()
    for raw in coverage.get("matched_rule_ids", pd.Series(dtype=str)):
        classified_ids.update(_json_list(str(raw)))

    rows: list[dict[str, Any]] = []
    for entry in RULE_REGISTRY:
        matched = coverage["matched_rule_ids"].str.contains(entry.rule_id, regex=False, na=False)
        rows.append(
            {
                "rule_id": entry.rule_id,
                "rule_category": entry.rule_category,
                "registry_coverage_status": entry.coverage_status,
                "domain_modules": json.dumps(list(entry.domain_modules), ensure_ascii=False),
                "description": entry.description,
                "matched_clause_count": int(matched.sum()),
                "has_clause_mapping": entry.rule_id in classified_ids,
            }
        )

    frame = pd.DataFrame(rows)
    return frame.sort_values(["registry_coverage_status", "matched_clause_count"], ascending=[True, False])


def build_sut_coverage(clauses: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if _IN_FORCE_ONLY and "is_in_force" in clauses.columns:
        clauses = clauses[clauses["is_in_force"]].copy()
    classified = classify_clauses(clauses)
    coverage = _enrich_with_coverage(classified)
    rule_summary = build_coverage_summary(coverage)
    section_summary = build_section_summary(coverage)
    registry_summary = build_registry_coverage_summary(coverage)
    return coverage, rule_summary, section_summary, registry_summary


def write_sut_coverage(
    clauses_path: Path,
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    clauses = pd.read_parquet(clauses_path)
    coverage, rule_summary, section_summary, registry_summary = build_sut_coverage(clauses)

    output_dir.mkdir(parents=True, exist_ok=True)
    coverage.to_parquet(output_dir / "sut_clause_coverage.parquet", index=False)
    rule_summary.to_parquet(output_dir / "sut_coverage_by_rule.parquet", index=False)
    section_summary.to_parquet(output_dir / "sut_coverage_by_section.parquet", index=False)
    registry_summary.to_parquet(output_dir / "sut_registry_coverage.parquet", index=False)

    return coverage, rule_summary, section_summary, registry_summary
