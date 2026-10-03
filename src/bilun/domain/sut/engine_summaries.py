from __future__ import annotations

import json
from typing import Any
import polars as pl
from ..constants import PROSE_MANIFESTS_DIR

from .rule_registry import RULE_BY_ID
from .rules_catalog import _load_sut_clauses_frame


def _prose_partial_engine_summary(
    *,
    rule_id: str,
    clause_frame: pl.DataFrame,
    registry_status: str,
    prose_rules_on_disk: int,
    manifest_traced_clause_count: int | None = None,
    honesty_note: str,
) -> dict[str, Any]:
    """Honest partial-engine rollup for prose corpora (registry vs manifest encoding)."""
    scoped = clause_frame.filter(pl.col("primary_rule_id") == rule_id)
    classified_rows = scoped.height
    gap_rows = (
        scoped.filter(pl.col("has_algorithmic_gap") == True).height
        if "has_algorithmic_gap" in scoped.columns
        else 0
    )
    encoded_rows = (
        scoped.filter(pl.col("has_rule_encoding") == True).height
        if "has_rule_encoding" in scoped.columns
        else 0
    )
    unencoded_gap_rows = (
        scoped.filter(
            (pl.col("has_algorithmic_gap") == True)
            & (pl.col("has_rule_encoding") == False)
        ).height
        if {"has_algorithmic_gap", "has_rule_encoding"}.issubset(set(scoped.columns))
        else gap_rows
    )
    deferred_gap_rows = (
        scoped.filter(
            (pl.col("has_algorithmic_gap") == False)
            & (pl.col("has_rule_encoding") == False)
        ).height
        if {"has_algorithmic_gap", "has_rule_encoding"}.issubset(set(scoped.columns))
        else 0
    )
    true_gap_rows = unencoded_gap_rows
    return {
        "rule_id": rule_id,
        "registry_status": registry_status,
        "prose_engine_status": "partial" if registry_status == "partial" else "implemented",
        "classified_clause_rows": classified_rows,
        "encoded_clause_rows": encoded_rows,
        "deferred_gap_rows": deferred_gap_rows,
        "true_gap_rows": true_gap_rows,
        "algorithmic_gap_rows": gap_rows,
        "unencoded_gap_rows": unencoded_gap_rows,
        "encoded_clause_pct": round(100.0 * encoded_rows / classified_rows, 1)
        if classified_rows
        else 0.0,
        "gap_pct_of_classified": round(100.0 * gap_rows / classified_rows, 1)
        if classified_rows
        else 0.0,
        "prose_rules_on_disk": prose_rules_on_disk,
        "manifest_traced_clause_count": manifest_traced_clause_count,
        "honesty_note": honesty_note,
    }


def _manifest_traced_clause_count(manifest_name: str) -> int:
    manifest_path = PROSE_MANIFESTS_DIR / manifest_name
    if not manifest_path.is_file():
        return 0
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids: set[str] = set()
    encoded = payload.get("encoded_clause_ids")
    if isinstance(encoded, list):
        ids.update(str(clause_id) for clause_id in encoded)
    for key, value in payload.items():
        if not isinstance(value, list):
            continue
        if key in {"encoded_clause_ids"} or key.endswith("_clause_ids"):
            ids.update(str(clause_id) for clause_id in value)
    return len(ids)


def _load_prose_manifest_stats(manifest_name: str) -> dict[str, Any]:
    traced = _manifest_traced_clause_count(manifest_name)
    manifest_path = PROSE_MANIFESTS_DIR / manifest_name
    rules_in_json = 0
    if manifest_path.is_file():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        rules_in_json = int(payload.get("rules_in_json") or 0)
    return {
        "manifest_traced_clause_count": traced,
        "rules_in_json": rules_in_json,
    }


