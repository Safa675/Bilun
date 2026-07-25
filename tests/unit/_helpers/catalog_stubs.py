"""Injected catalog fixtures so pricing tests do not freeze live gazette prices.

Use these instead of asserting absolute TRY amounts from the current EK-2B/C
as-of snapshot. See ``plans/refactor/brittle-test-remediation-plan.md`` Phase 5.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import polars as pl
import pytest

# Fixture catalog — owned by tests, not the live gazette.
FIXTURE_KATSAYI = 0.593
FIXTURE_BED_DAILY_TRY = 222.36
FIXTURE_PROC_PUAN: dict[str, float] = {
    "610130": 3397.78,  # Appendektomi → A1
    "530390": 22.46,  # Subkütan enjeksiyon → E
    "620462": 5053.36,  # Labioplasti → beyond table
}
FIXTURE_GAZETTE_SERVICE_TRY = 449.73
FIXTURE_GAZETTE_AMENDED_TRY = 539.68
FIXTURE_GAZETTE_AMENDMENT_DATE = "2026-01-01"


def install_anestezi_catalog_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    katsayi: float = FIXTURE_KATSAYI,
    puan_by_code: dict[str, float] | None = None,
) -> dict[str, float]:
    """Stub katsayi + surgical puan lookup used by anestezi_puani."""
    puan = dict(puan_by_code or FIXTURE_PROC_PUAN)

    def _lookup(raw_code: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        code = str(raw_code or "").strip().replace(".", "").replace(" ", "")
        if code.startswith("P") or code.startswith("p"):
            code = code[1:]
        if code not in puan:
            return {"entry": None}
        return {"entry": {"code": code, "puan": puan[code]}}

    monkeypatch.setattr(
        "src.bilun.domain.prose_rules.anestezi_puani.get_katsayi",
        lambda: katsayi,
    )
    monkeypatch.setattr(
        "src.bilun.domain.prose_rules.anestezi_puani.lookup_procedure_code",
        _lookup,
    )
    return puan


def install_yatak_catalog_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    daily_rate_try: float = FIXTURE_BED_DAILY_TRY,
) -> float:
    """Stub 510010 bed-day price_try used by yatak_puani."""

    def _lookup(raw_code: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        code = str(raw_code or "").strip()
        if code == "510010":
            return {"entry": {"code": code, "price_try": daily_rate_try, "puan": 374.97}}
        return {"entry": None}

    monkeypatch.setattr(
        "src.bilun.domain.prose_rules.yatak_puani.lookup_procedure_code",
        _lookup,
    )
    return daily_rate_try


def install_gazette_price_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    code: str = "600150",
    service_price: float = FIXTURE_GAZETTE_SERVICE_TRY,
    amended_price: float = FIXTURE_GAZETTE_AMENDED_TRY,
    amendment_date: str = FIXTURE_GAZETTE_AMENDMENT_DATE,
) -> dict[str, float | str]:
    """Stub temporal EK-2B lookups used by gazette_repricing."""

    amendment = date.fromisoformat(amendment_date)

    def _price_for_date(proc_code: str, procedure_date: Any, price_type: str = "price_try") -> float | None:
        normalized = str(proc_code or "").strip().replace(".", "")
        if normalized.startswith("P") or normalized.startswith("p"):
            normalized = normalized[1:]
        if normalized != code:
            return None
        asof = procedure_date
        if not isinstance(asof, date):
            asof = date.fromisoformat(str(asof)[:10])
        if asof < amendment:
            return service_price
        return amended_price

    def _history(hist_code: str, catalog: str = "ek2b") -> pl.DataFrame:
        normalized = str(hist_code or "").strip()
        if normalized.startswith("P") or normalized.startswith("p"):
            normalized = normalized[1:]
        if normalized != code:
            return pl.DataFrame(
                schema={"code": pl.Utf8, "effective_date": pl.Utf8, "price_try": pl.Float64}
            )
        return pl.DataFrame(
            {
                "code": [code, code],
                "effective_date": ["2024-01-01", amendment_date],
                "price_try": [service_price, amended_price],
            }
        )

    monkeypatch.setattr(
        "src.bilun.domain.prose_rules.gazette_repricing.get_ek2b_price_for_date",
        _price_for_date,
    )
    monkeypatch.setattr(
        "src.bilun.domain.prose_rules.gazette_repricing.get_ek2c_price_for_date",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "src.bilun.domain.prose_rules.gazette_repricing.get_price_history",
        _history,
    )
    return {
        "service_price": service_price,
        "amended_price": amended_price,
        "recoverable": amended_price - service_price,
        "amendment_date": amendment_date,
    }
