"""Gate B extraction helpers for L2.2 §2.2 payment method prose."""

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

_SECTION_PREFIX = "2.2"
_TEXT_TRUNC = 240
_DEONTIC_MODALITIES = frozenset({"MUST_BILL", "MUST_NOT_BILL", "NO_PAY", "MAY_BILL"})
_PAYMENT_KEYWORDS = (
    "tanıya dayalı işlem",
    "hizmet başına ödeme",
    "hizmet başı",
    "ek-2/c",
    "ek-2/b",
    "ek-2/a",
    "faturalandır",
    "ödeme yöntemi",
    "yatarak tedavi",
    "ayakta tedavi",
    "basamak",
    "gündüz yatak",
    "yatak bedeli",
)
_ENCODED_CLAUSE_BY_SUT_SECTION: dict[str, list[str]] = {
    "2.2.1.B-1.a": ["C000571"],
    "2.2.1.B-1.b": ["C000572"],
    "2.2.2.(1)": ["C000633"],
    "2.2.2.(2)": ["C000634"],
}


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _section_prefix_for_sut_section(sut_section: str) -> str:
    if sut_section.startswith("2.2.1.B-1"):
        return "2.2.1.B-1"
    if sut_section.startswith("2.2.2"):
        return "2.2.2"
    return sut_section


def _fikra_marker(sut_section: str) -> str | None:
    if sut_section.endswith(".a"):
        return "a)"
    if sut_section.endswith(".b"):
        return "b)"
    match = re.search(r"\((\d+)\)$", sut_section)
    if match:
        return f"({match.group(1)})"
    return None


def _text_matches_sut_section(text: str, sut_section: str) -> bool:
    stripped = str(text or "").lstrip()
    marker = _fikra_marker(sut_section)
    if marker and stripped.startswith(marker):
        return True
    normalized = _normalize_tr(text)
    if sut_section == "2.2.1.B-1.a":
        return "ek-2/c" in normalized and "tanıya dayalı" in normalized and "sadece" not in normalized
    if sut_section == "2.2.1.B-1.b":
        return "sadece" in normalized and "ek-2/b" in normalized
    if sut_section == "2.2.2.(1)":
        return stripped.startswith("(1)") and "yatarak" in normalized
    if sut_section == "2.2.2.(2)":
        return stripped.startswith("(2)") and "üçüncü basamak" in normalized
    return False


def map_rule_to_clause_ids(
    rule: dict[str, Any],
    candidates: pl.DataFrame,
    *,
    text_col: str,
) -> list[str]:
    """Resolve gate_b_sources for one payment_method JSON rule."""
    sut_section = str(rule.get("sut_section") or rule.get("rule_id") or "")
    hardcoded = _ENCODED_CLAUSE_BY_SUT_SECTION.get(sut_section)
    if hardcoded:
        in_force = set(candidates["clause_id"].cast(str).to_list())
        return [clause_id for clause_id in hardcoded if clause_id in in_force]

    section_prefix = _section_prefix_for_sut_section(sut_section)
    subset = candidates.filter(pl.col("section_id").str.starts_with(section_prefix))
    hits: list[str] = []
    for record in subset.iter_rows(named=True):
        text = str(record.get(text_col) or record.get("text_tr") or "")
        if _text_matches_sut_section(text, sut_section):
            hits.append(str(record["clause_id"]))
    return hits


def map_rules_to_clause_ids(
    rules: list[dict[str, Any]],
    candidates: pl.DataFrame,
    *,
    text_col: str,
) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for rule in rules:
        rule_id = str(rule.get("rule_id") or "")
        if not rule_id:
            continue
        mapping[rule_id] = map_rule_to_clause_ids(rule, candidates, text_col=text_col)
    return mapping


def _payment_kind_hint(text: str, section_id: str) -> str:
    normalized = _normalize_tr(text)
    if section_id.startswith("2.2.2.B") or "seans" in normalized:
        return "session"
    if "üçüncü basamak" in normalized and "ek-2/b" in normalized:
        return "overridable"
    if "sadece" in normalized and "ek-2/b" in normalized:
        return "itemized"
    if "ek-2/c" in normalized and "tanıya dayalı" in normalized:
        return "package"
    if "hizmet başına" in normalized or "hizmet başı" in normalized:
        return "itemized"
    if "ek-2/c" in normalized and "ek-2/b" in normalized:
        return "mixed"
    if any(kw in normalized for kw in ("faturalandır", "ödeme", "yatak bedeli")):
        return "payment_general"
    return "other"


def _encode_priority(
    *,
    clause_id: str,
    encoded_clause_ids: set[str],
    deontic: str,
    payment_kind: str,
) -> str:
    if clause_id in encoded_clause_ids:
        return "skip_already_encoded"
    if payment_kind == "session":
        return "defer_session_pricing"
    if deontic in _DEONTIC_MODALITIES and payment_kind in {
        "package",
        "itemized",
        "overridable",
        "mixed",
        "payment_general",
    }:
        return "p1_encode"
    if deontic in _DEONTIC_MODALITIES:
        return "p2_encode"
    return "reference"


def load_candidate_clauses(clauses_path: Path) -> pl.DataFrame:
    """§2.2 in-force rows for Gate B export."""
    df = in_force_polars_filter(pl.read_parquet(clauses_path))
    return df.filter(pl.col("section_id").str.starts_with(_SECTION_PREFIX))