def _material_bundling_partial_engine_summary(clause_frame: pl.DataFrame) -> dict[str, Any]:
    from src.bilun.domain.prose_rules.material_bundling import load_material_bundling_rules

    manifest_stats = _load_prose_manifest_stats("L1.4_material_bundling_encoded_manifest.json")
    rules_on_disk = len(load_material_bundling_rules().get("rules") or [])
    summary = _prose_partial_engine_summary(
        rule_id="material_bundling_prose",
        clause_frame=clause_frame,
        registry_status=RULE_BY_ID["material_bundling_prose"].coverage_status,
        prose_rules_on_disk=rules_on_disk,
        manifest_traced_clause_count=manifest_stats.get("manifest_traced_clause_count"),
        honesty_note=(
            "Registry is implemented for the prose engine; manifest traces §3.1–3.2 encode "
            f"candidates ({manifest_stats.get('manifest_traced_clause_count', 0):,} clause IDs) "
            f"vs {rules_on_disk} JSON rules on disk. Long-tail §3.1 fikra stay manifest-only."
        ),
    )
    summary["corpus_export_rows"] = _l14_corpus_row_count()
    from src.bilun.domain.materials.coverage_scope import kdv_pricing_clause_count

    summary["kdv_pricing_clauses"] = kdv_pricing_clause_count()
    return summary


def _l14_corpus_row_count() -> int:
    """L1.4 material bundling corpus count (§3.1–3.2 clauses)."""
    return _corpus_row_count_from_parquet("3.1") + _corpus_row_count_from_parquet("3.2")


def _corpus_row_count_from_parquet(section_prefix: str) -> int:
    """Derive corpus row count from sut_clauses.parquet (no CSV runtime reads)."""
    frame = _load_sut_clauses_frame()
    if frame.height == 0:
        return 0
    try:
        return frame.filter(pl.col("section_id").str.starts_with(section_prefix)).height
    except Exception:  # pragma: no cover - defensive
        return 0


_PAYMENT_METHOD_MOTORS = (
    "payment_method_package",
    "payment_method_itemized",
    "payment_method_tier_override",
)

_COPAY_MOTORS = (
    "copay_rate_general",
    "copay_exemption_ek1a",
    "copay_exemption_ek4d",
    "copay_exemption_visit_type",
)


def _l18_corpus_row_count() -> int:
    """L1.8 copay exemption corpus count (§1.8 clauses)."""
    return _corpus_row_count_from_parquet("1.8")


def _copay_exemption_partial_engine_summary(clause_frame: pl.DataFrame) -> dict[str, Any]:
    from src.bilun.domain.prose_rules.copay_general import load_decision_table

    manifest_stats = _load_prose_manifest_stats("L1.8_copay_exemption_encoded_manifest.json")
    rules_on_disk = len(load_decision_table().get("rules") or [])
    scoped = clause_frame.filter(
        pl.col("section_id").str.starts_with("1.8")
        & pl.col("primary_rule_id").is_in(list(_COPAY_MOTORS))
    )
    classified_rows = scoped.height
    gap_rows = (
        scoped.filter(pl.col("has_algorithmic_gap") == True).height
        if "has_algorithmic_gap" in scoped.columns
        else 0
    )
    encoded_rows = (
        scoped.filter(pl.col("has_rule_encoding") == True).height
        if "has_rule_encoding" in scoped.columns
        else 0
    )
    unencoded_gap_rows = (
        scoped.filter(
            (pl.col("has_algorithmic_gap") == True)
            & (pl.col("has_rule_encoding") == False)
        ).height
        if {"has_algorithmic_gap", "has_rule_encoding"}.issubset(set(scoped.columns))
        else gap_rows
    )
    return {
        "rule_id": "copay_general_1_8",
        "registry_status": "partial",
        "prose_engine_status": "partial",
        "classified_clause_rows": classified_rows,
        "encoded_clause_rows": encoded_rows,
        "algorithmic_gap_rows": gap_rows,
        "unencoded_gap_rows": unencoded_gap_rows,
        "encoded_clause_pct": round(100.0 * encoded_rows / classified_rows, 1)
        if classified_rows
        else 0.0,
        "gap_pct_of_classified": round(100.0 * gap_rows / classified_rows, 1)
        if classified_rows
        else 0.0,
        "prose_rules_on_disk": rules_on_disk,
        "manifest_traced_clause_count": manifest_stats.get("manifest_traced_clause_count"),
        "corpus_export_rows": _l18_corpus_row_count(),
        "honesty_note": (
            "§1.8 copay motors share one Gate B manifest; "
            f"{rules_on_disk} JSON rules trace "
            f"{manifest_stats.get('manifest_traced_clause_count', 0):,} clause IDs. "
            "Compositor modules (EK-1A, visit type, patient status) carry manifest traces "
            "beyond on-disk JSON exemption rows."
        ),
    }


