"""Claim header totals and EK-2C-1 reconciliation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd

from catalog import _money

def _reconcile_claim_header_totals(
    claims: list[dict[str, Any]],
    procedure_rows: list[dict[str, Any]],
    materials: list[dict[str, Any]],
    drug_rows: list[dict[str, Any]],
    expected: list[dict[str, Any]] | None = None,
) -> None:
    """Recompute claim header billed/payable totals from line sums."""
    billed_by_claim: dict[str, float] = defaultdict(float)
    payable_by_claim: dict[str, float] = defaultdict(float)

    for rows in (procedure_rows, materials, drug_rows):
        for row in rows:
            claim_id = str(row.get("fatura_id", ""))
            if not claim_id:
                continue
            billed_by_claim[claim_id] += float(row.get("fatura_tutari_try") or 0)
            payable_by_claim[claim_id] += float(row.get("beklenen_odenebilir_tutar_try") or 0)

    claim_level_expected = {
        str(row.get("fatura_id", "")): row
        for row in (expected or [])
        if str(row.get("satir_tipi", "")) == "fatura" and not str(row.get("satir_id", ""))
    }

    for claim in claims:
        claim_id = str(claim.get("fatura_id", ""))
        billed = billed_by_claim.get(claim_id, 0.0)
        payable = payable_by_claim.get(claim_id, 0.0)
        claim["beklenen_toplam_fatura_tutari_try"] = _money(billed)
        claim["beklenen_toplam_odenebilir_tutar_try"] = _money(payable)

        expected_row = claim_level_expected.get(claim_id)
        if expected_row is not None:
            expected_row["beklenen_odenebilir_tutar_try"] = _money(payable)
            expected_row["beklenen_tasarruf_try"] = _money(billed - payable)
            expected_row["beklenen_durum"] = (
                "kismi_red" if payable < billed else "odenebilir"
            )


def _build_normalized_ek2c1_copay_rates(ek2c1_df: pd.DataFrame) -> dict[str, float]:
    """EK-2C-1 mandated copay fractions keyed by normalized procedure code."""
    from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code

    rates: dict[str, float] = {}
    if ek2c1_df.empty:
        return rates
    for _, row in ek2c1_df.iterrows():
        norm = normalize_procedure_code(str(row["procedure_code"]))
        if norm:
            rates[norm] = float(row["copay_rate_pct"]) / 100.0
    return rates


def _reconcile_ek2c1_procedure_lines(
    rows: list[dict[str, Any]],
    ek2c1_copay_rates: dict[str, float],
) -> None:
    """Align EK-2C-1 listed lines: flag on + payable = billed × (1 − mandated copay %)."""
    from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code

    for row in rows:
        if row.get("pakete_dahil_mi"):
            code = normalize_procedure_code(str(row.get("islem_kodu") or ""))
            if code in ek2c1_copay_rates:
                row["katilim_payi_orani_uygulanabilir_mi"] = False
                row["katilim_payi_orani"] = None
            continue
        code = normalize_procedure_code(str(row.get("islem_kodu") or ""))
        if not code or code not in ek2c1_copay_rates:
            continue
        billed = float(row.get("fatura_tutari_try") or 0)
        if billed <= 0:
            continue
        copay_frac = ek2c1_copay_rates[code]
        row["katilim_payi_orani_uygulanabilir_mi"] = True
        row["katilim_payi_orani"] = copay_frac
        row["ilave_ucret_uygulanabilir_mi"] = False
        row["ilave_ucret_orani"] = None
        payable = _money(billed * (1 - copay_frac))
        row["beklenen_odenebilir_tutar_try"] = min(payable, billed)


def _ensure_ek2c1_violation_demos(
    procedure_rows: list[dict[str, Any]],
    ek2c1_copay_rates: dict[str, float],
) -> None:
    """Inject a small fixed set of deliberate EK-2C-1 violations for optimizer demos."""
    from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code

    catalog_lines: list[dict[str, Any]] = []
    for row in procedure_rows:
        if row.get("pakete_dahil_mi"):
            continue
        code = normalize_procedure_code(str(row.get("islem_kodu") or ""))
        billed = float(row.get("fatura_tutari_try") or 0)
        if code in ek2c1_copay_rates and billed > 0:
            catalog_lines.append(row)

    if len(catalog_lines) < 3:
        return

    row_rate_1 = catalog_lines[0]
    billed_1 = float(row_rate_1["fatura_tutari_try"])
    row_rate_1["katilim_payi_orani_uygulanabilir_mi"] = True
    row_rate_1["beklenen_odenebilir_tutar_try"] = billed_1

    row_rate_2 = catalog_lines[1]
    billed_2 = float(row_rate_2["fatura_tutari_try"])
    code_2 = normalize_procedure_code(str(row_rate_2["islem_kodu"]))
    mandated_2 = ek2c1_copay_rates[code_2]
    wrong_frac = mandated_2 + 0.20 if mandated_2 <= 0.60 else mandated_2 - 0.20
    if abs(wrong_frac - mandated_2) < 0.01:
        wrong_frac = 0.20
    row_rate_2["katilim_payi_orani_uygulanabilir_mi"] = True
    row_rate_2["katilim_payi_orani"] = wrong_frac
    row_rate_2["beklenen_odenebilir_tutar_try"] = _money(billed_2 * (1 - wrong_frac))

    row_flag = catalog_lines[2]
    row_flag["katilim_payi_orani_uygulanabilir_mi"] = False
    row_flag["katilim_payi_orani"] = None

