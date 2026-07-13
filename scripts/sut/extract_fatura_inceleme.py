#!/usr/bin/env python3
"""Extract clauses from the FATURA İNCELEME USUL VE ESASLARI PDF.

This is a lightweight extractor — NOT the full OOXML pipeline used for SUT.
The Fatura İnceleme document is 170 static rules with no amendment history,
so strike/force tracking and deontic classification are unnecessary.

Categorization data (ALGORITHMIC / DOCUMENTATION / INTERPRETIVE) is sourced
from a pre-built JSON file produced by rule analysis.

Output: data/gazette/fatura_inceleme_clauses.parquet
  - clause_id: F000001+ (sequential, F-prefixed to distinguish from SUT's C)
  - section: branch name or "ORTAK KRİTERLER" / "GENEL KURALLAR"
  - rule_number: int
  - text_tr: full rule text
  - category: ALGORITHMIC | DOCUMENTATION | INTERPRETIVE
  - sut_ref: nullable string (SUT section reference, e.g. "2.2.2.A")
  - required_fields: JSON list of claim fields the rule needs
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_PDF_PATH = _PROJECT_ROOT / "raw data" / "FATURA İNCELEME USUL VE ESASLARI.pdf"
_OUTPUT_PATH = _PROJECT_ROOT / "data" / "gazette" / "fatura_inceleme_clauses.parquet"
_CATEGORIZED_JSON = Path("/tmp/fatura_rules_categorized.json")

# Section headers — all-caps Turkish branch names + structural sections
_SECTION_HEADERS = {
    "I- AÇIKLAMALAR",
    "II-GENEL KURALLAR",
    "III-ORTAK KRİTERLER",
    "IV- BRANŞLARA AİT KRİTERLER",
}

# Map raw section header to clean section name
_SECTION_MAP = {
    "I- AÇIKLAMALAR": "AÇIKLAMALAR",
    "II-GENEL KURALLAR": "GENEL KURALLAR",
    "III-ORTAK KRİTERLER": "ORTAK KRİTERLER",
    "IV- BRANŞLARA AİT KRİTERLER": "BRANŞLARA AİT KRİTERLER",
}


def _extract_pdf_text() -> str:
    """Extract text from PDF using pdftotext -layout."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(_PDF_PATH), "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _is_branch_header(line: str) -> bool:
    """Check if a line is a branch header (all-caps Turkish text, not a section)."""
    stripped = line.strip()
    if not stripped or len(stripped) < 5:
        return False
    if stripped in _SECTION_HEADERS:
        return False
    if stripped.startswith(("MADDE", "BÖLÜM", "I-", "II-", "III-", "IV-")):
        return False
    if stripped in ("SOSYAL GÜVENLİK KURUMU", "FATURA İNCELEME USUL VE ESASLARI"):
        return False
    # All-caps: Turkish uppercase letters + spaces
    return bool(re.match(r"^[A-ZÇĞİÖŞÜ ]+$", stripped))


def _parse_rules(text: str) -> list[dict]:
    """Parse numbered rules from the extracted text.

    Returns list of {section, rule_number, text_tr} dicts.
    """
    lines = text.split("\n")
    rules: list[dict] = []
    current_section = "ÖN"
    current_branch = ""
    rule_num = 0
    rule_text_lines: list[str] = []

    def _flush_rule() -> None:
        nonlocal rule_text_lines, rule_num
        if rule_num > 0 and rule_text_lines:
            text_tr = " ".join(rule_text_lines).strip()
            section = current_branch or current_section
            rules.append(
                {
                    "section": section,
                    "rule_number": rule_num,
                    "text_tr": text_tr,
                }
            )
        rule_text_lines = []
        rule_num = 0

    for line in lines:
        stripped = line.strip()

        # Section header
        if stripped in _SECTION_MAP:
            _flush_rule()
            current_section = _SECTION_MAP[stripped]
            current_branch = ""
            continue

        # Branch header (within BRANŞLARA AİT KRİTERLER)
        if current_section == "BRANŞLARA AİT KRİTERLER" and _is_branch_header(stripped):
            _flush_rule()
            current_branch = stripped
            continue

        # Numbered rule start: "  1." or "1." with content
        m = re.match(r"^(\d+)\.\s+(.*)", stripped)
        if m:
            _flush_rule()
            rule_num = int(m.group(1))
            rest = m.group(2)
            if rest:
                rule_text_lines.append(rest)
            continue

        # Continuation of current rule
        if rule_num > 0 and stripped:
            rule_text_lines.append(stripped)

    _flush_rule()
    return rules


def _load_categorization() -> dict[str, dict]:
    """Load pre-built categorization from the analysis JSON.

    Returns a lookup dict keyed by (section, rule_number) → category data.
    """
    if not _CATEGORIZED_JSON.exists():
        print(
            f"WARNING: Categorization JSON not found at {_CATEGORIZED_JSON}. "
            "All rules will default to ALGORITHMIC.",
            file=sys.stderr,
        )
        return {}

    with open(_CATEGORIZED_JSON, encoding="utf-8") as f:
        rules = json.load(f)

    lookup: dict[str, dict] = {}
    for r in rules:
        key = f"{r['section']}|{r['rule_number']}"
        lookup[key] = r
    return lookup


def _normalize_section(section: str) -> str:
    """Normalize section names to match the categorization JSON."""
    # The categorization used "ORTAK KRİTERLER" for common criteria
    if section in ("ORTAK KRİTERLER",):
        return "ORTAK KRİTERLER"
    if section in ("GENEL KURALLAR",):
        return "GENEL KURALLAR"
    if section in ("AÇIKLAMALAR",):
        return "AÇIKLAMALAR"
    return section


def build_fatura_inceleme_clauses() -> pd.DataFrame:
    """Build the clause DataFrame from the PDF + categorization."""
    text = _extract_pdf_text()
    parsed_rules = _parse_rules(text)
    categorization = _load_categorization()

    rows: list[dict] = []
    for i, rule in enumerate(parsed_rules, 1):
        section = _normalize_section(rule["section"])
        cat_key = f"{section}|{rule['rule_number']}"
        cat = categorization.get(cat_key, {})

        clause_id = f"F{i:06d}"
        rows.append(
            {
                "clause_id": clause_id,
                "section": section,
                "rule_number": rule["rule_number"],
                "text_tr": rule["text_tr"],
                "category": cat.get("category", "ALGORITHMIC"),
                "sut_ref": cat.get("sut_ref"),
                "required_fields": json.dumps(
                    cat.get("required_fields", []), ensure_ascii=False
                ),
            }
        )

    df = pd.DataFrame(rows)
    return df


def write_fatura_inceleme_parquet(
    output_path: Path | None = None,
) -> Path:
    """Extract clauses and write to parquet. Returns the output path."""
    df = build_fatura_inceleme_clauses()
    out = output_path or _OUTPUT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)

    # Summary
    print(f"Wrote {len(df)} clauses to {out}")
    print(f"  By category: {dict(df['category'].value_counts())}")
    print(f"  By section ({df['section'].nunique()} sections):")
    for section, count in df["section"].value_counts().items():
        print(f"    {section:50s} {count:3d}")
    return out


if __name__ == "__main__":
    write_fatura_inceleme_parquet()