def _l22_corpus_row_count() -> int:
    return _corpus_row_count_from_parquet("2.2")


def _payment_method_partial_engine_summary(clause_frame: pl.DataFrame) -> dict[str, Any]:
    from src.bilun.domain.prose_rules.payment_method import load_decision_table

    manifest_stats = _load_prose_manifest_stats("L2.2_payment_method_encoded_manifest.json")
    rules_on_disk = len(load_decision_table().get("rules") or [])
    scoped = clause_frame.filter(
        pl.col("section_id").str.starts_with("2.2")
        & pl.col("primary_rule_id").is_in(list(_PAYMENT_METHOD_MOTORS))
    )
    classified_rows = scoped.height
    gap_rows = (
        scoped.filter(pl.col("has_algorithmic_gap") == True).height
        if "has_algorithmic_gap" in scoped.columns
        else 0
    )
    encoded_rows = (
        scoped.filter(pl.col("has_rule_encoding") == True).height
        if "has_rule_encoding" in scoped.columns
        else 0
    )
    unencoded_gap_rows = (
        scoped.filter(
            (pl.col("has_algorithmic_gap") == True)
            & (pl.col("has_rule_encoding") == False)
        ).height
        if {"has_algorithmic_gap", "has_rule_encoding"}.issubset(set(scoped.columns))
        else gap_rows
    )
    return {
        "rule_id": "payment_method_2_2",
        "registry_status": "partial",
        "prose_engine_status": "partial",
        "classified_clause_rows": classified_rows,
        "encoded_clause_rows": encoded_rows,
        "algorithmic_gap_rows": gap_rows,
        "unencoded_gap_rows": unencoded_gap_rows,
        "encoded_clause_pct": round(100.0 * encoded_rows / classified_rows, 1)
        if classified_rows
        else 0.0,
        "gap_pct_of_classified": round(100.0 * gap_rows / classified_rows, 1)
        if classified_rows
        else 0.0,
        "prose_rules_on_disk": rules_on_disk,
        "manifest_traced_clause_count": manifest_stats.get("manifest_traced_clause_count"),
        "corpus_export_rows": _l22_corpus_row_count(),
        "honesty_note": (
            "§2.2 payment motors share one Gate B manifest; "
            f"{rules_on_disk} JSON rules trace "
            f"{manifest_stats.get('manifest_traced_clause_count', 0):,} clause IDs. "
            "§2.2.2.B session-fraction stays PARTIAL (session_pricing_2_2_2_B)."
        ),
    }


def _specialty_materials_partial_engine_summary(clause_frame: pl.DataFrame) -> dict[str, Any]:
    from src.bilun.domain.prose_rules.specialty_materials import load_specialty_materials_rules

    manifest_stats = _load_prose_manifest_stats("L4.4_specialty_prose_encoded_manifest.json")
    rules_on_disk = len(load_specialty_materials_rules().get("rules") or [])
    summary = _prose_partial_engine_summary(
        rule_id="specialty_materials_prose",
        clause_frame=clause_frame,
        registry_status=RULE_BY_ID["specialty_materials_prose"].coverage_status,
        prose_rules_on_disk=rules_on_disk,
        manifest_traced_clause_count=manifest_stats.get("manifest_traced_clause_count"),
        honesty_note=(
            "L4.4 export subset is 84 deontic §3.3 rows; manifest traces all of them while "
            f"{rules_on_disk} JSON rules cover branch themes (3.3.1–3.3.4). "
            "Catalog pricing (specialty_materials) remains separate."
        ),
    )
    summary["corpus_export_rows"] = 84
    return summary


