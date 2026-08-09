"""Unit tests for SUT prose clause extraction."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import pytest

from scripts.sut.prose.extractor import (
    _build_clause_coordinate,
    _extract_annex_refs,
    _extract_clause_coordinate,
    _extract_percentages,
    _extract_procedure_codes,
    _extract_sut_section_refs,
    _find_body_start,
    _parse_section_heading,
    _read_docx_paragraphs,
    _run_is_struck,
    extract_sut_clauses,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RAW_DATA_DIR = _REPO_ROOT / "raw data"
_CONSOLIDATED_FOLDER_RE = re.compile(
    r"^\d{4}\.\d{2}\.\d{2}-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT$"
)


def _find_consolidated_sut_docx(raw_data_dir: Path = _RAW_DATA_DIR) -> Path | None:
    """Auto-discover the active consolidated SUT docx.

    Only one consolidated ("İşlenmiş Güncel 2013 SUT") folder is kept at a time;
    each new tebliğ supersedes the prior one (it contains all past amendments).
    The folder name follows ``YYYY.MM.DD-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT``.
    Delta/incremental folders (no "İşlenmiş") are excluded.
    """
    for entry in sorted(raw_data_dir.iterdir()):
        if not entry.is_dir():
            continue
        if not _CONSOLIDATED_FOLDER_RE.match(entry.name):
            continue
        docx_files = sorted(entry.rglob("*.docx"))
        if docx_files:
            return docx_files[0]
    return None


_ACTIVE_DOCX = _find_consolidated_sut_docx()


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

    def test_extract_clause_coordinate_fikra(self) -> None:
        assert _extract_clause_coordinate("(3) Bu hüküm uygulanır.") == (3, None)

    def test_extract_clause_coordinate_bent(self) -> None:
        assert _extract_clause_coordinate("a) Birinci bent metni") == (None, "a")

    def test_extract_clause_coordinate_uppercase_bent_lowered(self) -> None:
        # _BENT_RE uses IGNORECASE; the letter is normalized to lowercase.
        assert _extract_clause_coordinate("A) Birinci bent metni") == (None, "a")

    def test_extract_clause_coordinate_none_for_prose_and_headings(self) -> None:
        assert _extract_clause_coordinate("Genel Hükümler") == (None, None)
        # Numbered items ("1) ...") are now real clauses and DO carry a number.
        assert _extract_clause_coordinate("1) Numaralı liste maddesi") == (1, None)
        assert _extract_clause_coordinate("(Değişik: 12.04.2026) metin") == (None, None)

    def test_build_clause_coordinate_combines_section_number_letter(self) -> None:
        assert _build_clause_coordinate("3.3.3.A", 1, "a") == "3.3.3.A.(1).a"
        assert _build_clause_coordinate("3.3.3.A", 1, None) == "3.3.3.A.(1)"
        assert _build_clause_coordinate("3.3.3.A", None, "b") == "3.3.3.A.b"

    def test_build_clause_coordinate_null_when_empty(self) -> None:
        assert _build_clause_coordinate(None, None, None) is None
        assert _build_clause_coordinate(None, 1, None) == "(1)"


@pytest.mark.skipif(not _ACTIVE_DOCX, reason="consolidated SUT docx not present")
class TestDocxExtraction:
    @pytest.fixture(scope="class")
    def clauses(self) -> pd.DataFrame:
        assert _ACTIVE_DOCX is not None
        return extract_sut_clauses(_ACTIVE_DOCX)

    def test_non_empty(self, clauses: pd.DataFrame) -> None:
        assert len(clauses) > 5000

    def test_expected_columns(self, clauses: pd.DataFrame) -> None:
        required = {
            "clause_id",
            "section_id",
            "text_tr",
            "in_force_text",
            "is_in_force",
            "had_struck_content",
            "annex_refs",
            "deontic_modality",
            "clause_type",
            "source_effective_date",
        }
        assert required.issubset(clauses.columns)

    def test_clause_coordinate_columns_present(self, clauses: pd.DataFrame) -> None:
        assert {"clause_number", "clause_letter", "clause_coordinate"}.issubset(
            clauses.columns
        )

    def test_fikra_rows_carry_clause_number(self, clauses: pd.DataFrame) -> None:
        fikra = clauses[clauses["clause_type"] == "fikra"]
        assert not fikra.empty
        # Every fikra must have a parsed integer clause_number.
        assert fikra["clause_number"].notna().all()
        assert fikra["clause_number"].dtype.kind in {"i", "u"}
        # Fıkra never carries a bent letter.
        assert fikra["clause_letter"].isna().all()
        # The coordinate string contains the parsed number in parentheses.
        first = fikra.iloc[0]
        assert f"({int(first['clause_number'])})" in first["clause_coordinate"]

    def test_bent_rows_carry_clause_letter(self, clauses: pd.DataFrame) -> None:
        bent = clauses[clauses["clause_type"] == "bent"]
        assert not bent.empty
        assert bent["clause_letter"].notna().all()
        # Bent carries a single lowercase Turkish letter, no number.
        assert bent["clause_number"].isna().all()
        sample = bent["clause_letter"].dropna().astype(str)
        assert sample.str.len().eq(1).all()
        assert sample.str.fullmatch(r"[a-zçğıöşü]").all()

    def test_headings_and_prose_have_null_coordinate_parts(
        self, clauses: pd.DataFrame
    ) -> None:
        for ct in ("section_heading", "chapter", "amendment"):
            rows = clauses[clauses["clause_type"] == ct]
            if rows.empty:
                continue
            assert rows["clause_number"].isna().all(), f"{ct} should have null number"
            assert rows["clause_letter"].isna().all(), f"{ct} should have null letter"

    def test_in_force_subset_of_rows(self, clauses: pd.DataFrame) -> None:
        assert clauses["is_in_force"].sum() < len(clauses)
        assert clauses["is_in_force"].sum() > 3000

    def test_effective_date_matches_folder(self, clauses: pd.DataFrame) -> None:
        """source_effective_date must match the date in the folder name (date-neutral)."""
        assert _ACTIVE_DOCX is not None
        folder_date = _ACTIVE_DOCX.parent.name[:10]  # YYYY.MM.DD
        expected = folder_date.replace(".", "-")
        assert clauses["source_effective_date"].iloc[0] == expected

    def test_section_1_8_present(self, clauses: pd.DataFrame) -> None:
        section = clauses[clauses["section_id"] == "1.8"]
        assert not section.empty
        assert (section["section_title"] == "Katılım payı").any()

    def test_copay_percentage_clause(self, clauses: pd.DataFrame) -> None:
        hits = clauses[clauses["text_tr"].str.contains("%10", na=False)]
        assert not hits.empty
        assert (hits["percentages"] != "[]").any()

    def test_body_start_skips_toc(self) -> None:
        assert _ACTIVE_DOCX is not None
        paragraphs = _read_docx_paragraphs(_ACTIVE_DOCX)
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

    def test_reextract_stability(self, clauses: pd.DataFrame) -> None:
        """Track E Phase 6: double-extraction must produce identical clause_keys."""
        from scripts.sut.prose.extractor import add_identity_columns
        
        assert _ACTIVE_DOCX is not None
        # clauses is the first extraction (via fixture). Add identity columns.
        clauses_1 = add_identity_columns(clauses)
        
        # Extract a second time and add identity columns
        clauses_2 = add_identity_columns(extract_sut_clauses(_ACTIVE_DOCX))
        
        # Keys should be identical and in the same order
        keys_1 = clauses_1["clause_key"].to_list()
        keys_2 = clauses_2["clause_key"].to_list()
        assert keys_1 == keys_2



@pytest.mark.skipif(not _ACTIVE_DOCX, reason="consolidated SUT docx not present")
class TestInForceExtraction:
    @pytest.fixture(scope="class")
    def clauses(self) -> pd.DataFrame:
        assert _ACTIVE_DOCX is not None
        return extract_sut_clauses(_ACTIVE_DOCX)

    def test_titubb_fikra_in_force_flags(self, clauses: pd.DataFrame) -> None:
        c618 = clauses.loc[clauses["clause_id"] == "C001618"].iloc[0]
        c619 = clauses.loc[clauses["clause_id"] == "C001619"].iloc[0]
        c684 = clauses.loc[clauses["clause_id"] == "C002684"].iloc[0]
        assert not bool(c618["is_in_force"])
        assert c618["in_force_text"] == ""
        assert bool(c618["had_struck_content"])
        assert not bool(c619["is_in_force"])
        assert bool(c684["is_in_force"])
        assert "TİTUBB" in str(c684["in_force_text"])
        assert str(c684["in_force_text"]).startswith("(2)")

    def test_mixed_strike_strips_dead_runs(self, clauses: pd.DataFrame) -> None:
        mixed = clauses[
            clauses["had_struck_content"] & clauses["is_in_force"]
        ]
        assert not mixed.empty
        for _, row in mixed.head(5).iterrows():
            assert len(str(row["in_force_text"])) < len(str(row["text_tr"]))

    def test_clean_paragraph_in_force_equals_text_tr(self, clauses: pd.DataFrame) -> None:
        """A paragraph with no struck runs must have in_force_text == text_tr."""
        clean = clauses[~clauses["had_struck_content"] & clauses["is_in_force"]]
        assert not clean.empty
        for _, row in clean.head(20).iterrows():
            assert str(row["in_force_text"]) == str(row["text_tr"])

    def test_mixed_strike_in_force_excludes_struck_fragments(self, clauses: pd.DataFrame) -> None:
        """Mixed paragraphs: in_force_text is shorter than text_tr and non-empty."""
        mixed = clauses[
            clauses["had_struck_content"] & clauses["is_in_force"]
        ]
        assert not mixed.empty
        for _, row in mixed.head(5).iterrows():
            in_force = str(row["in_force_text"]).strip()
            legacy = str(row["text_tr"]).strip()
            assert in_force  # non-empty (it's in force)
            assert len(in_force) < len(legacy)  # struck fragments stripped

    def test_fully_struck_paragraph_is_not_in_force(self, clauses: pd.DataFrame) -> None:
        """A paragraph that had struck content but no surviving live text must be
        is_in_force=false with an empty in_force_text (covers fully-struck Mülga
        paragraphs and any other fully-superseded paragraph)."""
        struck_only = clauses[
            clauses["had_struck_content"] & ~clauses["is_in_force"]
        ]
        assert not struck_only.empty, "expected fully-struck out-of-force paragraphs"
        assert (struck_only["in_force_text"] == "").all()
        assert not bool(struck_only["is_in_force"].any())


class TestRunIsStruck:
    """Spec-completeness tests for _run_is_struck (no docx required)."""

    _W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    def _make_run(self, strike_val: str | None, present: bool = True) -> ET.Element:
        run = ET.Element(f"{self._W}r")
        rpr = ET.SubElement(run, f"{self._W}rPr")
        if present:
            strike = ET.SubElement(rpr, f"{self._W}strike")
            if strike_val is not None:
                strike.set(f"{self._W}val", strike_val)
        return run

    def test_bare_strike_is_struck(self) -> None:
        assert _run_is_struck(self._make_run(strike_val=None)) is True

    def test_strike_val_true_is_struck(self) -> None:
        assert _run_is_struck(self._make_run(strike_val="true")) is True
        assert _run_is_struck(self._make_run(strike_val="1")) is True
        assert _run_is_struck(self._make_run(strike_val="on")) is True

    def test_strike_val_false_is_not_struck(self) -> None:
        assert _run_is_struck(self._make_run(strike_val="false")) is False
        assert _run_is_struck(self._make_run(strike_val="0")) is False
        assert _run_is_struck(self._make_run(strike_val="off")) is False

    def test_no_strike_element_is_not_struck(self) -> None:
        assert _run_is_struck(self._make_run(strike_val=None, present=False)) is False