def enrich_gate_b_dataframe(
    hit: pl.DataFrame,
    *,
    encoded_clause_ids: set[str] | None = None,
) -> pl.DataFrame:
    """Add payment_kind_hint and encode_priority for Gate B CSV outputs."""
    encoded = encoded_clause_ids or set()
    text_col = regulatory_text_column(hit)
    rows: list[dict[str, Any]] = []

    for record in hit.iter_rows(named=True):
        text = str(record.get(text_col) or record.get("text_tr") or "")
        clause_id = str(record.get("clause_id") or "")
        section_id = str(record.get("section_id") or "")
        deontic = str(record.get("deontic_modality") or "")
        payment_kind = _payment_kind_hint(text, section_id)
        rows.append(
            {
                "clause_id": clause_id,
                "section_id": section_id,
                "text_tr": text[:_TEXT_TRUNC],
                "deontic_modality": deontic,
                "payment_kind_hint": payment_kind,
                "encode_priority": _encode_priority(
                    clause_id=clause_id,
                    encoded_clause_ids=encoded,
                    deontic=deontic,
                    payment_kind=payment_kind,
                ),
            }
        )

    return pl.DataFrame(rows)


def gate_b_summary(enriched: pl.DataFrame) -> dict[str, int]:
    summary = {"total_rows": len(enriched)}
    for priority in enriched["encode_priority"].unique().to_list():
        summary[str(priority)] = int(
            enriched.filter(pl.col("encode_priority") == priority).height
        )
    return summary


def attach_gate_b_sources(
    rules: list[dict[str, Any]],
    mapping: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Return rules with gate_b_sources and per-rule mapping."""
    updated: list[dict[str, Any]] = []
    per_rule: dict[str, list[str]] = {}
    for rule in rules:
        rule_copy = dict(rule)
        rule_id = str(rule.get("rule_id") or "")
        mapped = list(mapping.get(rule_id) or [])
        existing = list(rule.get("gate_b_sources") or [])
        sources = mapped if mapped else existing
        rule_copy["gate_b_sources"] = sources
        per_rule[rule_id] = sources
        updated.append(rule_copy)
    return updated, per_rule


def build_encoded_manifest(
    *,
    rules: list[dict[str, Any]],
    per_rule_sources: dict[str, list[str]],
) -> dict[str, Any]:
    encoded = sorted(
        {
            clause_id
            for sources in per_rule_sources.values()
            for clause_id in sources
        }
    )
    return {
        "manifest_version": "wave2-v1",
        "rule_set_id": "payment_method_2_2",
        "scope_note": f"§2.2 package vs itemized vs tier-override ({len(rules)} JSON rules)",
        "rules_in_json": len(rules),
        "gate_b_sources_encoded": encoded,
        "encoded_clause_ids": encoded,
        "gate_b_sources_by_rule": per_rule_sources,
        "related_rule_sets": ["session_pricing_2_2_2_B.json"],
    }


def run_gate_b_pipeline(
    *,
    clauses_path: Path,
    prose_json_path: Path,
    corpus_csv_path: Path,
    manifest_path: Path,
    write_prose_json: bool = True,
) -> dict[str, Any]:
    candidates = load_candidate_clauses(clauses_path)
    text_col = regulatory_text_column(candidates)

    payload = json.loads(prose_json_path.read_text(encoding="utf-8"))
    rules = list(payload.get("rules") or [])
    mapping = map_rules_to_clause_ids(rules, candidates, text_col=text_col)
    updated_rules, per_rule_sources = attach_gate_b_sources(rules, mapping)
    encoded_ids = {
        clause_id
        for sources in per_rule_sources.values()
        for clause_id in sources
    }

    enriched = enrich_gate_b_dataframe(candidates, encoded_clause_ids=encoded_ids)
    summary = gate_b_summary(enriched)
    manifest = build_encoded_manifest(rules=updated_rules, per_rule_sources=per_rule_sources)

    corpus_csv_path.parent.mkdir(parents=True, exist_ok=True)
    enriched.write_csv(corpus_csv_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if write_prose_json:
        payload["rules"] = updated_rules
        prose_json_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return {
        "summary": summary,
        "manifest": manifest,
        "per_rule_sources": per_rule_sources,
    }


def main() -> None:
    result = run_gate_b_pipeline(
        clauses_path=_PROJECT_ROOT / "data/gazette/sut_clauses.parquet",
        prose_json_path=_PROJECT_ROOT / "data/gazette/prose_rules/payment_method_2_2.json",
        corpus_csv_path=_PROJECT_ROOT / "data/gazette/prose_corpus/L2.2_payment_method_prose.csv",
        manifest_path=_PROJECT_ROOT / "data/gazette/prose_manifests/L2.2_payment_method_encoded_manifest.json",
    )
    summary = result["summary"]
    encoded = result["manifest"]["gate_b_sources_encoded"]
    print(f"Wrote {summary['total_rows']} corpus rows")
    print(f"Encoded clause IDs ({len(encoded)}): {', '.join(encoded)}")
    for rule_id, sources in sorted(result["per_rule_sources"].items()):
        print(f"  {rule_id}: {sources}")


if __name__ == "__main__":
    main()
