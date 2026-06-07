"""Unit tests for MEDULA knowledge-base search."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_search_known_codes_finds_documented_code():
    from src.bilun.chatbot.medula_kb import search_known_codes

    results = search_known_codes("MEDULA returned sonucKodu 9000 for this claim")
    assert len(results) == 1
    assert results[0]["code"] == "9000"
    assert results[0]["is_error"] is False


def test_search_known_codes_marks_real_errors():
    from src.bilun.chatbot.medula_kb import search_known_codes

    results = search_known_codes("We got error 1688 on molecular microbiology")
    assert len(results) == 1
    assert results[0]["code"] == "1688"
    assert results[0]["is_error"] is True


def test_search_workflow_stage_detects_invoice_stage():
    from src.bilun.chatbot.medula_kb import search_workflow_stage

    stage = search_workflow_stage("Fatura kayıt sırasında 105 gün sınırına takıldık")
    assert stage is not None
    assert stage["stage"] == "fatura_kayit"
    assert "Fatura Kayıt" in stage["name_tr"]


def test_search_rejection_categories_matches_entitlement_keywords():
    from src.bilun.chatbot.medula_kb import search_rejection_categories

    matches = search_rejection_categories("Hasta müstehaklık sorgusu başarısız oldu")
    assert matches
    assert matches[0]["category"] == "Müstehaklık / Entitlement"


def test_search_medula_composes_all_result_keys():
    from src.bilun.chatbot.medula_kb import search_medula

    payload = search_medula("9000 provizyon uyarısı müstehaklık")
    assert "known_codes" in payload
    assert "rejection_categories" in payload
    assert "workflow_stage" in payload
    assert "playbook_entries" in payload
    assert payload["known_codes"]
    assert payload["rejection_categories"]


def test_search_playbook_entries_matches_molecular_microbiology():
    from src.bilun.chatbot.medula_kb import search_playbook_entries

    matches = search_playbook_entries("1688 moleküler mikrobiyoloji rapor eksik")
    assert matches
    assert matches[0]["playbook_key"] == "1688_molecular_microbiology"
