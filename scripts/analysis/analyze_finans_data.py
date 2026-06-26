#!/usr/bin/env python3
"""Analyze the Acibadem Finans.XLSX extract to test the provider's claims.

Provider claim: "the data is from 6 patients."
This script tests that claim against the data and produces two artifacts:

  1. ``reports/finans-analysis.md`` — a human-readable proof report (the kind
     of thing you forward to the provider).
  2. ``reports/finans_flagged.xlsx`` — the line-level evidence: every row whose
     invoice (FATURANO) spans more than one SIRA is tagged, plus a per-invoice
     summary sheet.

The analysis is fully vectorized with Polars (no per-row Python loops). The
decisive test: a real patient identifier cannot share an invoice number with
another patient — an invoice belongs to one patient's encounter. If ``SIRA`` is
the patient id, the number of invoices spanning >1 SIRA must be 0.

Run:
    python scripts/analysis/analyze_finans_data.py
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "raw data" / "Finans.XLSX"
REPORT_MD = REPO_ROOT / "reports" / "finans-analysis.md"
FLAGGED_XLSX = REPO_ROOT / "reports" / "finans_flagged.xlsx"


def load() -> pl.DataFrame:
    """Load the Finans extract with correct dtypes (dates parsed, numbers floats).

    Reads via openpyxl (always available) then hands the rows to Polars. The
    file is small (~7.6k rows) so a single read is cheap; this avoids pulling in
    the optional ``fastexcel`` dependency that Polars' calamine engine needs.
    """
    if not SOURCE.exists():
        raise FileNotFoundError(f"Source not found: {SOURCE}")
    import openpyxl

    wb = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    ws = wb["Sheet 1"]
    rows_iter = ws.iter_rows(values_only=True)
    header = list(next(rows_iter))
    data = list(rows_iter)

    df = pl.DataFrame(
        data,
        schema=header,
        orient="row",
        schema_overrides={
            "TARIH": pl.Datetime,
            "INDIRIM_ORANI": pl.Float64,
            "KDVSIZ_FIYAT": pl.Float64,
            "KDVLI_FIYAT": pl.Float64,
            "KDVSIZ_INDIRIMLI_FIYAT": pl.Float64,
            "KDVLI_INDIRIMLI_FIYAT": pl.Float64,
            "SIRA": pl.Utf8,
            "FATURANO": pl.Utf8,
            "HIZMETKODU": pl.Utf8,
        },
    )
    return df


def per_sira_summary(df: pl.DataFrame) -> pl.DataFrame:
    """One row per SIRA: line/invoice/month counts, date span, distinct codes."""
    return (
        df.group_by("SIRA")
        .agg(
            n_lines=pl.len(),
            n_invoices=pl.col("FATURANO").n_unique(),
            n_service_codes=pl.col("HIZMETKODU").n_unique(),
            first_date=pl.col("TARIH").min(),
            last_date=pl.col("TARIH").max(),
            n_months=pl.col("TARIH").dt.strftime("%Y-%m").n_unique(),
            total_kdvli_try=pl.col("KDVLI_INDIRIMLI_FIYAT").sum(),
        )
        .with_columns(
            span_days=(pl.col("last_date") - pl.col("first_date")).dt.total_days(),
            lines_per_invoice=pl.col("n_lines") / pl.col("n_invoices"),
        )
        .sort("n_lines", descending=True)
    )


def per_invoice_summary(df: pl.DataFrame) -> pl.DataFrame:
    """One row per FATURANO: distinct SIRA count + line/date breakdown.

    The ``n_distinct_sira`` column is the decisive flag: if >1, that invoice
    spans multiple patients — impossible if SIRA is the patient id.
    """
    return (
        df.group_by("FATURANO")
        .agg(
            n_lines=pl.len(),
            n_distinct_sira=pl.col("SIRA").n_unique(),
            siras=pl.col("SIRA").unique().sort(),
            n_service_codes=pl.col("HIZMETKODU").n_unique(),
            first_date=pl.col("TARIH").min(),
            last_date=pl.col("TARIH").max(),
            date_span_days=(pl.col("TARIH").max() - pl.col("TARIH").min())
            .dt.total_days(),
        )
        .sort("n_distinct_sira", "n_lines", descending=[True, True])
    )


def shared_invoice_evidence(df: pl.DataFrame, invoice: str) -> dict:
    """Build the per-SIRA breakdown for one shared invoice (for the report)."""
    sub = df.filter(pl.col("FATURANO") == invoice)
    by_sira = (
        sub.group_by("SIRA")
        .agg(
            n_lines=pl.len(),
            first_date=pl.col("TARIH").min(),
            first_code=pl.col("HIZMETKODU").first(),
            codes=pl.col("HIZMETKODU").unique(),
        )
        .sort("SIRA")
    )
    return {
        "invoice": invoice,
        "siras": by_sira.to_dicts(),
    }


def flag_rows(df: pl.DataFrame, inv_summary: pl.DataFrame) -> pl.DataFrame:
    """Attach a flag column: 1 if the row's invoice spans >1 SIRA, else 0."""
    dirty = inv_summary.filter(pl.col("n_distinct_sira") > 1).select("FATURANO")
    return df.join(
        dirty.with_columns(pl.lit(1).alias("FLAG_shared_invoice")),
        on="FATURANO",
        how="left",
    ).with_columns(pl.col("FLAG_shared_invoice").fill_null(0))


