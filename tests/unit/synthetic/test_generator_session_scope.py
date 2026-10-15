"""The synthetic generator applies session factors to operations only, like the engine (#261)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPTS_SYNTHETIC = Path(__file__).resolve().parents[3] / "scripts" / "synthetic"
if str(SCRIPTS_SYNTHETIC) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_SYNTHETIC))

from gen.claim_lines import _apply_session_point_billed_factors  # noqa: E402


def _row(line: int, code: str, billed: float) -> dict:
    return {
        "islem_satiri_id": f"L{line}", "fatura_id": "F1", "hasta_id": "H1", "basvuru_id": "B1",
        "islem_tarihi": "2026-08-18", "islem_kodu": code, "islem_adi": code,
        "islem_kategorisi": "islem", "adet": 1, "birim_fiyat_try": billed,
        "fatura_tutari_try": billed, "beklenen_odenebilir_tutar_try": billed,
        "pakete_dahil_mi": False,
    }


def test_only_the_second_operation_is_scaled() -> None:
    rows = [
        _row(1, "615931", 3837.32),  # Primary operation (higher puan).
        _row(2, "615995", 3032.01),  # Secondary operation: 30 %.
        _row(3, "510010", 222.36),  # Bed, anaesthesia and lab keep their amount.
        _row(4, "550160", 928.09),
        _row(5, "L107020", 30.00),
    ]
    _apply_session_point_billed_factors(rows)
    assert [row["fatura_tutari_try"] for row in rows] == [3837.32, 909.60, 222.36, 928.09, 30.00]


def test_lines_without_a_second_operation_are_untouched() -> None:
    rows = [_row(1, "615931", 3837.32), _row(2, "550160", 928.09), _row(3, "510010", 222.36)]
    assert _apply_session_point_billed_factors(rows) == (0.0, 0.0)
    assert [row["fatura_tutari_try"] for row in rows] == [3837.32, 928.09, 222.36]
