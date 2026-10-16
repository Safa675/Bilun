"""EK-2/A-2 on a service date: procedures an outpatient visit bills on top of EK-2/A.

SUT §2.2.1.B-1(10) (C000581): "Ayakta tedavilerde ödeme uygulamasında, SUT eki EK-2/A-2
Listesinde yer alan işlemlerin faturalandırılmasında aşağıdaki hususlara uyulur"; its (a)
(C000582) bills such a procedure that is in EK-2/C as its package. The curated history
(scripts/sut/catalogs/outpatient_procedures.py) holds every dated version of the list; a
row applies from its list's date or the later Yürürlük date of its own marker, until the
next version or its Mülga date (800931 from 2026-04-16, 802220 until 2026-04-15).

Codes are EK-2/B codes as the list writes them (no ``P`` prefix); callers normalize.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from functools import lru_cache

import polars as pl

from ..constants import _GAZETTE_CURATED_DIR
from .validity import as_of_iso, in_force

logger = logging.getLogger("bilun.domain.loaders.ek2a2")

EK2A2_CURATED_HISTORY_PATH = (
    _GAZETTE_CURATED_DIR / "ek2a2_outpatient_additional_procedures.parquet"
)


@lru_cache(maxsize=1)
def _ek2a2_history() -> pl.DataFrame:
    if not EK2A2_CURATED_HISTORY_PATH.exists():
        logger.warning("EK-2/A-2 history not found: %s", EK2A2_CURATED_HISTORY_PATH)
        return pl.DataFrame(
            schema={"code": pl.String, "valid_from": pl.String, "valid_to": pl.String},
        )
    return pl.read_parquet(EK2A2_CURATED_HISTORY_PATH, columns=["code", "valid_from", "valid_to"])


@lru_cache(maxsize=512)
def _codes_on(day: str) -> frozenset[str]:
    return frozenset(in_force(_ek2a2_history(), day).get_column("code").to_list())


def ek2a2_codes_as_of(as_of: date | datetime | str | None = None) -> frozenset[str]:
    """The EK-2/A-2 codes in force on ``as_of`` (default today)."""
    return _codes_on(as_of_iso(as_of))