def write_markdown(
    df: pl.DataFrame,
    sira_sum: pl.DataFrame,
    inv_sum: pl.DataFrame,
    flagged: pl.DataFrame,
) -> None:
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    shared = inv_sum.filter(pl.col("n_distinct_sira") > 1)
    total_lines = df.height
    n_shared = shared.height
    n_shared_lines = flagged.filter(pl.col("FLAG_shared_invoice") == 1).height

    lines: list[str] = []
    lines.append("# Finans.XLSX — Veri Bütünlük Analizi")
    lines.append("")
    lines.append(f"**Kaynak:** `{SOURCE.relative_to(REPO_ROOT)}`")
    lines.append(
        f"**Toplam satır:** {total_lines:,}  ·  "
        f"**Benzersiz FATURANO:** {df['FATURANO'].n_unique():,}  ·  "
        f"**Benzersiz SIRA:** {df['SIRA'].n_unique()}"
    )
    lines.append("")

    # ---- Headline finding ----
    lines.append("## Özet Karar")
    lines.append("")
    if n_shared == 0:
        verdict = "✅ Tutarlı: hiçbir fatura birden fazla SIRA'da görünmüyor."
    else:
        verdict = (
            f"❌ **TUTARSIZ:** {n_shared} fatura birden fazla SIRA'da görünüyor. "
            "SIRA hasta numarasıysa bu imkânsız (bir fatura tek hastaya aittir)."
        )
    lines.append(verdict)
    lines.append("")

    # ---- Provider claim check ----
    lines.append("## Sağlayıcı İddiası: \"6 hasta\"")
    lines.append("")
    lines.append(
        f"Veride {df['SIRA'].n_unique()} benzersiz SIRA var (iddia edilen 6 ile uyumlu). "
        "Ancak satır yoğunluğu ve fatura paylaşımı bu sayının **gerçek hasta sayısı "
        "olmayabileceğini** gösteriyor:"
    )
    lines.append("")
    lines.append("| SIRA | Satır | Fatura | Ay | Tarih aralığı | Kod | Satır/Fatura |")
    lines.append("|------|-------|--------|----|---------------|-----|--------------|")
    for r in sira_sum.iter_rows(named=True):
        span = f"{r['first_date'].date()} → {r['last_date'].date()}"
        lines.append(
            f"| {r['SIRA']} | {r['n_lines']:,} | {r['n_invoices']} | {r['n_months']} | "
            f"{span} | {r['n_service_codes']} | {r['lines_per_invoice']:.1f} |"
        )
    lines.append("")
    lines.append(
        "> Tek bir SIRA'nın 2.500+ satır üretmesi 7 yılda \"tek hasta\" veya "
        "\"bir kohort/bölüm\" olabilir. Satır yoğunluğu tek başına karar verici değil."
    )
    lines.append("")

    # ---- Decisive evidence ----
    lines.append("## Karar Verici Kanıt: Birden fazla SIRA'da görünen faturalar")
    lines.append("")
    lines.append(
        f"**{n_shared} fatura** birden fazla SIRA'da görünüyor "
        f"({n_shared_lines:,} satırı etkiliyor). Her biri için ayrıntı:"
    )
    lines.append("")
    for r in shared.iter_rows(named=True):
        inv = r["FATURANO"]
        ev = shared_invoice_evidence(df, inv)
        lines.append(f"### FATURANO `{inv}` — {len(ev['siras'])} SIRA, {r['n_lines']} satır")
        lines.append("")
        lines.append(
            f"- Tarih aralığı: **{r['first_date'].date()} → {r['last_date'].date()}** "
            f"({r['date_span_days']} gün)"
        )
        lines.append(f"- Hizmet kodu sayısı: {r['n_service_codes']}")
        lines.append("")
        lines.append("| SIRA | Satır | İlk tarih | İlk kod |")
        lines.append("|------|-------|-----------|---------|")
        for s in ev["siras"]:
            lines.append(
                f"| {s['SIRA']} | {s['n_lines']} | {s['first_date'].date()} | `{s['first_code']}` |"
            )
        lines.append("")

    # ---- Smoking gun ----
    placeholder = inv_sum.filter(pl.col("FATURANO").is_in(["0", "1"]))
    if placeholder.height:
        lines.append("## Reddedilen Fatura Numaraları (Placeholder)")
        lines.append("")
        lines.append(
            "`FATURANO = 0` ve `FATURANO = 1` gerçek fatura değil — geçersiz/bilinmeyen "
            "için kullanılan değer. Bu yüzden birden fazla SIRA'da görünüyor:"
        )
        lines.append("")
        lines.append("| FATURANO | SIRA'lar | Satır | Tarih aralığı |")
        lines.append("|----------|----------|-------|---------------|")
        for r in placeholder.iter_rows(named=True):
            lines.append(
                f"| {r['FATURANO']} | {r['siras']} | {r['n_lines']} | "
                f"{r['first_date'].date()} → {r['last_date'].date()} |"
            )
        lines.append("")
        real_shared = shared.filter(~pl.col("FATURANO").is_in(["0", "1"]))
        lines.append(
            f"Bunları çıkarsak bile **{real_shared.height} gerçek fatura** hâlâ "
            "birden fazla SIRA'da görünüyor — yani placeholder hatası tek açıklama değil."
        )
        lines.append("")

    # ---- Conclusion ----
    lines.append("## Sonuç ve Sorulacak Sorular")
    lines.append("")
    lines.append(
        "1. **\"SIRA hasta numarası mı?\"** — öyleyse neden "
        f"{real_shared.height if placeholder.height else n_shared} gerçek fatura "
        "birden fazla SIRA'da görünüyor?"
    )
    lines.append(
        "2. **\"Her SIRA tek bir hastanın geçmişi mi, yoksa grup/kohort mu?\"** — "
        "satır yoğunluğu (SIRA 91: 2.500+ satır / 7 yıl) iki duruma da uyuyor."
    )
    lines.append(
        "3. **Gerçek hasta protokol numarası (dosya no / patient ID)** verilmesi — "
        "bunlar olmadan gerçek hasta sayısı kanıtlanamaz."
    )
    lines.append("")
    lines.append("## Çıktılar")
    lines.append("")
    lines.append(
        f"- Bu rapor: `{REPORT_MD.relative_to(REPO_ROOT)}`\n"
        f"- İşaretli satırlar: `{FLAGGED_XLSX.relative_to(REPO_ROOT)}` "
        f"(`FLAG_shared_invoice` sütunu = 1 olanlar problemli)"
    )

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT_MD.relative_to(REPO_ROOT)}")


