"""
Extract structured clauses from the consolidated SUT main document (docx).

Phase 1 output schema (sut_clauses.parquet):
  clause_id              — stable sequential id (C000001)
  paragraph_index        — 0-based index in extracted body paragraphs
  section_id             — e.g. 1.8.2, 2.2.2.B.a
  section_title          — heading title when present
  parent_section_id      — immediate parent section
  section_path           — full hierarchy joined by /
  chapter                — BIRINCI BOLUM, IKINCI BOLUM, ...
  clause_type            — chapter | section_heading | fikra | bent | amendment | prose
  text_tr                — original paragraph text
  is_heading             — bool
  is_amendment           — bool (Degisik/Mulga/Ek marker)
  is_superseded_marker   — bool (Mulga or inline replacement chain)
  annex_refs             — JSON list, e.g. ["EK-2/C", "EK-1/A"]
  procedure_codes        — JSON list of P/L/R codes
  percentages            — JSON list of floats
  deontic_markers        — JSON list of matched Turkish legal verbs
  deontic_modality       — coarse classification when detectable
  sut_section_refs       — JSON list of cross-refs like 1.8.5, 2.2(5)
  amendment_refs         — JSON list of Resmi Gazete citations
  source_docx            — absolute path to source file
  source_effective_date  — YYYY-MM-DD parsed from folder name when possible
  char_count             — int
  word_count             — int
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd

_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

_CHAPTER_RE = re.compile(
    r"^(BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI)\s+BÖLÜM\s*$"
)
_CHAPTER_LABELS = {
    "BİRİNCİ": "BIRINCI_BOLUM",
    "İKİNCİ": "IKINCI_BOLUM",
    "ÜÇÜNCÜ": "UCUNCU_BOLUM",
    "DÖRDÜNCÜ": "DORDUNCU_BOLUM",
    "BEŞİNCİ": "BESINCI_BOLUM",
    "ALTINCI": "ALTINCI_BOLUM",
}

# 1.8 - Katılım payı | 1.5.1.A-1 - Title | 2.2.2.B.a - Title
_SECTION_HEADING_RE = re.compile(
    r"^(\d+(?:\.\d+)*)"
    r"(?:\.([A-ZÇĞİÖŞÜ])(?:-(\d+))?)?"
    r"(?:\.([a-zçğıöşü]))?"
    r"\s*(?:[-–]\s*)?"
    r"(.*)$"
)

_FIKRA_RE = re.compile(r"^\((\d+)\)")
_NUMBERED_ITEM_RE = re.compile(r"^\d+\)\s")
_BENT_RE = re.compile(r"^([a-zçğıöşü])\)\s*", re.IGNORECASE)
_AMENDMENT_RE = re.compile(r"^\((Değişik|Mülga|Ek|Değişiklik|Mülga:)", re.IGNORECASE)

_ANNEX_RE = re.compile(
    r"EK[-\s]?(\d+[A-ZÇĞİÖŞÜ]?)(?:[-\s/]?([A-ZÇĞİÖŞÜ0-9-]+))?",
    re.IGNORECASE,
)
_PROCEDURE_CODE_RE = re.compile(r"\b(P?\d[\d.]{5,9}|L\d{6,7}|R\d{6,7})\b")
_PERCENT_RE = re.compile(r"%\s*(\d+(?:[.,]\d+)?)")
_SUT_REF_RE = re.compile(
    r"SUT(?:['’]un|un)?\s+(\d+(?:\.\d+)*)(?:\((\d+)\))?\s*(?:fıkr)?",
    re.IGNORECASE,
)
_SECTION_INLINE_REF_RE = re.compile(
    r"(?<!\d)(\d+\.\d+(?:\.\d+)*)(?:\((\d+)\))?\s*(?:fıkr|madde)",
    re.IGNORECASE,
)
_RG_AMENDMENT_RE = re.compile(
    r"RG[-\s]?(\d{2}/\d{2}/\d{4})[-\s]?(\d+)",
    re.IGNORECASE,
)

_DEONTIC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("MUST_NOT_BILL", re.compile(r"faturalandırılamaz|faturalandırılmayacaktır|faturalandırılmayacak|ayrıca faturalandırılmayacaktır", re.I)),
    ("MUST_BILL", re.compile(r"faturalandırılır|faturalandırılabilir|ayrıca faturalandırılabilir", re.I)),
    ("NO_PAY", re.compile(r"ödenmez|karşılanmaz|bedelleri Kurumca karşılanmaz", re.I)),
    ("NO_COPAY", re.compile(r"katılım payı alınmaz|katılım payından muaf", re.I)),
    ("COPAY_REQUIRED", re.compile(r"katılım payı alınır", re.I)),
    ("PROHIBITED", re.compile(r"yapılamaz|yasaktır", re.I)),
    ("MANDATORY", re.compile(r"zorundadır|uyulacaktır", re.I)),
]

_DEONTIC_MARKER_RE = re.compile(
    r"(faturalandırıl(?:ır|amaz|mayacaktır|mayacak|abilir)|"
    r"öden(?:mez|ir)|karşılanmaz|"
    r"alın(?:maz|ır)|"
    r"yapılamaz|yasaktır|"
    r"zorundadır|uyulacaktır|"
    r"hariç)",
    re.IGNORECASE,
)


def _json_list(values: list[Any]) -> str:
    return json.dumps(values, ensure_ascii=False)


def _normalize_annex(raw: str) -> str | None:
    m = _ANNEX_RE.search(raw)
    if not m:
        return None
    base = m.group(1).upper().replace(" ", "")
    suffix = (m.group(2) or "").upper().replace(" ", "")
    if suffix:
        return f"EK-{base}/{suffix}"
    return f"EK-{base}"


def _extract_annex_refs(text: str) -> list[str]:
    seen: set[str] = set()
    refs: list[str] = []
    for m in _ANNEX_RE.finditer(text):
        raw = m.group(0)
        norm = _normalize_annex(raw)
        if norm and norm not in seen:
            seen.add(norm)
            refs.append(norm)
    return refs


def _extract_percentages(text: str) -> list[float]:
    values: list[float] = []
    for m in _PERCENT_RE.finditer(text):
        raw = m.group(1).replace(",", ".")
        try:
            values.append(float(raw))
        except ValueError:
            continue
    return values


def _normalize_procedure_code(code: str) -> str:
    normalized = code.replace(".", "").strip()
    if normalized.startswith("P") and len(normalized) > 1:
        return normalized[1:]
    return normalized


def _extract_procedure_codes(text: str) -> list[str]:
    seen: set[str] = set()
    codes: list[str] = []
    for m in _PROCEDURE_CODE_RE.finditer(text):
        code = _normalize_procedure_code(m.group(1))
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def _extract_sut_section_refs(text: str) -> list[str]:
    seen: set[str] = set()
    refs: list[str] = []

    def _add(section: str, fikra: str | None) -> None:
        ref = f"{section}({fikra})" if fikra else section
        if ref not in seen:
            seen.add(ref)
            refs.append(ref)

    for m in _SUT_REF_RE.finditer(text):
        _add(m.group(1), m.group(2))
    for m in _SECTION_INLINE_REF_RE.finditer(text):
        _add(m.group(1), m.group(2))
    return refs


def _extract_amendment_refs(text: str) -> list[str]:
    return [f"RG-{m.group(1)}/{m.group(2)}" for m in _RG_AMENDMENT_RE.finditer(text)]


def _extract_deontic_markers(text: str) -> list[str]:
    seen: set[str] = set()
    markers: list[str] = []
    for m in _DEONTIC_MARKER_RE.finditer(text):
        token = m.group(1).lower()
        if token not in seen:
            seen.add(token)
            markers.append(m.group(1))
    return markers


def _classify_deontic_modality(text: str, markers: list[str]) -> str | None:
    if not markers:
        return None
    for modality, pattern in _DEONTIC_PATTERNS:
        if pattern.search(text):
            return modality
    return "REGULATORY_ACTION"


def _parse_section_heading(text: str) -> tuple[str, str] | None:
    m = _SECTION_HEADING_RE.match(text)
    if not m:
        return None

    numeric = m.group(1)
    letter = m.group(2)
    subnum = m.group(3)
    bent = m.group(4)
    title = (m.group(5) or "").strip()

    parts = [numeric]
    if letter:
        token = letter
        if subnum:
            token = f"{letter}-{subnum}"
        parts.append(token)
    if bent:
        parts.append(bent)

    section_id = ".".join(parts)

    if _FIKRA_RE.match(text) or _NUMBERED_ITEM_RE.match(text):
        return None
    if re.fullmatch(r"\d+", section_id):
        return None

    # Require plausible heading: has title or is short standalone id line
    if not title and len(text) > 40:
        return None
    if title and re.search(r"\d{1,3}$", title) and len(title) < 4:
        # TOC artifact like "Amaç6"
        title = re.sub(r"\d{1,3}$", "", title).strip()

    return section_id, title


def _parent_section_id(section_id: str) -> str | None:
    if not section_id:
        return None
    if re.match(r"^\d+$", section_id):
        return None
    parts = section_id.split(".")
    if len(parts) <= 1:
        return None
    return ".".join(parts[:-1])


def _read_docx_paragraphs(docx_path: Path) -> list[str]:
    with zipfile.ZipFile(docx_path) as archive:
        document_xml = archive.read("word/document.xml")
    root = ET.fromstring(document_xml)

    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_WORD_NS}p"):
        texts = [node.text or "" for node in paragraph.iter(f"{_WORD_NS}t")]
        paragraphs.append("".join(texts).strip())
    return paragraphs


def _find_body_start(paragraphs: list[str]) -> int:
    """Skip TOC; body begins at the second bare 'BİRİNCİ BÖLÜM' line."""
    hits = [
        idx
        for idx, text in enumerate(paragraphs)
        if text == "BİRİNCİ BÖLÜM"
    ]
    if len(hits) >= 2:
        return hits[1]
    if hits:
        return hits[0]
    return 0


def _infer_effective_date(docx_path: Path) -> str | None:
    for part in docx_path.parts:
        m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", part)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _classify_clause_type(
    text: str,
    is_chapter: bool,
    section_heading: tuple[str, str] | None,
    is_amendment: bool,
) -> str:
    if is_chapter:
        return "chapter"
    if section_heading is not None:
        return "section_heading"
    if is_amendment:
        return "amendment"
    if _FIKRA_RE.match(text):
        return "fikra"
    if _BENT_RE.match(text):
        return "bent"
    return "prose"


@dataclass
class SutClauseExtractor:
    docx_path: Path
    body_start: int | None = None

    _chapter: str | None = field(default=None, init=False)
    _section_stack: list[str] = field(default_factory=list, init=False)

    def extract(self) -> pd.DataFrame:
        paragraphs = _read_docx_paragraphs(self.docx_path)
        start = self.body_start if self.body_start is not None else _find_body_start(paragraphs)
        body = paragraphs[start:]

        effective_date = _infer_effective_date(self.docx_path)
        rows: list[dict[str, Any]] = []

        for offset, text in enumerate(body):
            if not text:
                continue

            paragraph_index = start + offset
            chapter_match = _CHAPTER_RE.match(text)
            section_heading = _parse_section_heading(text)
            is_amendment = bool(_AMENDMENT_RE.match(text))
            is_chapter = chapter_match is not None

            if is_chapter:
                self._chapter = _CHAPTER_LABELS[chapter_match.group(1)]
                self._section_stack = []

            section_id: str | None = None
            section_title: str | None = None
            parent_section: str | None = None
            section_path: str | None = None

            if section_heading is not None:
                section_id, section_title = section_heading
                parent_section = _parent_section_id(section_id)
                while self._section_stack:
                    top = self._section_stack[-1]
                    if section_id == top or section_id.startswith(top + "."):
                        break
                    self._section_stack.pop()
                if not self._section_stack or self._section_stack[-1] != section_id:
                    self._section_stack.append(section_id)
                section_path = "/".join(self._section_stack)
            elif self._section_stack:
                section_id = self._section_stack[-1]
                parent_section = _parent_section_id(section_id)
                section_path = "/".join(self._section_stack)

            annex_refs = _extract_annex_refs(text)
            procedure_codes = _extract_procedure_codes(text)
            percentages = _extract_percentages(text)
            deontic_markers = _extract_deontic_markers(text)
            deontic_modality = _classify_deontic_modality(text, deontic_markers)
            sut_section_refs = _extract_sut_section_refs(text)
            amendment_refs = _extract_amendment_refs(text)

            clause_type = _classify_clause_type(
                text, is_chapter, section_heading, is_amendment
            )

            rows.append(
                {
                    "paragraph_index": paragraph_index,
                    "section_id": section_id,
                    "section_title": section_title,
                    "parent_section_id": parent_section,
                    "section_path": section_path,
                    "chapter": self._chapter,
                    "clause_type": clause_type,
                    "text_tr": text,
                    "is_heading": clause_type in {"chapter", "section_heading"},
                    "is_amendment": is_amendment,
                    "is_superseded_marker": bool(
                        re.search(r"\(Mülga:", text, re.IGNORECASE)
                    ),
                    "annex_refs": _json_list(annex_refs),
                    "procedure_codes": _json_list(procedure_codes),
                    "percentages": _json_list(percentages),
                    "deontic_markers": _json_list(deontic_markers),
                    "deontic_modality": deontic_modality,
                    "sut_section_refs": _json_list(sut_section_refs),
                    "amendment_refs": _json_list(amendment_refs),
                    "source_docx": str(self.docx_path.resolve()),
                    "source_effective_date": effective_date,
                    "char_count": len(text),
                    "word_count": len(text.split()),
                }
            )

        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame

        frame.insert(0, "clause_id", [f"C{i:06d}" for i in range(1, len(frame) + 1)])
        return frame


def extract_sut_clauses(docx_path: Path, *, body_start: int | None = None) -> pd.DataFrame:
    return SutClauseExtractor(docx_path=docx_path, body_start=body_start).extract()


def write_sut_clauses_parquet(
    docx_path: Path,
    output_path: Path,
    *,
    body_start: int | None = None,
) -> pd.DataFrame:
    frame = extract_sut_clauses(docx_path, body_start=body_start)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_path, index=False)
    return frame
