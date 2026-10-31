"""The shared ICD-10 matcher."""

from __future__ import annotations

import pytest

from src.bilun.domain.icd10 import (
    Icd10Cover,
    icd10_any_code_covered,
    icd10_covers,
    normalize_icd10,
    normalize_icd10_list,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("listed", "code", "exact", "leaves"),
    [
        ("M45", "M45", True, True),
        ("M45", "M45.9", True, True),
        ("M45", "M45.90", True, True),
        ("M45", "M450", False, False),
        ("M08.0", "M08.01", False, True),
        ("M08.0", "M08.0.1", True, True),
        ("M08.0", "M08.1", False, False),
        ("M08.0", "M08", False, False),
        ("E75.21", "E75.2", False, False),
        ("", "M45", False, False),
        ("", ".5", True, True),
    ],
)
def test_icd10_covers_by_reading(listed: str, code: str, exact: bool, leaves: bool) -> None:
    assert icd10_covers(listed, code, cover=Icd10Cover.EXACT) is exact
    assert icd10_covers(listed, code, cover=Icd10Cover.LEAVES) is leaves


def test_normalisation_and_any_code() -> None:
    assert normalize_icd10(None) == normalize_icd10("") == ""
    assert normalize_icd10(" m45.9 ") == "M45.9"
    assert normalize_icd10_list([" k50 ", None, "", " ", 0]) == ["K50", ""]
    assert normalize_icd10_list(None) == []
    assert icd10_any_code_covered([None, " ", " m45.9"], ["M45"], cover=Icd10Cover.EXACT) is True
    assert icd10_any_code_covered(None, ["M45"], cover=Icd10Cover.EXACT) is False
    assert icd10_any_code_covered(["M08.01"], ["M08.0"], cover=Icd10Cover.EXACT) is False
    assert icd10_any_code_covered(["M08.01"], ["M08.0"], cover=Icd10Cover.LEAVES) is True
