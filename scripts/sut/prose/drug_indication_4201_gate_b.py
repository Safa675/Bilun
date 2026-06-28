"""Gate B export + manifest bootstrap for §4.2.1 rheumatology / biologic drug indication pilot."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.drug_indication_gate_b import (  # noqa: E402
    _encode_tier,
    _heuristic_inn,
    infer_defer_themes,
)

_SECTION_421_RE = re.compile(r"^4\.2\.1(?:[^0-9]|$)")
_MOTOR = "drug_indication_prose"
_DEONTIC_MODALITIES = frozenset(
    {"MUST_BILL", "MUST_NOT_BILL", "NO_PAY", "MAY_BILL", "PROHIBITED", "REGULATORY_ACTION"}
)
_DRUG_KEYWORDS = (
    "leflunomid",
    "altin preparat",
    "altın preparat",
    "anti-tnf",
    "anti tnf",
    "rituksimab",
    "abatasept",
    "ustekinumab",
    "tofacitinib",
    "kanakinumab",
    "anakinra",
    "tosilizumab",
    "infliksimab",
    "adalimumab",
    "etanersept",
    "golimumab",
    "sertolizumab",
    "sekukinumab",
    "vedolizumab",
    "apremilast",
    "romatoid",
    "psoriatik",
    "ankilozan",
    "spondilit",
    "crohn",
    "ulseratif",
    "kolit",
    "uveit",
    "psoriazis",
    "biyolojik",
    "ilaç",
    "ilac",
    "rapor",
    "reçete",
    "recete",
)
_RHEUM_INN_TOKENS = (
    "leflunomid",
    "altin preparat",
    "altın preparat",
    "infliksimab",
    "adalimumab",
    "etanersept",
    "golimumab",
    "sertolizumab",
    "rituksimab",
    "abatasept",
    "tosilizumab",
    "ustekinumab",
    "tofacitinib",
    "barisitinib",
    "upadasitinib",
    "anakinra",
    "kanakinumab",
    "vedolizumab",
    "apremilast",
    "sekukinumab",
)


def is_421_proper(section_id: str) -> bool:
    """True for §4.2.1 proper — excludes 4.2.10–4.2.19 false prefix matches."""
    return bool(_SECTION_421_RE.match(str(section_id or "")))


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _matches_drug_keyword(text: str) -> bool:
    normalized = _normalize_tr(text)
    return any(keyword in normalized for keyword in _DRUG_KEYWORDS)


def _drug_keyword_density(text: str) -> int:
    normalized = _normalize_tr(text)
    return sum(1 for keyword in _DRUG_KEYWORDS if keyword in normalized)


def _has_report_signal(text: str) -> bool:
    normalized = _normalize_tr(text)
    return "rapor" in normalized or "reçete" in normalized or "recete" in normalized


def _in_force_clause_ids(clauses_path: Path) -> frozenset[str]:
    """In-force §4.2.1 proper clause IDs from coverage parquet (matches gap_refresh)."""
    coverage_path = clauses_path.parent / "sut_clause_coverage.parquet"
    if not coverage_path.is_file():
        return frozenset()
    coverage = pl.read_parquet(coverage_path)
    motor = coverage.filter(
        (pl.col("primary_rule_id") == _MOTOR)
        & pl.col("section_id").map_elements(is_421_proper, return_dtype=pl.Boolean)
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def _encode_tier_for_clause(text: str, *, section_id: str) -> tuple[str, str]:
    inn = _heuristic_inn(text)
    tier = _encode_tier(text, inn)
    if tier == "C" and is_421_proper(section_id):
        normalized = _normalize_tr(text)
        if inn and _has_report_signal(text):
            return "A", inn
        if any(token in normalized for token in _RHEUM_INN_TOKENS) and _has_report_signal(text):
            return "A", inn or "biyolojik_ajan"
        if "anti-tnf" in normalized or "anti tnf" in normalized:
            if _has_report_signal(text):
                return "A", inn or "anti_tnf"
    return tier, inn


def _signal_score(*, deontic: str, text: str, tier: str) -> int:
    score = _drug_keyword_density(text)
    if deontic in _DEONTIC_MODALITIES:
        score += 3
    if _has_report_signal(text):
        score += 2
    if tier == "A":
        score += 2
    return score


def export_4201_candidates(
    clauses_path: Path,
    *,
    encoded_clause_ids: frozenset[str] | None = None,
) -> pl.DataFrame:
    """Export in-force §4.2.1 proper rows sorted by deontic + drug-keyword signal."""
    encoded_clause_ids = encoded_clause_ids or frozenset()
    in_force = _in_force_clause_ids(clauses_path)
    clauses = pl.read_parquet(clauses_path)
    section = clauses.filter(
        pl.col("section_id").map_elements(is_421_proper, return_dtype=pl.Boolean)
    )
    if in_force:
        section = section.filter(pl.col("clause_id").is_in(list(in_force)))
    if section.is_empty():
        return pl.DataFrame()

    rows: list[dict[str, Any]] = []
    for record in section.iter_rows(named=True):
        clause_id = str(record.get("clause_id") or "")
        section_id = str(record.get("section_id") or "")
        text = str(record.get("text_tr") or "")
        deontic = str(record.get("deontic_modality") or "")

        tier, inn = _encode_tier_for_clause(text, section_id=section_id)
        defer_themes = infer_defer_themes(text) if tier == "C" else []
        if clause_id in encoded_clause_ids:
            encode_priority = "skip_already_encoded"
        elif tier == "C":
            encode_priority = "defer_tier_c"
        elif tier == "A":
            encode_priority = "p1_encode"
        else:
            encode_priority = "p2_encode"

        rows.append(
            {
                "clause_id": clause_id,
                "section_id": section_id,
                "deontic_modality": deontic,
                "text_tr": text,
                "heuristic_inn": inn,
                "encode_tier": tier,
                "encode_priority": encode_priority,
                "signal_score": _signal_score(deontic=deontic, text=text, tier=tier),
                "defer_themes": ",".join(defer_themes) if defer_themes else "",
            }
        )

    return (
        pl.DataFrame(rows)
        .sort(["signal_score", "clause_id"], descending=[True, False])
        if rows
        else pl.DataFrame()
    )


def _encoded_clause_ids_from_rules(rules: list[dict[str, Any]]) -> set[str]:
    encoded: set[str] = set()
    for rule in rules:
        for clause_id in rule.get("gate_b_sources") or []:
            encoded.add(str(clause_id))
    return encoded


def build_4201_manifest(
    gate_b_frame: pl.DataFrame,
    rules: list[dict[str, Any]],
    *,
    effective_date: str,
) -> dict[str, Any]:
    """Manifest for §4.2.1 pilot — encoded pilot rules + tier_a_pending + Tier C deferred."""
    encoded_ids = _encoded_clause_ids_from_rules(rules)
    rules_by_clause: dict[str, list[str]] = {}
    for rule in rules:
        rule_id = str(rule.get("rule_id") or "")
        for clause_id in rule.get("gate_b_sources") or []:
            rules_by_clause.setdefault(str(clause_id), []).append(rule_id)

    traces: list[dict[str, Any]] = []
    tier_a_pending: list[str] = []
    tier_b_pending: list[str] = []
    tier_c_deferred: list[str] = []

    for row in gate_b_frame.iter_rows(named=True):
        clause_id = str(row.get("clause_id") or "")
        encode_tier = str(row.get("encode_tier") or "C")
        text = str(row.get("text_tr") or "")
        if clause_id in encoded_ids:
            status = "encoded"
        elif encode_tier == "A":
            status = "tier_a_pending"
            tier_a_pending.append(clause_id)
        elif encode_tier == "B":
            status = "tier_b_pending"
            tier_b_pending.append(clause_id)
        else:
            status = "tier_c_deferred"
            tier_c_deferred.append(clause_id)

        entry: dict[str, Any] = {
            "clause_id": clause_id,
            "section_id": str(row.get("section_id") or ""),
            "encode_tier": encode_tier,
            "manifest_status": status,
            "heuristic_inn": str(row.get("heuristic_inn") or ""),
            "signal_score": int(row.get("signal_score") or 0),
        }
        if status == "encoded":
            entry["linked_rule_ids"] = sorted(rules_by_clause.get(clause_id, []))
        elif status == "tier_c_deferred":
            themes = infer_defer_themes(text)
            entry["defer_themes"] = themes
            labels = ", ".join(themes) if themes else "clinical_pathway"
            entry["defer_reason"] = (
                f"Deferred — requires structured ingest for: {labels}. "
                "Tier C manifest-only until EMR fields support pathway."
            )
        traces.append(entry)

    return {
        "manifest_version": "r5-a1-v1",
        "section_id": "4.2.1",
        "effective_date": effective_date,
        "rules_in_json": len(rules),
        "section_4.2.1_clause_total": gate_b_frame.height,
        "section_clause_total": gate_b_frame.height,
        "encoded_clause_count": len(encoded_ids),
        "encoded_clause_ids": sorted(encoded_ids),
        "gate_b_sources_encoded": sorted(encoded_ids),
        "tier_a_pending_clause_ids": sorted(tier_a_pending),
        "tier_b_pending_clause_ids": sorted(tier_b_pending),
        "tier_c_deferred_clause_ids": sorted(tier_c_deferred),
        "tier_a_pending_count": len(tier_a_pending),
        "tier_b_pending_count": len(tier_b_pending),
        "tier_c_deferred_count": len(tier_c_deferred),
        "clause_traces": traces,
    }


def gate_b_summary(enriched: pl.DataFrame) -> dict[str, int]:
    if enriched.is_empty():
        return {"total": 0}
    summary: dict[str, int] = {"total": enriched.height}
    for col in ("encode_tier", "encode_priority"):
        for key, count in enriched.group_by(col).len().iter_rows():
            summary[f"{col}:{key}"] = int(count)
    return summary


def _resolve_batch_rules(
    rules_path: Path | None,
    batch_rules: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if batch_rules is not None:
        return batch_rules
    if rules_path is None:
        return []
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    return [
        rule
        for rule in (payload.get("rules") or [])
        if is_421_proper(str(rule.get("sut_section") or ""))
    ]


def _gap_clause_ids(clauses_path: Path) -> frozenset[str]:
    """Motor-bound §4.2.1 proper clause IDs with ``has_rule_encoding=false``."""
    coverage_path = clauses_path.parent / "sut_clause_coverage.parquet"
    if not coverage_path.is_file():
        return frozenset()
    coverage = pl.read_parquet(coverage_path)
    motor = coverage.filter(
        (pl.col("primary_rule_id") == _MOTOR)
        & pl.col("section_id").map_elements(is_421_proper, return_dtype=pl.Boolean)
        & ~pl.col("has_rule_encoding")
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def _manifest_status_ids(manifest: dict[str, Any]) -> dict[str, frozenset[str]]:
    encoded = frozenset(str(cid) for cid in manifest.get("encoded_clause_ids") or [])
    tier_c = frozenset(str(cid) for cid in manifest.get("tier_c_deferred_clause_ids") or [])
    tier_a = frozenset(str(cid) for cid in manifest.get("tier_a_pending_clause_ids") or [])
    tier_b = frozenset(str(cid) for cid in manifest.get("tier_b_pending_clause_ids") or [])
    return {
        "encoded": encoded,
        "tier_c_deferred": tier_c,
        "tier_a_pending": tier_a,
        "tier_b_pending": tier_b,
    }


def scan_4201_tier_ab_promotions(
    gate_b_frame: pl.DataFrame,
    *,
    encoded_clause_ids: frozenset[str] | set[str],
) -> list[dict[str, Any]]:
    """Find Tier C gaps that look actionable as Tier A/B with the existing schema."""
    encoded = {str(cid) for cid in encoded_clause_ids}
    promotions: list[dict[str, Any]] = []
    tier_c = gate_b_frame.filter(pl.col("encode_tier") == "C")
    for row in tier_c.iter_rows(named=True):
        clause_id = str(row.get("clause_id") or "")
        if clause_id in encoded:
            continue
        text = str(row.get("text_tr") or "")
        section_id = str(row.get("section_id") or "")
        deontic = str(row.get("deontic_modality") or "")
        inn = _heuristic_inn(text)
        raw_tier = _encode_tier(text, inn)
        reasons: list[str] = []
        if raw_tier in {"A", "B"}:
            reasons.append(f"raw_tier={raw_tier}")
        if (
            deontic in _DEONTIC_MODALITIES
            and inn
            and _has_report_signal(text)
        ):
            reasons.append("deontic_inn_report")
        promoted_tier, promoted_inn = _encode_tier_for_clause(text, section_id=section_id)
        if promoted_tier in {"A", "B"} and promoted_tier != "C":
            reasons.append(f"421_heuristic={promoted_tier}")
        if reasons:
            promotions.append(
                {
                    "clause_id": clause_id,
                    "section_id": section_id,
                    "heuristic_inn": inn or promoted_inn,
                    "proposed_tier": promoted_tier if promoted_tier in {"A", "B"} else raw_tier,
                    "reasons": reasons,
                    "text_tr": text,
                }
            )
    return promotions


def audit_4201_gap_parity(
    clauses_path: Path,
    manifest: dict[str, Any],
    *,
    gate_b_frame: pl.DataFrame | None = None,
) -> dict[str, Any]:
    """Parity audit: every coverage gap must be ``encoded`` or ``tier_c_deferred``."""
    gap_ids = _gap_clause_ids(clauses_path)
    statuses = _manifest_status_ids(manifest)
    trace_ids = {str(t.get("clause_id") or "") for t in manifest.get("clause_traces") or []}

    honest_gap_ids = statuses["encoded"] | statuses["tier_c_deferred"]
    untraced = sorted(
        gap_ids - honest_gap_ids - statuses["tier_a_pending"] - statuses["tier_b_pending"]
    )
    misclassified_ab = sorted(
        (statuses["tier_a_pending"] | statuses["tier_b_pending"]) & gap_ids
    )
    missing_from_traces = sorted(gap_ids - trace_ids)
    encoded_still_gap = sorted(gap_ids & statuses["encoded"])

    defer_reason_gaps = [
        str(t.get("clause_id") or "")
        for t in manifest.get("clause_traces") or []
        if t.get("manifest_status") == "tier_c_deferred"
        and (not t.get("defer_reason") or t.get("defer_themes") is None)
    ]

    frame = gate_b_frame if gate_b_frame is not None else export_4201_candidates(clauses_path)
    export_ids = set(frame["clause_id"].to_list())
    gaps_missing_export = sorted(gap_ids - export_ids)

    promotions = scan_4201_tier_ab_promotions(
        frame,
        encoded_clause_ids=statuses["encoded"],
    )

    return {
        "gap_count": len(gap_ids),
        "encoded_count": len(statuses["encoded"]),
        "tier_c_deferred_count": len(statuses["tier_c_deferred"]),
        "untraced_before": len(untraced) + len(misclassified_ab) + len(gaps_missing_export),
        "untraced_clause_ids": untraced,
        "misclassified_ab_gap_ids": misclassified_ab,
        "missing_from_traces": missing_from_traces,
        "gaps_missing_export": gaps_missing_export,
        "encoded_still_gap": encoded_still_gap,
        "defer_reason_gaps": defer_reason_gaps,
        "defer_reason_gap_count": len(defer_reason_gaps),
        "promotion_candidates": promotions,
        "promotion_count": len(promotions),
    }


def repair_4201_manifest_untraced(
    manifest: dict[str, Any],
    gate_b_frame: pl.DataFrame,
    *,
    gap_clause_ids: frozenset[str] | None = None,
) -> tuple[dict[str, Any], int]:
    """Add ``tier_c_deferred`` traces for gap IDs missing honest manifest coverage."""
    gap_ids = gap_clause_ids if gap_clause_ids is not None else frozenset()
    statuses = _manifest_status_ids(manifest)
    honest = statuses["encoded"] | statuses["tier_c_deferred"]
    pending = statuses["tier_a_pending"] | statuses["tier_b_pending"]
    missing = gap_ids - honest - pending if gap_ids else frozenset()

    trace_by_id = {str(t["clause_id"]): dict(t) for t in manifest.get("clause_traces") or []}
    frame_by_id = {str(r["clause_id"]): r for r in gate_b_frame.iter_rows(named=True)}
    repaired = 0

    for clause_id in sorted(missing):
        row = frame_by_id.get(clause_id)
        text = str((row or {}).get("text_tr") or "")
        themes = infer_defer_themes(text) if text else []
        labels = ", ".join(themes) if themes else "clinical_pathway"
        trace_by_id[clause_id] = {
            "clause_id": clause_id,
            "section_id": str((row or {}).get("section_id") or ""),
            "encode_tier": str((row or {}).get("encode_tier") or "C"),
            "manifest_status": "tier_c_deferred",
            "heuristic_inn": str((row or {}).get("heuristic_inn") or ""),
            "signal_score": int((row or {}).get("signal_score") or 0),
            "defer_themes": themes,
            "defer_reason": (
                f"Deferred — requires structured ingest for: {labels}. "
                "Tier C manifest-only until EMR fields support pathway."
            ),
        }
        repaired += 1

    if not repaired:
        return manifest, 0

    tier_c = sorted(
        cid
        for cid, trace in trace_by_id.items()
        if trace.get("manifest_status") == "tier_c_deferred"
    )
    updated = dict(manifest)
    updated["clause_traces"] = [trace_by_id[cid] for cid in sorted(trace_by_id)]
    updated["tier_c_deferred_clause_ids"] = tier_c
    updated["tier_c_deferred_count"] = len(tier_c)
    return updated, repaired


def normalize_4201_defer_reasons(
    manifest: dict[str, Any],
    gate_b_frame: pl.DataFrame,
) -> tuple[dict[str, Any], int]:
    """Ensure every ``tier_c_deferred`` trace has ``defer_reason`` and ``defer_themes``."""
    frame_by_id = {str(r["clause_id"]): r for r in gate_b_frame.iter_rows(named=True)}
    traces = [dict(t) for t in manifest.get("clause_traces") or []]
    fixed = 0

    for trace in traces:
        if trace.get("manifest_status") != "tier_c_deferred":
            continue
        clause_id = str(trace.get("clause_id") or "")
        row = frame_by_id.get(clause_id)
        text = str((row or {}).get("text_tr") or "")
        needs_reason = not trace.get("defer_reason")
        needs_themes = trace.get("defer_themes") is None
        if not needs_reason and not needs_themes:
            continue
        themes = trace.get("defer_themes")
        if themes is None:
            themes = infer_defer_themes(text) if text else []
            trace["defer_themes"] = themes
        if needs_reason:
            labels = ", ".join(themes) if themes else "clinical_pathway"
            trace["defer_reason"] = (
                f"Deferred — requires structured ingest for: {labels}. "
                "Tier C manifest-only until EMR fields support pathway."
            )
        fixed += 1

    if not fixed:
        return manifest, 0

    updated = dict(manifest)
    updated["clause_traces"] = traces
    return updated, fixed


def _load_4201_rules_from_prose(rules_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    return [
        rule
        for rule in (payload.get("rules") or [])
        if is_421_proper(str(rule.get("sut_section") or ""))
    ]


def run_4201_audit(
    clauses_path: Path,
    rules_path: Path,
    *,
    effective_date: str,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Full §4.2.1 honest-gap audit (parity + Tier A/B promotion scan + defer repair)."""
    rules = _load_4201_rules_from_prose(rules_path)
    frame = export_4201_candidates(clauses_path)
    manifest = build_4201_manifest(frame, rules, effective_date=effective_date)
    before = audit_4201_gap_parity(clauses_path, manifest, gate_b_frame=frame)

    manifest, repaired_untraced = repair_4201_manifest_untraced(
        manifest,
        frame,
        gap_clause_ids=_gap_clause_ids(clauses_path),
    )
    manifest, defer_reason_fixed = normalize_4201_defer_reasons(manifest, frame)
    after = audit_4201_gap_parity(clauses_path, manifest, gate_b_frame=frame)

    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return {
        **after,
        "repaired_untraced": repaired_untraced,
        "defer_reason_fixed": defer_reason_fixed,
        "untraced_before": before["untraced_before"],
        "untraced_after": len(after["untraced_clause_ids"]) + len(after["misclassified_ab_gap_ids"]),
        "promoted_clause_ids": sorted({p["clause_id"] for p in after["promotion_candidates"]}),
    }


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    corpus_csv: Path,
    manifest_path: Path,
    effective_date: str,
    rules_path: Path | None = None,
    batch_rules: list[dict[str, Any]] | None = None,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    resolved = _resolve_batch_rules(rules_path, batch_rules)
    manifest = build_4201_manifest(
        export_4201_candidates(clauses_path),
        resolved,
        effective_date=effective_date,
    )
    encoded = frozenset(manifest["gate_b_sources_encoded"])

    corpus_csv.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    frame = export_4201_candidates(clauses_path, encoded_clause_ids=encoded)
    frame.write_csv(corpus_csv)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return frame, manifest


