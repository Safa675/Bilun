"""Synthetic material line L4.4 specialty prose flags."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SYNTHETIC_DIR = Path(__file__).resolve().parents[3] / "scripts" / "synthetic"
if str(SYNTHETIC_DIR) not in sys.path:
    sys.path.insert(0, str(SYNTHETIC_DIR))

from generators import (  # noqa: E402
    SPECIALTY_PROSE_FLAG_COLUMNS,
    build_workbook_tables,
)


def test_material_lines_include_specialty_flag_columns() -> None:
    tables = build_workbook_tables(num_patients=10, seed=20260611)
    materials = tables["malzeme_fatura_satirlari"]
    assert not materials.empty

    for col in SPECIALTY_PROSE_FLAG_COLUMNS:
        assert col in materials.columns


def test_material_lines_cover_each_specialty_flag_demo_row() -> None:
    tables = build_workbook_tables(num_patients=10, seed=20260611)
    materials = tables["malzeme_fatura_satirlari"]

    # Duplicate-billing flags are context-gated (require a co-material on the
    # same claim). They may legitimately have zero rows when no qualifying
    # co-material exists in a small cohort — demanding coverage would force a
    # false-positive match. Mirrors the validator exemption.
    context_gated = frozenset(
        {
            "wheelchair_stand_device_duplicate_billing",
            "spinal_mobility_device_duplicate_billing",
            "nimv_heated_humidifier_separate_billing",
        }
    )

    for col in SPECIALTY_PROSE_FLAG_COLUMNS:
        if col in context_gated:
            continue
        assert materials[col].astype(bool).any(), f"missing demo row for {col}"


def test_keyword_demo_material_names_present() -> None:
    tables = build_workbook_tables(num_patients=10, seed=20260611)
    names = set(tables["malzeme_fatura_satirlari"]["malzeme_adi"].astype(str))
    assert "Transparan film yara örtüsü" in names
    assert "Kontakt lens solüsyonu" in names
