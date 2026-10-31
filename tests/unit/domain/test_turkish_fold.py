"""The shared Turkish text fold."""

from __future__ import annotations

import pytest

from src.bilun.domain.turkish_fold import TurkishFold, fold_turkish

pytestmark = pytest.mark.unit


def test_the_folds_differ_where_the_callers_did() -> None:
    # The variants are kept apart on purpose; these are the differences they keep.
    assert fold_turkish("ılık", TurkishFold.ACCENTLESS) == "ılık"
    assert fold_turkish("ılık", TurkishFold.ACCENTLESS_DOTLESS_I) == "ilik"
    assert fold_turkish("Şeker", TurkishFold.DOTTED_I) == "şeker"
    assert fold_turkish("Şeker", TurkishFold.ASCII) == "seker"
    assert fold_turkish("Café", TurkishFold.ASCII) == "café"
    assert fold_turkish("Café", TurkishFold.ACCENTLESS) == "cafe"
    assert fold_turkish("İzmir", TurkishFold.LOWER) == "i̇zmir"
    assert fold_turkish("Straße", TurkishFold.CASEFOLD) == "strasse"
    assert fold_turkish("Straße", TurkishFold.LOWER) == "straße"
    assert fold_turkish(" X ", TurkishFold.LOWER) == " x "
    assert fold_turkish(" X ", TurkishFold.LOWER, strip=True) == "x"
    assert fold_turkish(None, TurkishFold.ACCENTLESS) == "none"
    assert fold_turkish("\U0001d6a4", TurkishFold.ACCENTLESS_DOTLESS_I) == "ı"
