#!/usr/bin/env python3
"""Draft MEDULA playbook rows from a hospital rejection export CSV.

Expected columns (case-insensitive):
  sonuc_kodu | hata_mesaji | medula_asamasi (optional)

Usage:
  PYTHONPATH=. python scripts/medula/draft_playbook_from_export.py export.csv -o draft.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


def _normalize_header(value: str) -> str:
    return re.sub(r"[\s_\-]+", "", value.casefold())


def _pick(row: dict[str, str], *candidates: str) -> str:
    normalized = {_normalize_header(key): value for key, value in row.items()}
    for candidate in candidates:
        hit = normalized.get(_normalize_header(candidate))
        if hit is not None and str(hit).strip():
            return str(hit).strip()
    return ""


def _keyword_tokens(message: str, *, limit: int = 6) -> list[str]:
    tokens = re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]+", message.casefold())
    seen: set[str] = set()
    keywords: list[str] = []
    for token in tokens:
        if len(token) < 3 or token in seen:
            continue
        seen.add(token)
        keywords.append(token)
        if len(keywords) >= limit:
            break
    return keywords


def draft_playbook_from_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        code = _pick(row, "sonuc_kodu", "sonuckodu", "result_code", "code")
        message = _pick(row, "hata_mesaji", "hatamesaji", "message", "error_message")
        stage = _pick(row, "medula_asamasi", "medulaasamasi", "stage", "medula_stage")
        if not code:
            continue
        grouped[code].append({"message": message, "stage": stage})

    entries: list[dict[str, Any]] = []
    for code in sorted(grouped):
        samples = grouped[code]
        messages = [sample["message"] for sample in samples if sample["message"]]
        stages = sorted({sample["stage"] for sample in samples if sample["stage"]})
        sample_message = messages[0] if messages else f"MEDULA sonuc kodu {code}"
        keywords: list[str] = []
        for message in messages[:5]:
            for token in _keyword_tokens(message):
                if token not in keywords:
                    keywords.append(token)
        if not keywords:
            keywords = [code]
        entries.append(
            {
                "playbook_key": f"{code}_draft",
                "sonuc_kodu": code,
                "medula_stages": stages or ["fatura_kayit"],
                "hata_mesaji_keywords": keywords[:8],
                "sut_anchor": "Hospital export draft — review before merge",
                "problem_summary_tr": sample_message,
                "problem_summary_en": sample_message,
                "corrective_steps_tr": [
                    "Gerçek hastane mesajına göre düzeltici adımları güncelleyin.",
                    "Anahtar kelime listesini doğrulayın.",
                ],
                "corrective_steps_en": [
                    "Update corrective steps from the real hospital message.",
                    "Validate keyword list against production samples.",
                ],
                "rebill_permitted": True,
                "rebill_stage": stages[0] if stages else "fatura_kayit",
                "draft_source": "hospital_export",
                "sample_count": len(samples),
            }
        )

    return {
        "version": 0,
        "description": "Draft MEDULA playbook rows generated from hospital export",
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    with args.csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    payload = draft_playbook_from_rows(rows)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Drafted {len(payload['entries'])} playbook entries → {args.output}")


if __name__ == "__main__":
    main()
