"""Unit tests for SUT prose clause extraction."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.sut.prose.extractor import (
    _extract_annex_refs,
    _extract_percentages,
    _extract_procedure_codes,
    _extract_sut_section_refs,
    _find_body_start,
    _parse_section_heading,
    _read_docx_paragraphs,
    extract_sut_clauses,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DOCX = (
    _REPO_ROOT
    / "raw data"
    / "2026.01.17-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT"
    / "17.01.2026-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT.docx"
)


class TestParsingHelpers:
    def test_parse_section_heading_simple(self) -> None:
        assert _parse_section_heading("1.8 - Katılım payı") == ("1.8", "Katılım payı")

    def test_parse_section_heading_letter_subnum(self) -> None:
        parsed = _parse_section_heading("1.5.1.A-1 - Hasta kabul işlemleri")
        assert parsed == ("1.5.1.A-1", "Hasta kabul işlemleri")

    def test_parse_section_heading_rejects_long_prose(self) -> None:
        prose = "(1) " + "x" * 50
        assert _parse_section_heading(prose) is None

    def test_parse_section_heading_rejects_numbered_fikra(self) -> None:
        assert _parse_section_heading("1) Bünyesinde birinci basamak sağlık hizmeti sunan kurum.") is None
        assert _parse_section_heading("(1) Katılım payı alınır.") is None

    def test_extract_annex_refs(self) -> None:
        text = 'SUT eki "EK-2/C Listesinde" ve EK-1/A listesinde'
        refs = _extract_annex_refs(text)
        assert "EK-2/C" in refs
        assert "EK-1/A" in refs

    def test_extract_percentages(self) -> None:
        assert _extract_percentages("%10 ve %20 oranında") == [10.0, 20.0]
        assert _extract_percentages("puanının %30'u") == [30.0]

    def test_extract_procedure_codes(self) -> None:
        text = '520.021 kodlu "Yeşil alan muayenesi" ve 705371 kodlu kan'
        codes = _extract_procedure_codes(text)
        assert "520021" in codes
        assert "705371" in codes

    def test_extract_sut_section_refs(self) -> None:
        text = "SUT'un 2.2(5) fıkrasında belirtilen istisnalar"
        refs = _extract_sut_section_refs(text)
        assert "2.2(5)" in refs


@pytest.mark.skipif(not _DEFAULT_DOCX.exists(), reason="SUT docx not present")
class TestDocxExtraction:
    @pytest.fixture(scope="class")
    def clauses(self) -> pd.DataFrame:
        return extract_sut_clauses(_DEFAULT_DOCX)

    def test_non_empty(self, clauses: pd.DataFrame) -> None:
        assert len(clauses) > 5000

    def test_expected_columns(self, clauses: pd.DataFrame) -> None:
        required = {
            "clause_id",
            "section_id",
            "text_tr",
            "annex_refs",
            "deontic_modality",
            "clause_type",
            "source_effective_date",
        }
        assert required.issubset(clauses.columns)

    def test_effective_date(self, clauses: pd.DataFrame) -> None:
        assert clauses["source_effective_date"].iloc[0] == "2026-01-17"

    def test_section_1_8_present(self, clauses: pd.DataFrame) -> None:
        section = clauses[clauses["section_id"] == "1.8"]
        assert not section.empty
        assert (section["section_title"] == "Katılım payı").any()

    def test_copay_percentage_clause(self, clauses: pd.DataFrame) -> None:
        hits = clauses[clauses["text_tr"].str.contains("%10", na=False)]
        assert not hits.empty
        assert (hits["percentages"] != "[]").any()

    def test_body_start_skips_toc(self) -> None:
        paragraphs = _read_docx_paragraphs(_DEFAULT_DOCX)
        start = _find_body_start(paragraphs)
        assert paragraphs[start] == "BİRİNCİ BÖLÜM"

    def test_chapters_extracted(self, clauses: pd.DataFrame) -> None:
        assert (clauses["chapter"] == "BIRINCI_BOLUM").any()
        assert (clauses["clause_type"] == "chapter").sum() >= 6

    def test_deontic_hits(self, clauses: pd.DataFrame) -> None:
        assert (clauses["deontic_markers"] != "[]").sum() > 100

    def test_no_bare_digit_section_path(self, clauses: pd.DataFrame) -> None:
        assert (clauses["section_path"] == "1").sum() == 0
        assert (clauses["section_id"] == "1").sum() == 0

    def test_annex_refs_in_payment_section(self, clauses: pd.DataFrame) -> None:
        section = clauses[clauses["section_path"].str.contains("2.2", na=False)]
        assert (section["annex_refs"].str.contains("EK-2/C", na=False)).any()
