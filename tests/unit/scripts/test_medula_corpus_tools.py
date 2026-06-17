"""Tests for MEDULA known-code sync and export draft tooling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_PLAYBOOK_PATH = _REPO / "data/medula/rejection_playbook.json"
_KNOWN_CODES_PATH = _REPO / "data/medula/known_codes.json"


def test_known_codes_cover_all_playbook_sonuc_kodlari() -> None:
    playbook = json.loads(_PLAYBOOK_PATH.read_text(encoding="utf-8"))
    known = json.loads(_KNOWN_CODES_PATH.read_text(encoding="utf-8"))
    playbook_codes = {
        str(entry["sonuc_kodu"])
        for entry in playbook.get("entries", [])
        if entry.get("sonuc_kodu")
    }
    missing = sorted(code for code in playbook_codes if code not in known)
    assert not missing, f"known_codes.json missing playbook codes: {missing}"


def test_search_known_codes_finds_sprint3_codes() -> None:
    from src.bilun.chatbot.medula_kb import search_known_codes

    for code in ("0901", "0704", "1102"):
        results = search_known_codes(f"MEDULA error {code}")
        assert results
        assert results[0]["code"] == code
        assert results[0]["is_error"] is True


def test_draft_playbook_from_export() -> None:
    from scripts.medula.draft_playbook_from_export import draft_playbook_from_rows

    rows = [
        {
            "sonuc_kodu": "0901",
            "hata_mesaji": "Mükerrer işlem aynı gün tekrar faturalandırılamaz",
            "medula_asamasi": "fatura_kayit",
        },
        {
            "sonuc_kodu": "0901",
            "hata_mesaji": "Mükerrer işlem kaydı tespit edildi",
            "medula_asamasi": "fatura_kayit",
        },
    ]
    payload = draft_playbook_from_rows(rows)
    assert len(payload["entries"]) == 1
    entry = payload["entries"][0]
    assert entry["sonuc_kodu"] == "0901"
    assert "mükerrer" in " ".join(entry["hata_mesaji_keywords"]).casefold()
    assert entry["sample_count"] == 2
