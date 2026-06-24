#!/usr/bin/env python3
"""Export §4.2.33 anti-VEGF / göz ilaçları prose corpus (L4.33 Phase 0).

Extracts SUT §4.2.33 clauses (göz hastalıklarında ilaç kullanım ilkeleri), groups
actionable clauses by (INN, endikasyon alt-bölümü), and extracts dose-protocol
metadata (loading-dose count, annual max) via regex so the golden-file JSON in
Phase 2 can be compiled with full provenance to clause_ids.

§4.2.33 is the only §4.2 subsection whose rules have direct private-hospital revenue
impact (günübirlik intravitreal injection — both "reçete" and "uygulanır" verbs).
Output corpus feeds data/gazette/prose_rules/anti_vegf_prose.json (Phase 2).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_DEFAULT_CLAUSES = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
_DEFAULT_OUT_CSV = _PROJECT_ROOT / "data/gazette/prose_corpus/L4.33_anti_vegf_corpus.csv"
_DEFAULT_OUT_SUMMARY = _PROJECT_ROOT / "data/gazette/prose_corpus/L4.33_anti_vegf_summary.json"

# INN list — anti-VEGF + ITV steroids + diğer göz ilaçları in §4.2.33
_INN_LIST = [
    "ranibizumab",
    "bevacizumab",
    "aflibersept",
    "pegaptanib",
    "verteporfin",
    "vertaporfin",  # SUT spelling variant
    "deksametazon",  # intravitreal implant
    "siklosporin",
    "sisteamin",
    "merkaptamin",  # sisteamin synonym
]

# Alt-bölüm → endikasyon grubu + ICD-10 (ICD-10 SUT metninde yok, endikasyondan çıkarıldı)
_SUBSECTION_MAP: dict[str, dict[str, object]] = {
    "4.2.33.A": {
        "indication": "yas_tip_yas_bagli_makula_dejenerasyonu_wet_amd",
        "indication_tr": "Yaş tip yaşa bağlı makula dejenerasyonu (YAŞ AMD)",
        "icd10_codes": ["H35.3"],
    },
    "4.2.33.B": {
        "indication": "retina_ven_dali_tikanikligi_rvdt_srvt",
        "indication_tr": "Retina ven dal/santral retinal ven tıkanıklığı (RVDT/SRVT)",
        "icd10_codes": ["H34.8"],
    },
    "4.2.33.C": {
        "indication": "patolojik_miyopi_koroidal_neovaskularizasyon",
        "indication_tr": "Patolojik miyopiye bağlı koroidal neovaskülarizasyon (PM-KNV)",
        "icd10_codes": ["H44.2"],
    },
    "4.2.33.Ç": {
        "indication": "diyabetik_makuler_odem_dmo",
        "indication_tr": "Diyabetik maküler ödem (DMÖ)",
        "icd10_codes": ["E10.3", "E11.3", "E13.3", "E14.3"],
    },
    "4.2.33.D": {
        "indication": "diyabetik_makuler_odem_dmo",
        "indication_tr": "Diyabetik maküler ödem (DMÖ) — D varyantı",
        "icd10_codes": ["E10.3", "E11.3", "E13.3", "E14.3"],
    },
    "4.2.33.E": {
        "indication": "diger_goz_hastaliklari",
        "indication_tr": "Göz hastalıklarında kullanılan diğer ilaçlar",
        "icd10_codes": [],
    },
    "4.2.33.F": {
        "indication": "premature_retinopatisi_rop",
        "indication_tr": "Prematüre retinopatisi (ROP)",
        "icd10_codes": ["H35.1", "P35.1"],
    },
}

# Doz protokolü regex'leri (SUT metninden loading/annual-max çıkarma)
_RE_LOADING_DOSE_COUNT = re.compile(
    r"(?:ardışık|peş peşe|üst üste).{0,40}?(\d+)\s*uygulama"
    r"|(\d+)\s*kez\s+yükleme"
    r"|yükleme.{0,40}?(\d+)\s*(?:doz|uygulama)",
    re.IGNORECASE,
)
_RE_ANNUAL_MAX = re.compile(
    r"(?:yılda|maksimum|en fazla).{0,30}?(\d+)\s*uygulama", re.IGNORECASE
)
_RE_REPORT_DURATION = re.compile(r"(\d+)\s*ay\s*süreli", re.IGNORECASE)
_RE_AYAKTA = re.compile(r"ayakta\s+tedavi", re.IGNORECASE)
_RE_GUNUBIRLIK = re.compile(r"günübirlik\s+tedavi", re.IGNORECASE)


def _extract_inns(text: str) -> list[str]:
    """Return canonical INNs mentioned in the clause text."""
    lower = text.lower()
    hits = []
    canonical = {
        "ranibizumab": "ranibizumab",
        "bevacizumab": "bevacizumab",
        "aflibersept": "aflibersept",
        "aflibercept": "aflibersept",  # EN spelling variant
        "pegaptanib": "pegaptanib",
        "verteporfin": "verteporfin",
        "vertaporfin": "verteporfin",
        "deksametazon": "deksametazon",
        "siklosporin": "siklosporin",
        "sisteamin": "sisteamin",
        "merkaptamin": "sisteamin",
    }
    for token, canon in canonical.items():
        if token in lower:
            if canon not in hits:
                hits.append(canon)
    return hits


def _extract_dose_protocol(text: str) -> dict[str, object]:
    """Extract loading-dose count + annual max via regex (best-effort, manual review in Phase 2)."""
    loading = None
    m = _RE_LOADING_DOSE_COUNT.search(text)
    if m:
        for g in m.groups():
            if g:
                loading = int(g)
                break

    annual_max = None
    m = _RE_ANNUAL_MAX.search(text)
    if m:
        annual_max = int(m.group(1))

    durations = [int(x) for x in _RE_REPORT_DURATION.findall(text)]
    report_duration_months = max(durations) if durations else None

    return {
        "loading_dose_count": loading,
        "max_applications_per_year": annual_max,
        "report_duration_months": report_duration_months,
        "ayakta_tedavi": bool(_RE_AYAKTA.search(text)),
        "gunubirlik_tedavi": bool(_RE_GUNUBIRLIK.search(text)),
    }


def build_corpus(clauses_path: Path) -> pl.DataFrame:
    """Filter §4.2.33 substantive clauses, tag INNs + dose protocol metadata."""
    all_4233 = pl.read_parquet(clauses_path).filter(
        pl.col("section_id").str.starts_with("4.2.33")
    )
    substantive = all_4233.filter(
        (pl.col("is_heading") == False) & (pl.col("is_amendment") == False)
    )

    rows: list[dict[str, object]] = []
    for record in substantive.sort(["section_id", "paragraph_index"]).iter_rows(named=True):
        text = str(record.get("text_tr") or "")
        section_id = str(record.get("section_id") or "")
        inns = _extract_inns(text)
        if not inns:
            # Non-INN clause (tanım, etkinlik kriteri, genel kural) — keep for context
            inns = ["(non-INN)"]

        meta = _SUBSECTION_MAP.get(section_id, {})
        dose = _extract_dose_protocol(text)

        for inn in inns:
            rows.append(
                {
                    "clause_id": str(record.get("clause_id") or ""),
                    "section_id": section_id,
                    "indication_group": meta.get("indication", "general_4_2_33"),
                    "indication_tr": meta.get("indication_tr", ""),
                    "inn": inn,
                    "loading_dose_count": dose["loading_dose_count"],
                    "max_applications_per_year": dose["max_applications_per_year"],
                    "report_duration_months": dose["report_duration_months"],
                    "ayakta_tedavi": dose["ayakta_tedavi"],
                    "gunubirlik_tedavi": dose["gunubirlik_tedavi"],
                    "text_excerpt": text[:400],
                    "full_text": text,
                }
            )

    # Explicit schema — Polars infers Int64 for some dose columns when first
    # rows are None, then fails when a later row yields int via regex.
    schema = {
        "clause_id": pl.Utf8,
        "section_id": pl.Utf8,
        "indication_group": pl.Utf8,
        "indication_tr": pl.Utf8,
        "inn": pl.Utf8,
        "loading_dose_count": pl.Int64,
        "max_applications_per_year": pl.Int64,
        "report_duration_months": pl.Int64,
        "ayakta_tedavi": pl.Boolean,
        "gunubirlik_tedavi": pl.Boolean,
        "text_excerpt": pl.Utf8,
        "full_text": pl.Utf8,
    }
    return pl.DataFrame(rows, schema=schema)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clauses", type=Path, default=_DEFAULT_CLAUSES)
    parser.add_argument("--out-csv", type=Path, default=_DEFAULT_OUT_CSV)
    parser.add_argument("--out-summary", type=Path, default=_DEFAULT_OUT_SUMMARY)
    args = parser.parse_args()

    df = build_corpus(args.clauses)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(args.out_csv)

    inn_clause_pairs = df.filter(pl.col("inn") != "(non-INN)").select(
        "inn", "clause_id"
    ).unique()
    summary = {
        "section_4_2_33_total_clauses": int(
            pl.read_parquet(args.clauses)
            .filter(pl.col("section_id").str.starts_with("4.2.33"))
            .height
        ),
        "export_row_count": df.height,
        "unique_inn_clauses": inn_clause_pairs.height,
        "inn_counts": {
            row["inn"]: row["len"]
            for row in df.filter(pl.col("inn") != "(non-INN)")
            .group_by("inn")
            .len()
            .sort("len", descending=True)
            .iter_rows(named=True)
        },
        "indication_group_counts": {
            row["indication_group"]: row["len"]
            for row in df.group_by("indication_group")
            .len()
            .sort("indication_group")
            .iter_rows(named=True)
        },
        "dose_protocol_hits": {
            "loading_dose_count_extracted": int(
                df.filter(pl.col("loading_dose_count").is_not_null()).height
            ),
            "max_applications_per_year_extracted": int(
                df.filter(pl.col("max_applications_per_year").is_not_null()).height
            ),
            "gunubirlik_signal": int(df.filter(pl.col("gunubirlik_tedavi")).height),
        },
        "note": (
            "§4.2.33 anti-VEGF / göz ilaçları corpus. ICD-10 endikasyondan çıkarıldı "
            "(SUT metninde değil). Doz protokolü regex best-effort — Phase 2 golden-file "
            "review'de elle doğrulanmalı. anti_vegf_prose.json üretimi için temel."
        ),
    }
    args.out_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {df.height} rows to {args.out_csv}")
    print(f"Summary: {args.out_summary}")
    print(f"INN clauses: {inn_clause_pairs.height} | sections: {df['section_id'].n_unique()}")


if __name__ == "__main__":
    main()