def _gap_composition_summary(clause_frame: pl.DataFrame) -> dict[str, Any]:
    """Wave 4 scope-closure footnote: true gaps vs registry-partial rows."""
    has_cols = {"has_algorithmic_gap", "has_rule_encoding"}.issubset(set(clause_frame.columns))
    total_gaps = (
        clause_frame.filter(pl.col("has_algorithmic_gap") == True).height
        if "has_algorithmic_gap" in clause_frame.columns
        else 0
    )
    true_gaps = (
        clause_frame.filter(
            (pl.col("has_algorithmic_gap") == True)
            & (pl.col("has_rule_encoding") == False)
        ).height
        if has_cols
        else total_gaps
    )
    drug_gaps = (
        clause_frame.filter(
            (pl.col("has_algorithmic_gap") == True)
            & (pl.col("primary_rule_id") == "drug_indication_prose")
        ).height
        if total_gaps
        else 0
    )
    drug_true_gaps = (
        clause_frame.filter(
            (pl.col("has_algorithmic_gap") == True)
            & (pl.col("has_rule_encoding") == False)
            & (pl.col("primary_rule_id") == "drug_indication_prose")
        ).height
        if has_cols
        else 0
    )
    non_algorithmic_rows = (
        clause_frame.filter(pl.col("coverage_status") == "non_algorithmic").height
        if "coverage_status" in clause_frame.columns
        else 0
    )
    drug_gap_pct = round(100.0 * drug_gaps / total_gaps, 1) if total_gaps else 0.0
    return {
        "total_algorithmic_gaps": total_gaps,
        "total_true_gaps": true_gaps,
        "drug_indication_gap_rows": drug_gaps,
        "drug_indication_true_gap_rows": drug_true_gaps,
        "drug_indication_gap_pct_of_gaps": drug_gap_pct,
        "optimizer_gaps_excluding_drug": max(total_gaps - drug_gaps, 0),
        "non_algorithmic_clause_rows": non_algorithmic_rows,
        "footnote_en": (
            f"True algorithmic gaps (unencoded): {true_gaps:,}. "
            f"Registry-partial rows flagged: {total_gaps:,} "
            f"({drug_gaps:,} drug_indication_prose). "
            f"{non_algorithmic_rows:,} clauses are intentionally non-algorithmic "
            "(§5 admin, provizyon, definitions, RG amendment headers)."
        ),
        "footnote_tr": (
            f"Gerçek algoritmik boşluklar (kodlanmamış): {true_gaps:,}. "
            f"Kayıt-kısmi işaretli satırlar: {total_gaps:,} "
            f"({drug_gaps:,} ilaç endikasyon metni). "
            f"{non_algorithmic_rows:,} hüküm bilinçli olarak algoritmik değil "
            "(§5 idari, provizyon, tanım, RG mülga/değişiklik satırları)."
        ),
    }


