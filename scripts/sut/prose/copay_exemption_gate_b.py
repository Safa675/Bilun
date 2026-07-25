"""Gate B export + manifest bootstrap for L1.8 §1.8 copay rates and exemptions."""

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

from src.bilun.domain.sut.clause_in_force import in_force_polars_filter, regulatory_text_column

_SECTION_PREFIX = "1.8"
_RATE_SECTIONS = frozenset({"1.8.2", "1.8.3", "1.8.4"})
_EXEMPTION_SECTIONS = frozenset({"1.8.1", "1.8.5"})
_EK4D_TEXT_PATTERNS = (r"ek-4/d", r"ek\s*4\s*/\s*d")
_SUT_SECTION_RE = re.compile(r"^(?P<section>[\d.]+)(?:\.\((?P<fikra>\d+)\))?$")

# Compositor runtime modules — manifest traces for honest encode KPI (Phase D0+).
_COMPOSITOR_CLAUSE_TRACES: dict[str, list[str]] = {
    "copay_exemption_ek1a": ["C000361"],
    "copay_exemption_ek4d": ["C000326", "C000362"],
    "copay_exemption_visit_type": ["C000359", "C000360"],
    "copay_exemption_occupational": ["C000355"],
    "copay_exemption_patient_status": [
        "C000365",
        "C000366",
        "C000367",
        "C000369",
        "C000370",
        "C000375",
        "C000378",
        "C000379",
    ],
}


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _category_hint(section_id: str) -> str:
    if section_id in _RATE_SECTIONS or any(
        section_id.startswith(f"{sec}.") for sec in _RATE_SECTIONS
    ):
        return "rate"
    if section_id in _EXEMPTION_SECTIONS or section_id.startswith("1.8.5"):
        return "exemption"
    if section_id == "1.8":
        return "exemption"
    return "rate" if section_id.startswith("1.8.") else "exemption"


def _matches_ek4d_overlap(text: str) -> bool:
    normalized = _normalize_tr(text)
    return any(re.search(pat, normalized) for pat in _EK4D_TEXT_PATTERNS)


def _parse_sut_section(sut_section: str) -> tuple[str, str | None]:
    match = _SUT_SECTION_RE.match(str(sut_section or "").strip())
    if not match:
        return str(sut_section or "").strip(), None
    return match.group("section"), match.group("fikra")


def _fikra_number(text: str) -> str | None:
    match = re.match(r"^\((\d+)\)", str(text or "").strip())
    return match.group(1) if match else None


def clause_ids_for_sut_section(clauses: pl.DataFrame, sut_section: str) -> list[str]:
    """Map ``sut_section`` like ``1.8.2.(1)`` to in-force fıkra clause IDs."""
    section, fikra = _parse_sut_section(sut_section)
    if not section:
        return []

    text_col = regulatory_text_column(clauses)
    scoped = clauses.filter(pl.col("section_id") == section)
    if scoped.is_empty():
        scoped = clauses.filter(pl.col("section_id").str.starts_with(section))

    if fikra:
        hits: list[str] = []
        for row in scoped.filter(pl.col("clause_type") == "fikra").iter_rows(named=True):
            if _fikra_number(str(row.get(text_col) or row.get("text_tr") or "")) == fikra:
                cid = str(row.get("clause_id") or "")
                if cid:
                    hits.append(cid)
        if hits:
            return hits

    if not scoped.is_empty():
        first = scoped.sort("paragraph_index").head(1)
        return [str(first["clause_id"][0])]
    return []


def map_json_rules_to_clause_ids(
    rules_path: Path,
    clauses_path: Path,
) -> dict[str, list[str]]:
    """Return ``rule_id`` → clause IDs for ``copay_general_1_8.json`` rules."""
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    clauses = in_force_polars_filter(pl.read_parquet(clauses_path))
    mapping: dict[str, list[str]] = {}
    for rule in payload.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("rule_id") or "")
        sut_section = str(rule.get("sut_section") or "")
        if not rule_id or not sut_section:
            continue
        explicit = [
            str(clause_id)
            for clause_id in (rule.get("gate_b_sources") or [])
            if str(clause_id).strip()
        ]
        if explicit:
            mapping[rule_id] = explicit
        else:
            mapping[rule_id] = clause_ids_for_sut_section(clauses, sut_section)
    return mapping


