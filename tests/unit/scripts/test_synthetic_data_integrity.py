"""Synthetic claim-line accounting invariants for copay/surcharge decomposition."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SYNTHETIC_DIR = Path(__file__).resolve().parents[3] / "scripts" / "synthetic"
if str(SYNTHETIC_DIR) not in sys.path:
    sys.path.insert(0, str(SYNTHETIC_DIR))

from generators import build_workbook_tables  # noqa: E402


def _line_identity_holds(
    *,
    billed: float,
    expected_payable: float,
    copay_rate: float | None,
    surcharge_rate: float | None,
    tolerance: float = 0.10,
) -> bool:
    if surcharge_rate is not None and math.isnan(surcharge_rate):
        surcharge_rate = None
    if billed <= 0:
        return True
    if copay_rate is None:
        return True

    denominator = 1.0 - copay_rate
    if denominator <= 0:
        return False
    sgk_base = expected_payable / denominator
    patient_copay = sgk_base * copay_rate
    surcharge = sgk_base * (surcharge_rate or 0.0)
    at_risk_total = billed - expected_payable
    return abs(at_risk_total - (patient_copay + surcharge)) <= tolerance


def test_procedure_and_drug_line_identity() -> None:
    tables = build_workbook_tables(num_patients=15, seed=20260504)
    procedures = tables["islem_fatura_satirlari"]
    drugs = tables["ilac_fatura_satirlari"]

    assert not procedures.empty
    assert not drugs.empty

    proc_with_rate = procedures[procedures["katilim_payi_orani"].notna()]
    assert not proc_with_rate.empty
    # Exclude deliberate EK-2C-1 "copay not applied" violation demo rows: the
    # generator intentionally flags copay_applicable yet sets payable == billed
    # so the optimizer can surface the missed copay. These rows are designed to
    # violate the decomposition invariant and must be skipped here.
    copay_not_applied = (
        procedures["katilim_payi_orani_uygulanabilir_mi"]
        & (procedures["fatura_tutari_try"] == procedures["beklenen_odenebilir_tutar_try"])
    )
    proc_with_rate = proc_with_rate[~copay_not_applied.loc[proc_with_rate.index]]
    for row in proc_with_rate.itertuples(index=False):
        assert _line_identity_holds(
            billed=float(row.fatura_tutari_try),
            expected_payable=float(row.beklenen_odenebilir_tutar_try),
            copay_rate=float(row.katilim_payi_orani),
            surcharge_rate=(
                float(row.ilave_ucret_orani) if row.ilave_ucret_orani is not None else None
            ),
        )

    drug_with_rate = drugs[drugs["katilim_payi_orani"].notna()]
    assert not drug_with_rate.empty
    for row in drug_with_rate.itertuples(index=False):
        assert _line_identity_holds(
            billed=float(row.fatura_tutari_try),
            expected_payable=float(row.beklenen_odenebilir_tutar_try),
            copay_rate=float(row.katilim_payi_orani),
            surcharge_rate=None,
        )
