#!/usr/bin/env python3
"""Build human-review XLSX + HTML sidecars from a prose_corpus CSV.

Prototype for Gate B auditing: legend + readable excerpts. Does not replace
machine-readable CSV exports.

Usage:
  python scripts/sut/export_prose_review_bundle.py
  python scripts/sut/export_prose_review_bundle.py --csv data/gazette/prose_corpus/L4.33_anti_vegf_corpus.csv
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_DEFAULT_CSV = (
    _PROJECT_ROOT / "data/gazette/prose_corpus/L1.4_material_bundling_prose.csv"
)
_DEFAULT_OUT_DIR = _PROJECT_ROOT / "data/gazette/prose_corpus/review"


def _resolve_project_path(path: Path) -> Path:
    """Resolve CLI paths relative to repo root when needed."""
    if path.is_absolute():
        return path.resolve()
    return (_PROJECT_ROOT / path).resolve()


def _project_rel(path: Path) -> str:
    resolved = _resolve_project_path(path)
    try:
        return str(resolved.relative_to(_PROJECT_ROOT))
    except ValueError:
        return str(path)

# Shared legend rows: (column, meaning_tr, example_values)
_LEGEND_ROWS: list[tuple[str, str, str]] = [
    ("clause_id", "sut_clauses.parquet anahtarı; Rule Database'de tam metin", "C001618"),
    (
        "section_id",
        "SUT bölüm numarası",
        "3.1.1",
    ),
    (
        "section_title",
        "Bölüm başlığı (varsa)",
        "Tıbbi malzeme bedellerinin karşılanması",
    ),
    (
        "deontic_modality",
        "Yükümlülük tipi (otomatik sınıflandırma)",
        "NO_PAY | MUST_NOT_BILL | (boş)",
    ),
    (
        "selection_reason",
        "Satırın corpus'a alınma nedeni",
        "deontic | keyword",
    ),
    (
        "duplicate_of",
        "EK listesi ile tekrar mı?",
        "none | ek3b1 | ek3b2",
    ),
    (
        "encode_priority",
        "JSON kurala çevirme önerisi",
        "p1_encode | skip_annex_duplicate | skip_already_encoded | defer_tier_c | p2_encode",
    ),
    (
        "encoded_rule_id",
        "Zaten var olan prose_rules JSON kural id (varsa)",
        "3.1.2.(2).not_in_ek3c",
    ),
    (
        "suggested_condition_type",
        "Önerilen makine koşulu tipi",
        "titubb_uts_field | material_not_in_ek3c | manual_review",
    ),
    (
        "annex_refs",
        "Metinde geçen EK referansları (JSON liste)",
        '["EK-3/B"]',
    ),
    (
        "excerpt",
        "Hüküm metni (tam veya önizleme)",
        "Uzun Türkçe paragraf",
    ),
    (
        "char_count",
        "excerpt karakter sayısı",
        "950",
    ),
    # L4.33 / drug exports
    ("indication_group", "Endikasyon grubu (slug)", "dmo | wet_amd | general_4_2_33"),
    ("indication_tr", "Endikasyon Türkçe etiket", ""),
    ("inn", "Etkin madde (INN)", "ranibizumab | (non-INN)"),
    ("text_excerpt", "Kısaltılmış metin önizlemesi (~400 char)", ""),
    ("full_text", "Tam hüküm metni", ""),
]

_EXCERPT_COLUMNS = frozenset(
    {"excerpt", "text_excerpt", "full_text", "text_tr"}
)


def _preview(text: str, limit: int = 200) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _legend_for_columns(columns: list[str]) -> list[tuple[str, str, str]]:
    known = {row[0]: row for row in _LEGEND_ROWS}
    rows: list[tuple[str, str, str]] = []
    for col in columns:
        if col in known:
            rows.append(known[col])
        else:
            rows.append((col, "(bu pilot export'ta özel açıklama yok)", ""))
    return rows


def write_xlsx(
    df: pl.DataFrame,
    path: Path,
    *,
    title: str,
    source_csv: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    # --- Legend sheet ---
    ws_leg = wb.active
    ws_leg.title = "legend"
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F3A5F")
    for col_idx, header in enumerate(["column", "meaning_tr", "example_values"], start=1):
        cell = ws_leg.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
    for row_idx, (col, meaning, examples) in enumerate(
        _legend_for_columns(df.columns), start=2
    ):
        ws_leg.cell(row=row_idx, column=1, value=col)
        ws_leg.cell(row=row_idx, column=2, value=meaning)
        ws_leg.cell(row=row_idx, column=3, value=examples)
    ws_leg.column_dimensions["A"].width = 22
    ws_leg.column_dimensions["B"].width = 55
    ws_leg.column_dimensions["C"].width = 40
    ws_leg.freeze_panes = "A2"

    # --- Meta sheet ---
    ws_meta = wb.create_sheet("meta")
    meta_rows = [
        ("title", title),
        ("source_csv", _project_rel(source_csv)),
        ("row_count", str(df.height)),
        ("generated_at", datetime.now(UTC).replace(microsecond=0).isoformat()),
        ("note", "excerpt sütunları wrap-text açık; tam metin HTML'de de var"),
    ]
    for i, (k, v) in enumerate(meta_rows, start=1):
        ws_meta.cell(row=i, column=1, value=k)
        ws_meta.cell(row=i, column=2, value=v)
    ws_meta.column_dimensions["A"].width = 16
    ws_meta.column_dimensions["B"].width = 70

    # --- Data sheet ---
    ws = wb.create_sheet("corpus")
    columns = df.columns
    # Add preview column before long text columns
    display_cols = list(columns)
    excerpt_col = next((c for c in columns if c in _EXCERPT_COLUMNS), None)
    if excerpt_col and f"{excerpt_col}_preview" not in display_cols:
        display_cols = [c for c in display_cols if c != excerpt_col]
        preview_idx = len(display_cols)
        display_cols.insert(preview_idx, f"{excerpt_col}_preview")
        display_cols.insert(preview_idx + 1, excerpt_col)

    for col_idx, name in enumerate(display_cols, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.font = header_font
        cell.fill = header_fill

    wrap = Alignment(wrap_text=True, vertical="top")
    for row_idx, record in enumerate(df.iter_rows(named=True), start=2):
        for col_idx, name in enumerate(display_cols, start=1):
            if name.endswith("_preview") and excerpt_col:
                value = _preview(str(record.get(excerpt_col) or ""), 200)
            else:
                base = name.removesuffix("_preview") if name.endswith("_preview") else name
                value = record.get(base)
            if value is None:
                value = ""
            cell = ws.cell(row=row_idx, column=col_idx, value=str(value))
            if name in _EXCERPT_COLUMNS or name.endswith("_preview"):
                cell.alignment = wrap

    for col_idx, name in enumerate(display_cols, start=1):
        letter = get_column_letter(col_idx)
        if name in _EXCERPT_COLUMNS:
            ws.column_dimensions[letter].width = 70
        elif name.endswith("_preview"):
            ws.column_dimensions[letter].width = 35
        elif name in {"clause_id", "encoded_rule_id"}:
            ws.column_dimensions[letter].width = 24
        else:
            ws.column_dimensions[letter].width = 18
    ws.freeze_panes = "A2"

    wb.save(path)


def write_html(
    df: pl.DataFrame,
    path: Path,
    *,
    title: str,
    source_csv: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    excerpt_col = next((c for c in df.columns if c in _EXCERPT_COLUMNS), "excerpt")
    legend_rows = _legend_for_columns(df.columns)
    generated = datetime.now(UTC).replace(microsecond=0).isoformat()

    cards: list[str] = []
    for record in df.iter_rows(named=True):
        clause_id = html.escape(str(record.get("clause_id") or ""))
        section = html.escape(str(record.get("section_id") or ""))
        priority = html.escape(str(record.get("encode_priority") or record.get("indication_group") or ""))
        excerpt = html.escape(str(record.get(excerpt_col) or record.get("full_text") or ""))

        meta_bits = []
        for key in df.columns:
            if key in _EXCERPT_COLUMNS:
                continue
            val = record.get(key)
            if val is None or val == "":
                continue
            meta_bits.append(
                f"<tr><th>{html.escape(key)}</th><td>{html.escape(str(val))}</td></tr>"
            )
        meta_table = "\n".join(meta_bits)

        cards.append(
            f"""