def export_copay_exemption_candidates(
    clauses_path: Path,
    *,
    encoded_clause_ids: frozenset[str] | None = None,
) -> pl.DataFrame:
    """Export in-force §1.8 rows with Gate B enrichment columns."""
    encoded_clause_ids = encoded_clause_ids or frozenset()
    clauses = in_force_polars_filter(pl.read_parquet(clauses_path))
    text_col = regulatory_text_column(clauses)
    section = clauses.filter(pl.col("section_id").str.starts_with(_SECTION_PREFIX))

    rows: list[dict[str, Any]] = []
    for record in section.iter_rows(named=True):
        clause_id = str(record.get("clause_id") or "")
        section_id = str(record.get("section_id") or "")
        excerpt = str(record.get(text_col) or record.get("text_tr") or "")
        deontic = str(record.get("deontic_modality") or "")
        ek4d_overlap = _matches_ek4d_overlap(excerpt)

        if clause_id in encoded_clause_ids:
            encode_priority = "skip_already_encoded"
        elif ek4d_overlap and clause_id in _COMPOSITOR_CLAUSE_TRACES.get(
            "copay_exemption_ek4d", []
        ):
            encode_priority = "skip_ek4d_compositor_trace"
        elif ek4d_overlap:
            encode_priority = "flag_ek4d_overlap"
        elif deontic:
            encode_priority = "p1_encode"
        else:
            encode_priority = "defer_reference"

        rows.append(
            {
                "clause_id": clause_id,
                "section_id": section_id,
                "deontic_modality": deontic,
                "category_hint": _category_hint(section_id),
                "encode_priority": encode_priority,
            }
        )

    return pl.DataFrame(rows)


def build_encoded_manifest(
    rules_path: Path,
    clauses_path: Path,
) -> dict[str, Any]:
    """Build ``L1.8_copay_exemption_encoded_manifest.json`` payload."""
    json_traces = map_json_rules_to_clause_ids(rules_path, clauses_path)
    encoded: set[str] = set()
    for clause_ids in json_traces.values():
        encoded.update(clause_ids)
    for clause_ids in _COMPOSITOR_CLAUSE_TRACES.values():
        encoded.update(clause_ids)

    ek4d_overlap = sorted(
        cid
        for cid in encoded
        if cid in _COMPOSITOR_CLAUSE_TRACES.get("copay_exemption_ek4d", [])
    )

    return {
        "rules_in_json": len(json_traces),
        "json_rule_clause_traces": {
            rule_id: (clause_ids[0] if len(clause_ids) == 1 else clause_ids)
            for rule_id, clause_ids in sorted(json_traces.items())
        },
        "compositor_clause_traces": _COMPOSITOR_CLAUSE_TRACES,
        "encoded_clause_ids": sorted(encoded),
        "ek4d_overlap_clause_ids": ek4d_overlap,
    }


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    rules_path: Path,
    corpus_csv: Path,
    manifest_path: Path,
    write_corpus: bool = False,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    manifest = build_encoded_manifest(rules_path, clauses_path)
    encoded = frozenset(manifest["encoded_clause_ids"])

    corpus_csv.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    frame = export_copay_exemption_candidates(clauses_path, encoded_clause_ids=encoded)
    if write_corpus:
        frame.write_csv(corpus_csv)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return frame, manifest


def gate_b_summary(enriched: pl.DataFrame) -> dict[str, int]:
    if enriched.is_empty():
        return {"total": 0}
    summary: dict[str, int] = {"total": enriched.height}
    for key, count in enriched.group_by("encode_priority").len().iter_rows():
        summary[f"encode_priority:{key}"] = int(count)
    for key, count in enriched.group_by("category_hint").len().iter_rows():
        summary[f"category_hint:{key}"] = int(count)
    return summary


if __name__ == "__main__":
    repo = _PROJECT_ROOT
    clauses = repo / "data/gazette/sut_clauses.parquet"
    rules = repo / "data/gazette/prose_rules/copay_general_1_8.json"
    corpus = repo / "data/gazette/prose_corpus/L1.8_copay_exemption_prose.csv"
    manifest = repo / "data/gazette/prose_manifests/L1.8_copay_exemption_encoded_manifest.json"

    frame, manifest_payload = write_gate_b_artifacts(
        clauses_path=clauses,
        rules_path=rules,
        corpus_csv=corpus,
        manifest_path=manifest,
    )
    print(f"Wrote {frame.height} rows -> {corpus}")
    print(
        f"Manifest: {len(manifest_payload['gate_b_sources_encoded'])} encoded clause IDs -> {manifest}"
    )
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")