def write_flagged_xlsx(
    inv_sum: pl.DataFrame, flagged: pl.DataFrame
) -> None:
    """Write per-invoice summary + flagged line rows to a clean xlsx.

    Uses openpyxl directly (always available) rather than ``pl.ExcelWriter``,
    which would pull in an optional xlsx engine dependency.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    FLAGGED_XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F3A5F")
    dirty_fill = PatternFill("solid", fgColor="FCE4E4")

    # --- Sheet 1: per-invoice summary, shared-invoices first ---
    ws1 = wb.active
    ws1.title = "fatura_ozeti"
    inv_sorted = inv_sum.sort("n_distinct_sira", "n_lines", descending=[True, True])
    cols1 = inv_sorted.columns
    ws1.append(cols1)
    for r in inv_sorted.iter_rows(named=True):
        row_vals = []
        for c in cols1:
            v = r[c]
            if hasattr(v, "date"):
                row_vals.append(v.date())
            elif isinstance(v, list):
                row_vals.append(",".join(map(str, v)))
            else:
                row_vals.append(v)
        ws1.append(row_vals)
    for cell in ws1[1]:
        cell.font = header_font
        cell.fill = header_fill
    ws1.freeze_panes = "A2"

    # --- Sheet 2: line-level rows with flag, dirty rows first ---
    ws2 = wb.create_sheet("isaretli_satirlar")
    flagged_sorted = flagged.sort(
        "FLAG_shared_invoice", "FATURANO", descending=[True, False]
    )
    cols2 = flagged_sorted.columns
    ws2.append(cols2)
    for r in flagged_sorted.iter_rows(named=True):
        row_vals = []
        for c in cols2:
            v = r[c]
            if hasattr(v, "date"):
                row_vals.append(v.date())
            else:
                row_vals.append(v)
        ws2.append(row_vals)
    for cell in ws2[1]:
        cell.font = header_font
        cell.fill = header_fill
    ws2.freeze_panes = "A2"
    # tint dirty rows
    flag_col = cols2.index("FLAG_shared_invoice") + 1
    for ridx in range(2, ws2.max_row + 1):
        if ws2.cell(row=ridx, column=flag_col).value == 1:
            for cidx in range(1, len(cols2) + 1):
                ws2.cell(row=ridx, column=cidx).fill = dirty_fill

    wb.save(FLAGGED_XLSX)
    print(f"Wrote {FLAGGED_XLSX.relative_to(REPO_ROOT)}")


def main() -> None:
    df = load()
    sira_sum = per_sira_summary(df)
    inv_sum = per_invoice_summary(df)
    flagged = flag_rows(df, inv_sum)

    shared = inv_sum.filter(pl.col("n_distinct_sira") > 1)
    print("=" * 60)
    print("FINANS.XLSX ANALIZI")
    print("=" * 60)
    print(f"Toplam satır:              {df.height:,}")
    print(f"Benzersiz SIRA:            {df['SIRA'].n_unique()}")
    print(f"Benzersiz FATURANO:        {df['FATURANO'].n_unique():,}")
    print(f"Birden fazla SIRA fatura:  {shared.height}  <-- karar verici")
    print()
    print("SIRA basina:")
    print(sira_sum.select("SIRA", "n_lines", "n_invoices", "n_months", "span_days"))
    print()

    write_markdown(df, sira_sum, inv_sum, flagged)
    write_flagged_xlsx(inv_sum, flagged)


if __name__ == "__main__":
    main()
