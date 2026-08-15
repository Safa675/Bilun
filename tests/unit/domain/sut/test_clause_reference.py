"""Track E clause reference contract: clause_key resolution + provenance."""

from __future__ import annotations

import concurrent.futures

from src.bilun.domain.sut import clause_reference, rules_catalog
from src.bilun.domain.sut.clause_reference import (
    SOURCE_ALGORITMA_REHBERI,
    SOURCE_EL_KITABI,
    SutClauseReference,
    non_sut_reference,
    resolve_clause_key,
    sut_clause_reference,
)


def test_resolve_clause_key_known_coordinate() -> None:
    key = resolve_clause_key("1.1")
    assert key is not None
    assert "#" in key or key  # coord#hash preferred; bare hash tolerated


def test_resolve_clause_key_unknown_coordinate_returns_none() -> None:
    assert resolve_clause_key("99.99.99.(99)") is None


def test_resolve_clause_key_ambiguous_coordinate_uses_section_heading() -> None:
    # "1.9.1" is shared by the section heading and in-force amendment-marker
    # rows; the cite must resolve to the heading row, not fail.
    key = resolve_clause_key("1.9.1")
    assert key is not None
    assert key.startswith("1.9.1#")


def test_resolve_clause_key_empty_returns_none() -> None:
    assert resolve_clause_key("") is None
    assert resolve_clause_key("   ") is None


def test_sut_clause_reference_resolves_key() -> None:
    ref = sut_clause_reference("1.1", rule_type="COPAY_WAIVER", annex="EK-1/A")
    assert isinstance(ref, SutClauseReference)
    assert ref.clause_coordinate == "1.1"
    assert ref.source_type == "sut_clause"
    assert ref.rule_type == "COPAY_WAIVER"
    assert ref.annex == "EK-1/A"


def test_sut_clause_reference_unknown_coordinate_keeps_cite() -> None:
    ref = sut_clause_reference("99.99.99.(99)")
    assert ref.clause_key == ""
    assert ref.clause_coordinate == "99.99.99.(99)"


def test_non_sut_reference_carries_provenance_not_clause_key() -> None:
    ref = non_sut_reference(
        "El Kitabı Tablo 15",
        source_type=SOURCE_EL_KITABI,
    )
    assert ref.clause_key == ""
    assert ref.source_type == "el_kitabi"

    trafik = non_sut_reference(
        "Algoritma Rehberi §2-09",
        source_type=SOURCE_ALGORITMA_REHBERI,
        statutory_law="2918 Sayılı Kanun Madde 98",
    )
    assert trafik.statutory_law == "2918 Sayılı Kanun Madde 98"


def test_to_dict_round_shape() -> None:
    ref = sut_clause_reference("1.1")
    row = ref.to_dict()
    assert set(row) == {
        "clause_key",
        "clause_coordinate",
        "source_type",
        "rule_type",
        "annex",
        "statutory_law",
    }


def test_concurrent_first_resolution_never_caches_empty_key(monkeypatch) -> None:
    """Regression: cohort reports resolve clause refs from a ThreadPoolExecutor.

    A worker racing the initial coverage load previously observed a
    half-initialized cache and the resolver memoized the empty clause_key
    forever. With fresh module state, every concurrent first resolution of the
    same coordinate must yield the real key.
    """
    monkeypatch.setattr(clause_reference, "_RESOLVED_KEY_CACHE", {})
    monkeypatch.setattr(rules_catalog, "_coverage_cache", None, raising=False)
    monkeypatch.setattr(rules_catalog, "_coverage_loaded", False, raising=False)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _: resolve_clause_key("1.8.5.(8)"), range(64))
        )

    assert all(key == "1.8.5.(8)#2c30921a" for key in results), results
