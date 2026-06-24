#!/usr/bin/env python3
"""Compile Bucket A (encodable-now) §4.2.14.C Tier-C clauses into JSON rules.

Reads the classification CSV, takes Bucket A clauses, and appends new rules to
drug_indication_prose.json. Each rule uses only existing matcher fields
(drug_names, prescriber_specialties, report_specialties, report_duration_months,
report_required). Combo prohibitions + max-cycle rules use max_applications_per_year
(already supported by the anti-VEGF dose protocol engine).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_CLASSIFICATION_CSV = _PROJECT_ROOT / "data/gazette/prose_corpus/L4.2_oncology_tier_c_classification.csv"
_CLAUSES_PARQUET = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
_RULES_JSON = _PROJECT_ROOT / "data/gazette/prose_rules/drug_indication_prose.json"


def _extract_drugs(text: str) -> list[str]:
    """Extract INN drug names mentioned in clause text (lowercased Turkish)."""
    # Common oncology INNs in §4.2.14.C
    inn_patterns = [
        "filgrastim", "lenograstim", "pegfilgrastim", "lipegfilgrastim",
        "floxuridin", "dasatinib", "nilotinib", "bosutinib", "imatinib",
        "kabazitaksel", "abirateron", "enzalutamid", "everolimus",
        "sunitinib", "sorafenib", "erlotinib", "gefitinib", "dakomitinib",
        "afatinib", "rituximab", "mifamurtide", "gemtuzumab",
        "azasitidin", "desitabin", "brentuksimab", "karfilzomib",
        "iksazomib", "daratumumab", "pomalidomid", "lenalidomid",
        "bortezomib", "tositumomab", "ibritumomab",
        "alemtuzumab", "obinutuzumab", "ofatumumab",
        "vismodegib", "sonidegib", "fotemustin", "bevacizumab",
        "hidroksiüre", "anagrelid", "ruxolitinib",
    ]
    lower = text.lower()
    found = []
    for inn in inn_patterns:
        if inn in lower and inn not in found:
            found.append(inn)
    return found


def _extract_duration(text: str) -> int | None:
    m = re.search(r"(\d+)\s*ay\s*süre", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _extract_prescribers(text: str) -> list[str]:
    """Extract required prescriber/report specialties."""
    lower = text.lower()
    specs = []
    if "tıbbi onkoloji" in lower or "onkoloji uzman" in lower:
        specs.append("tıbbi onkoloji")
    if "hematoloji" in lower:
        specs.append("hematoloji")
    # "tüm uzman hekimlerce" → no specialty restriction (any specialist)
    return specs


def _extract_max_applications(text: str) -> tuple[int | None, str]:
    """Extract max cycle/dose count. Returns (count, kind)."""
    m = re.search(r"(?:maksimum|en\s*fazla)\s+(\d+)\s*(küre|doz|kür)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), m.group(2).lower()
    m = re.search(r"en\s*fazla\s+(\d+)\s*(küre|doz|kür)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)), m.group(2).lower()
    return None, ""


def _is_combo_prohibition(text: str) -> bool:
    return bool(
        re.search(r"(?:ardışık|kombine).{0,40}?(?:kullanılmaz|karşılanmaz|yasak)", text, re.IGNORECASE)
    )


def compile_bucket_a_rules() -> list[dict]:
    """Build new rules from Bucket A clauses."""
    df = pl.read_csv(_CLASSIFICATION_CSV)
    clauses = pl.read_parquet(_CLAUSES_PARQUET)

    bucket_a_ids = df.filter(pl.col("bucket") == "A")["clause_id"].to_list()
    a_clauses = clauses.filter(pl.col("clause_id").is_in(bucket_a_ids)).sort("paragraph_index")

    # Load existing rule_ids to avoid duplicates
    with _RULES_JSON.open(encoding="utf-8") as f:
        existing = json.load(f)
    existing_ids = {r["rule_id"] for r in existing.get("rules", [])}
    existing_sources = set()
    for r in existing.get("rules", []):
        existing_sources.update(r.get("gate_b_sources") or [])

    new_rules: list[dict] = []
    seen_clause_ids: set[str] = set()

    for record in a_clauses.iter_rows(named=True):
        clause_id = record.get("clause_id", "")
        text = str(record.get("text_tr") or "")
        # Skip if this clause is already encoded by an existing rule
        if clause_id in existing_sources:
            continue
        if clause_id in seen_clause_ids:
            continue

        drugs = _extract_drugs(text)
        if not drugs:
            continue  # Non-drug clause (e.g. general chemo dispensing), skip for now

        duration = _extract_duration(text)
        prescribers = _extract_prescribers(text)
        max_count, _ = _extract_max_applications(text)
        is_combo = _is_combo_prohibition(text)

        # Build rule — drug-specific
        drug_key = drugs[0].replace(" ", "_")
        rule_id = f"4.2.14.C.tier_c.{clause_id}.{drug_key}"
        if rule_id in existing_ids:
            continue

        rule: dict = {
            "rule_id": rule_id,
            "sut_section": "4.2.14.C",
            "drug_names": drugs,
            "report_required": True,
            "gate_b_sources": [clause_id],
            "message_tr": text[:200].replace("\n", " ").strip(),
        }

        if prescribers:
            rule["prescriber_specialties"] = prescribers
            rule["report_specialties"] = prescribers
        else:
            # "tüm uzman hekimlerce" → any specialist, board report still needed
            rule["report_specialties"] = ["tıbbi onkoloji", "hematoloji"]

        if duration:
            rule["report_duration_months"] = duration

        if max_count:
            rule["max_applications_per_year"] = max_count

        if is_combo:
            rule["combo_prohibition"] = True

        # ICD-10: default to C00-C97 (cancer) for oncology drugs unless text specifies
        rule["icd10_ranges"] = ["C00-C97"]

        new_rules.append(rule)
        seen_clause_ids.add(clause_id)

    return new_rules


def main() -> None:
    new_rules = compile_bucket_a_rules()
    print(f"Compiled {len(new_rules)} new Bucket A rules")

    with _RULES_JSON.open(encoding="utf-8") as f:
        payload = json.load(f)

    existing_count = len(payload.get("rules", []))
    payload["rules"].extend(new_rules)
    payload["coverage_note"] = (
        f"§4.2.14.C oncology ({len(payload['rules'])} rules incl. Tier-C Bucket A expansion) "
        f"+ §4.2.33 anti-VEGF (21 rules, loaded separately). "
        f"Tier-C Bucket A: prescriber/duration/combo/max-cycle encodable clauses."
    )

    with _RULES_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Updated {_RULES_JSON}: {existing_count} → {len(payload['rules'])} rules")
    print(f"New gate_b_sources: {sum(len(r.get('gate_b_sources', [])) for r in new_rules)} clauses")


if __name__ == "__main__":
    main()
