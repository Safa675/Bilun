"""Injected catalog fixtures so pricing tests do not freeze live gazette prices.

Use these instead of asserting absolute TRY amounts from the current EK-2B/C
as-of snapshot. See ``plans/refactor/brittle-test-remediation-plan.md`` Phase 5.
"""

from __future__ import annotations

from typing import Any

import pytest

# Fixture catalog — owned by tests, not the live gazette.
FIXTURE_KATSAYI = 0.593
FIXTURE_BED_DAILY_TRY = 222.36
FIXTURE_PROC_PUAN: dict[str, float] = {
    "610130": 3397.78,  # Appendektomi → A1
    "530390": 22.46,  # Subkütan enjeksiyon → E
    "620462": 5053.36,  # Labioplasti → beyond table
}


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
        lambda *args, **kwargs: katsayi,
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
    day_bed_rate_try: float | None = None,
) -> float:
    """Stub the 510010 bed-day price_try used by yatak_puani, and the 510120 day-bed price_try
    (SUT §2.2.2.(3): the bed of a stay of one date), a fifth of the bed day unless given."""
    day_bed = round(daily_rate_try / 5, 2) if day_bed_rate_try is None else day_bed_rate_try

    def _lookup(raw_code: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        code = str(raw_code or "").strip()
        if code == "510010":
            return {"entry": {"code": code, "price_try": daily_rate_try, "puan": 374.97}}
        if code == "510120":
            return {"entry": {"code": code, "price_try": day_bed, "puan": 74.96}}
        return {"entry": None}

    monkeypatch.setattr(
        "src.bilun.domain.prose_rules.yatak_puani.lookup_procedure_code",
        _lookup,
    )
    return daily_rate_try