def _drug_indication_partial_engine_summary(clause_frame: pl.DataFrame) -> dict[str, Any]:
    """Honest drug-indication engine rollup: registry status vs manifest encoding."""
    from src.bilun.domain.prose_rules.drug_indication import (
        drug_indication_coverage_scope,
        drug_indication_registry_promotion_gate,
    )
    from src.bilun.domain.sut.rule_registry import RULE_BY_ID

    from .coverage_evidence import build_drug_coverage_evidence, coverage_evidence_summary
    from ..prose_rules.drug_indication import list_drug_indication_rules

    evidence = build_drug_coverage_evidence(clause_frame, list_drug_indication_rules())
    scope = drug_indication_coverage_scope()
    registry_status = RULE_BY_ID["drug_indication_prose"].coverage_status
    di = clause_frame.filter(pl.col("primary_rule_id") == "drug_indication_prose")
    classified_rows = di.height
    gap_rows = (
        di.filter(pl.col("has_algorithmic_gap") == True).height
        if "has_algorithmic_gap" in di.columns
        else 0
    )
    encoded_rows = (
        di.filter(pl.col("has_rule_encoding") == True).height
        if "has_rule_encoding" in di.columns
        else 0
    )
    unencoded_gap_rows = (
        di.filter(
            (pl.col("has_algorithmic_gap") == True)
            & (pl.col("has_rule_encoding") == False)
        ).height
        if {"has_algorithmic_gap", "has_rule_encoding"}.issubset(set(di.columns))
        else gap_rows
    )
    deferred_gap_rows = (
        di.filter(
            (pl.col("has_algorithmic_gap") == False)
            & (pl.col("has_rule_encoding") == False)
        ).height
        if {"has_algorithmic_gap", "has_rule_encoding"}.issubset(set(di.columns))
        else 0
    )
    emr_blocked_rows = (
        di.filter(pl.col("emr_blocked") == True).height
        if "emr_blocked" in di.columns
        else 0
    )
    promotion = drug_indication_registry_promotion_gate(clause_frame)

    return {
        "rule_id": "drug_indication_prose",
        "registry_status": registry_status,
        "prose_engine_status": scope.get("prose_engine_status", registry_status),
        "classified_clause_rows": classified_rows,
        "encoded_clause_rows": encoded_rows,
        "deferred_gap_rows": deferred_gap_rows,
        "true_gap_rows": unencoded_gap_rows,
        "algorithmic_gap_rows": gap_rows,
        "unencoded_gap_rows": unencoded_gap_rows,
        "emr_blocked_rows": emr_blocked_rows,
        "registry_promotion_gate": promotion,
        "coverage_evidence": coverage_evidence_summary(evidence),
        "encoded_clause_pct": round(100.0 * encoded_rows / classified_rows, 1)
        if classified_rows
        else 0.0,
        "gap_pct_of_classified": round(100.0 * gap_rows / classified_rows, 1)
        if classified_rows
        else 0.0,
        "prose_rules_on_disk": scope.get("pilot_rule_count", 0),
        "tier_b_rule_count": scope.get("tier_b_rule_count", 0),
        "tier_a_pending_count": scope.get("tier_a_pending_count", 0),
        "tier_b_pending_count": scope.get("tier_b_pending_count", 0),
        "encode_tier_c_deferred_count": scope.get("encode_tier_c_deferred_count", 0),
        "section_4.2.14.C_clause_total": scope.get("section_4.2.14.C_clause_total", 828),
        "clause_trace_complete": scope.get("clause_trace_complete", False),
        "subsection_coverage": scope.get("subsection_coverage") or {},
        "honesty_note": (
            f"Registry is {registry_status}; "
            f"{encoded_rows:,} rows encoded, {deferred_gap_rows:,} tier-C/structural deferred, "
            f"{unencoded_gap_rows:,} true algorithmic gaps. "
            f"{emr_blocked_rows:,} EMR-blocked (clinical data required)."
        ),
    }




def build_partial_engine_summaries(clause_frame: pl.DataFrame) -> dict[str, Any]:
    return {
        "drug_indication_prose": _drug_indication_partial_engine_summary(clause_frame),
        "material_bundling_prose": _material_bundling_partial_engine_summary(clause_frame),
        "specialty_materials_prose": _specialty_materials_partial_engine_summary(clause_frame),
        "payment_method_2_2": _payment_method_partial_engine_summary(clause_frame),
        "copay_general_1_8": _copay_exemption_partial_engine_summary(clause_frame),
    }


def build_gap_composition_summary(clause_frame: pl.DataFrame) -> dict[str, Any]:
    return _gap_composition_summary(clause_frame)