<article class="card" id="{clause_id}">
  <header>
    <h2>{clause_id} <span class="muted">§{section}</span></h2>
    <p class="badge">{priority or '—'}</p>
  </header>
  <table class="meta">{meta_table}</table>
  <details open>
    <summary>Tam metin ({excerpt_col})</summary>
    <pre class="excerpt">{excerpt}</pre>
  </details>
</article>"""
        )

    legend_html = "\n".join(
        f"<tr><td><code>{html.escape(c)}</code></td>"
        f"<td>{html.escape(m)}</td>"
        f"<td><code>{html.escape(e)}</code></td></tr>"
        for c, m, e in legend_rows
    )

    doc = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)} — review</title>
  <style>
    :root {{ font-family: system-ui, sans-serif; line-height: 1.45; color: #1a1a1a; }}
    body {{ max-width: 960px; margin: 0 auto; padding: 1.5rem; background: #f6f7f9; }}
    h1 {{ font-size: 1.35rem; margin-bottom: 0.25rem; }}
    .muted {{ color: #666; font-weight: normal; font-size: 0.9rem; }}
    .intro {{ background: #fff; border: 1px solid #dde3ea; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1.25rem; }}
    table.legend {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    table.legend th, table.legend td {{ border: 1px solid #dde3ea; padding: 0.4rem 0.6rem; text-align: left; vertical-align: top; }}
    table.legend th {{ background: #1f3a5f; color: #fff; }}
    .card {{ background: #fff; border: 1px solid #dde3ea; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1rem; }}
    .card h2 {{ margin: 0 0 0.35rem; font-size: 1.05rem; }}
    .badge {{ display: inline-block; margin: 0; padding: 0.15rem 0.5rem; background: #e8f0fe; border-radius: 4px; font-size: 0.8rem; }}
    table.meta {{ width: 100%; font-size: 0.82rem; border-collapse: collapse; margin: 0.5rem 0 0.75rem; }}
    table.meta th {{ text-align: left; width: 28%; color: #444; padding: 0.2rem 0.5rem 0.2rem 0; vertical-align: top; }}
    table.meta td {{ padding: 0.2rem 0; }}
    pre.excerpt {{ white-space: pre-wrap; word-break: break-word; background: #f9fafb; border: 1px solid #eef1f4; border-radius: 6px; padding: 0.75rem; font-size: 0.88rem; margin: 0.5rem 0 0; }}
    details summary {{ cursor: pointer; font-weight: 600; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <div class="intro">
    <h1>{html.escape(title)}</h1>
    <p class="muted">Kaynak: <code>{html.escape(str(source_csv.relative_to(_PROJECT_ROOT)))}</code>
      · {df.height} satır · {html.escape(generated)}</p>
    <h3>Kolon sözlüğü</h3>
    <table class="legend">
      <thead><tr><th>Kolon</th><th>Anlam (TR)</th><th>Örnek değerler</th></tr></thead>
      <tbody>{legend_html}</tbody>
    </table>
  </div>
  {''.join(cards)}
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export prose corpus review XLSX + HTML.")
    parser.add_argument("--csv", type=Path, default=_DEFAULT_CSV)
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
    parser.add_argument(
        "--title",
        default="L1.4 Material bundling Gate B (§3.1–3.2)",
        help="Human title shown in HTML meta sheet",
    )
    parser.add_argument("--stem", default=None, help="Output file stem (default: CSV stem)")
    args = parser.parse_args()

    csv_path = _resolve_project_path(args.csv)
    out_dir = _resolve_project_path(args.out_dir)

    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")

    df = pl.read_csv(csv_path)
    stem = args.stem or csv_path.stem
    xlsx_path = out_dir / f"{stem}.review.xlsx"
    html_path = out_dir / f"{stem}.review.html"

    write_xlsx(df, xlsx_path, title=args.title, source_csv=csv_path)
    write_html(df, html_path, title=args.title, source_csv=csv_path)

    manifest = {
        "title": args.title,
        "source_csv": _project_rel(csv_path),
        "row_count": df.height,
        "xlsx": _project_rel(xlsx_path),
        "html": _project_rel(html_path),
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    manifest_path = out_dir / f"{stem}.review.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"Wrote {_project_rel(xlsx_path)}")
    print(f"Wrote {_project_rel(html_path)}")
    print(f"Wrote {_project_rel(manifest_path)}")


if __name__ == "__main__":
    main()