if __name__ == "__main__":
    import argparse
    from datetime import date

    parser = argparse.ArgumentParser(description="§4.2.1 rheumatology Gate B export")
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Run honest-gap parity audit (Tier C closure)",
    )
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="With --audit, write repaired manifest JSON",
    )
    args = parser.parse_args()

    repo = _PROJECT_ROOT
    clauses = repo / "data/gazette/sut_clauses.parquet"
    rules_path = repo / "data/gazette/prose_rules/drug_indication_prose.json"
    corpus = repo / "data/gazette/prose_corpus/L4.2_drug_indication_4201.csv"
    manifest = repo / "data/gazette/prose_manifests/L4.2_drug_indication_4201_manifest.json"
    effective = date.today().isoformat()

    if args.audit:
        report = run_4201_audit(
            clauses,
            rules_path,
            effective_date=effective,
            manifest_path=manifest if args.write_manifest else None,
        )
        print(
            f"§4.2.1 audit: gaps={report['gap_count']} "
            f"untraced_before={report['untraced_before']} "
            f"untraced_after={report['untraced_after']} "
            f"promotions={report['promotion_count']} "
            f"defer_reason_fixed={report['defer_reason_fixed']}"
        )
        if report["untraced_clause_ids"]:
            print(f"  untraced: {report['untraced_clause_ids']}")
        if report["misclassified_ab_gap_ids"]:
            print(f"  misclassified A/B gaps: {report['misclassified_ab_gap_ids']}")
        if report["promotion_candidates"]:
            for candidate in report["promotion_candidates"][:10]:
                print(
                    f"  promote? {candidate['clause_id']} "
                    f"{candidate['reasons']} inn={candidate['heuristic_inn']}"
                )
        if args.write_manifest:
            print(f"Wrote manifest -> {manifest}")
        raise SystemExit(
            0
            if not report["untraced_clause_ids"] and not report["misclassified_ab_gap_ids"]
            else 1
        )

    frame, manifest_payload = write_gate_b_artifacts(
        clauses_path=clauses,
        rules_path=rules_path,
        corpus_csv=corpus,
        manifest_path=manifest,
        effective_date=effective,
    )
    print(f"Wrote {frame.height} rows -> {corpus}")
    print(
        f"Manifest: {len(manifest_payload['gate_b_sources_encoded'])} encoded "
        f"tier_a_pending={manifest_payload['tier_a_pending_count']} "
        f"tier_c={manifest_payload['tier_c_deferred_count']} -> {manifest}"
    )
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")
