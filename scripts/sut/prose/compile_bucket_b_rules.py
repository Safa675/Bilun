#!/usr/bin/env python3
"""Compile Bucket B (model-extension) §4.2.14.C Tier-C clauses into JSON rules.

Bucket B clauses require biomarker (HER-2+, CD20+, KRAS) or prior-therapy
(imatinib-resistant, post-transplant) gating — two new DrugClaimLine fields.
This script extracts structured biomarker/prior-therapy requirements from clause
text and appends rules with `required_biomarkers` / `requires_prior_therapy` fields
to drug_indication_prose.json.
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
    inn_patterns = [
        "trastuzumab", "pertuzumab", "trastuzumab emtansin", "tdm1",
        "rituximab", "obinutuzumab", "ofatumumab", "alemtuzumab",
        "cetuximab", "panitumumab", "necitumumab",
        "nilotinib", "dasatinib", "bosutinib", "imatinib",
        "erlotinib", "gefitinib", "afatinib", "osimertinib",
        "vemurafenib", "dabrafenib", "trametinib",
        "everolimus", "temsirolimus",
        "bortezomib", "carfilzomib", "ixazomib", "lenalidomide", "pomalidomide",
        "thalidomide", "daratumumab",
        "fulvestrant", "tamoxifen", "letrozole", "anastrozole", "exemestane",
        "bevacizumab", "sunitinib", "sorafenib", "pazopanib", "regorafenib",
        "gemtuzumab", "brentuximab", "inotuzumab",
        "azacitidine", "decitabine", "venetoclax",
        "fludarabine", "clofarabine", "nelarabine",
        "enzalutamide", "abiraterone", "cabazitaxel",
        "pembrolizumab", "nivolumab", "atezolizumab", "durvalumab",
        "eculizumab", "ravulizumab",
        "interferon", "peginterferon",
        "anagrelide", "ruxolitinib", "hydroxyurea", "hidroksiüre",
    ]
    lower = text.lower()
    found = []
    for inn in inn_patterns:
        if inn in lower and inn not in found:
            found.append(inn)
    return found


def _extract_biomarkers(text: str) -> list[dict]:
    """Extract biomarker requirements as structured {marker, status_any} dicts."""
    lower = text.lower()
    markers: list[dict] = []

    # HER-2 / HER2
    if re.search(r"her\s*-?\s*2\s*(?:immünhistokimya|ihk)?.{0,20}\+3|her2.{0,10}\+3", text, re.IGNORECASE):
        markers.append({"marker": "HER2", "status_any": ["3+", "positive", "pozitif"]})
    elif re.search(r"fish|cish|sish.{0,10}\(\+\)|fish.{0,10}pozitif", text, re.IGNORECASE):
        markers.append({"marker": "HER2", "status_any": ["positive", "pozitif", "FISH+"]})
    elif "her2" in lower or "her-2" in lower:
        markers.append({"marker": "HER2", "status_any": ["positive", "pozitif", "3+"]})

    # HER-2 negatif (for ER+/HER2- drugs like fulvestrant/CDK4/6)
    if re.search(r"her\s*-?\s*2\s*negatif|her2\s*negatif", lower):
        markers.append({"marker": "HER2", "status_any": ["negative", "negatif", "0", "1+"]})

    # Hormon reseptörü / ER+
    if re.search(r"hormon\s*reseptörü\s*pozitif|östrojen\s*reseptör.{0,10}pozitif|er\s*pozitif", lower):
        markers.append({"marker": "ER", "status_any": ["positive", "pozitif"]})

    # CD20+
    if re.search(r"cd\s*20\s*pozitif|cd\s*20\s*\+", lower):
        markers.append({"marker": "CD20", "status_any": ["positive", "pozitif"]})

    # CD30+
    if re.search(r"cd\s*30\s*pozitif|cd\s*30.{0,10}\d", lower):
        markers.append({"marker": "CD30", "status_any": ["positive", "pozitif"]})

    # CD33+
    if re.search(r"cd\s*33\s*pozitif", lower):
        markers.append({"marker": "CD33", "status_any": ["positive", "pozitif"]})

    # KRAS wild-type / mutant
    if re.search(r"kras.{0,20}(wild|yabançı|mutasyon)", lower):
        markers.append({"marker": "KRAS", "status_any": ["wild_type", "wild-type", "mutant", "mutasyon"]})

    # BRAF V600
    if re.search(r"braf.{0,15}v600|braf.{0,15}mutasyon", lower):
        markers.append({"marker": "BRAF", "status_any": ["V600E", "mutant", "mutasyon"]})

    # EGFR mutation
    if re.search(r"egfr.{0,15}mutasyon|egfr.{0,10}pozitif", lower):
        markers.append({"marker": "EGFR", "status_any": ["mutation_positive", "pozitif"]})

    # ALK positive
    if re.search(r"alk.{0,10}pozitif|alk.{0,10}\+", lower):
        markers.append({"marker": "ALK", "status_any": ["positive", "pozitif"]})

    # Philadelphia chromosome / BCR-ABL
    if re.search(r"philadelphia\s*kromozomu\s*pozitif|bcr\s*-?\s*abl\s*pozitif", lower):
        markers.append({"marker": "BCR_ABL", "status_any": ["positive", "pozitif"]})

    # JAK2 V617F
    if re.search(r"jak\s*2\s*v617f|jak2.{0,10}mutasyon", lower):
        markers.append({"marker": "JAK2", "status_any": ["V617F", "mutasyon"]})

    # 17p deletion
    if re.search(r"17p\s*delesyon|17p\s*del", lower):
        markers.append({"marker": "TP17_DELETION", "status_any": ["present", "var"]})

    # BRCA
    if re.search(r"brca\s*[12]?\s*mutasyon|brca\s*[12]?\s*pozitif", lower):
        markers.append({"marker": "BRCA", "status_any": ["mutation", "mutasyon"]})

    # Genotype (Hep-C)
    if re.search(r"genotip\s*[123]", lower):
        markers.append({"marker": "HCV_GENOTYPE", "status_any": ["1", "2", "3"]})

    return markers


def _extract_prior_therapy(text: str) -> dict | None:
    """Extract prior-therapy requirement as {drug_or_class, outcome}."""
    lower = text.lower()

    # Imatinib-resistant (nilotinib/dasatinib)
    if re.search(r"imatinib.{0,30}direnç|imatinib.{0,30}intolere|önceki.{0,20}imatinib", lower):
        return {"drug_or_class": "imatinib", "outcome": "resistant_or_intolerant"}

    # Prior anti-angiogenic / TKI
    if re.search(r"sunitinib.{0,20}direnç|sunitinib.{0,20}kullan|sorafenib.{0,20}direnç", lower):
        return {"drug_or_class": "sunitinib_or_sorafenib", "outcome": "resistant"}

    # Post-transplant maintenance
    if re.search(r"transplantasyon\s+sonrasında|otolog\s+kök\s*hücre", lower):
        return {"drug_or_class": "stem_cell_transplant", "outcome": "completed"}

    # Prior endocrine therapy (fulvestrant/CDK4/6)
    if re.search(r"endokrin\s*tedavi.{0,20}sonras|aromataz.{0,10}sonras|tamoksifen.{0,10}sonras", lower):
        return {"drug_or_class": "endocrine_therapy", "outcome": "failed"}

    # Prior rituximab
    if re.search(r"rituximab.{0,20}kullan|rituksimab.{0,20}önceki", lower):
        return {"drug_or_class": "rituximab", "outcome": "prior"}

    # Prior bortezomib
    if re.search(r"bortezomib.{0,20}kullan|bortezomib.{0,20}önceki", lower):
        return {"drug_or_class": "bortezomib", "outcome": "prior_or_failed"}

    # Generic prior therapy
    if re.search(r"önceki\s+tedavi|dirençli|intolere", lower):
        return {"drug_or_class": "prior_therapy", "outcome": "resistant"}

    return None


def compile_bucket_b_rules() -> list[dict]:
    df = pl.read_csv(_CLASSIFICATION_CSV)
    clauses = pl.read_parquet(_CLAUSES_PARQUET)

    b_ids = df.filter(pl.col("bucket") == "B")["clause_id"].to_list()
    b_clauses = clauses.filter(pl.col("clause_id").is_in(b_ids)).sort("paragraph_index")

    with _RULES_JSON.open(encoding="utf-8") as f:
        existing = json.load(f)
    existing_ids = {r["rule_id"] for r in existing.get("rules", [])}
    existing_sources = set()
    for r in existing.get("rules", []):
        existing_sources.update(r.get("gate_b_sources") or [])

    new_rules: list[dict] = []
    seen: set[str] = set()

    for record in b_clauses.iter_rows(named=True):
        clause_id = record.get("clause_id", "")
        text = str(record.get("text_tr") or "")
        if clause_id in existing_sources or clause_id in seen:
            continue

        drugs = _extract_drugs(text)
        if not drugs:
            continue

        biomarkers = _extract_biomarkers(text)
        prior = _extract_prior_therapy(text)
        if not biomarkers and not prior:
            continue  # Bucket B sinyali var ama yapısal çıkarılamadı

        drug_key = drugs[0].replace(" ", "_").replace("/", "_")
        rule_id = f"4.2.14.C.tier_c_b.{clause_id}.{drug_key}"
        if rule_id in existing_ids:
            continue

        rule: dict = {
            "rule_id": rule_id,
            "sut_section": "4.2.14.C",
            "drug_names": drugs,
            "report_required": True,
            "report_specialties": ["tıbbi onkoloji"],
            "prescriber_specialties": ["tıbbi onkoloji"],
            "icd10_ranges": ["C00-C97"],
            "gate_b_sources": [clause_id],
            "message_tr": text[:200].replace("\n", " ").strip(),
        }
        if biomarkers:
            rule["required_biomarkers"] = biomarkers
        if prior:
            rule["requires_prior_therapy"] = prior

        new_rules.append(rule)
        seen.add(clause_id)

    return new_rules


def main() -> None:
    new_rules = compile_bucket_b_rules()
    print(f"Compiled {len(new_rules)} new Bucket B rules")
    bio_count = sum(1 for r in new_rules if r.get("required_biomarkers"))
    prior_count = sum(1 for r in new_rules if r.get("requires_prior_therapy"))
    print(f"  with biomarkers: {bio_count}")
    print(f"  with prior-therapy: {prior_count}")

    with _RULES_JSON.open(encoding="utf-8") as f:
        payload = json.load(f)
    existing = len(payload.get("rules", []))
    payload["rules"].extend(new_rules)
    payload["coverage_note"] = (
        f"§4.2.14.C oncology ({len(payload['rules'])} rules: Tier-A/B base + Bucket A "
        f"prescriber + Bucket B biomarker/prior-therapy) + §4.2.33 anti-VEGF (21 rules)."
    )
    with _RULES_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Updated {_RULES_JSON}: {existing} → {len(payload['rules'])} rules")


if __name__ == "__main__":
    main()
