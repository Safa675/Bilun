"""Cache compatibility and mutable clinical-record regressions."""

from dataclasses import replace

import pytest

from src.bilun.domain.prose_rules import gap_closing
from tests.unit.domain.prose_rules.test_drug_indication import _drug_line
from tests.unit.domain.prose_rules.test_gap_closing_for_context import _make_ctx


@pytest.fixture(autouse=True)
def clear_builder_cache():
    gap_closing._build_gap_closing_context.cache_clear()
    yield
    gap_closing._build_gap_closing_context.cache_clear()


def test_hashable_context_reuses_cached_result_and_cache_clear():
    builder = gap_closing._build_gap_closing_context
    context = _make_ctx()
    result = builder(context)
    assert builder(replace(context)) is result
    assert builder.cache_info().hits == 1
    assert builder.cache_info().misses == builder.cache_info().currsize == 1
    assert builder.cache_parameters() == {"maxsize": None, "typed": False}

    builder.cache_clear()
    assert builder.cache_info().hits == builder.cache_info().misses == 0
    assert builder.cache_info().currsize == 0
    fresh = builder(context)
    assert fresh == result and fresh is not result


def test_wrapped_interface_still_exposes_the_uncached_original_body():
    builder = gap_closing._build_gap_closing_context
    context = _make_ctx()
    first = builder.__wrapped__(context)
    second = builder.__wrapped__(context)
    assert first == second and first is not second
    assert builder.__wrapped__ is gap_closing._build_gap_closing_context_cached.__wrapped__
    assert builder.cache_info().currsize == builder.cache_info().misses == 0


@pytest.mark.parametrize("facts", [
    {"prior_therapies": ({"drug_or_class": "imatinib", "outcome": "resistant"},)},
    {"biomarkers": ({"marker": "BCR_ABL", "status": "positive"},)},
    {
        "prior_therapies": ({"drug_or_class": "imatinib", "outcome": "intolerant"},),
        "biomarkers": ({"marker": "BCR_ABL", "status": "positive"},),
    },
], ids=["prior-therapy-dict", "biomarker-dict", "both-clinical-dicts"])
def test_nested_mutable_facts_use_the_real_builder_without_cache(facts):
    context = _make_ctx(drug_lines=(_drug_line(report_present=True, **facts),))
    with pytest.raises(TypeError, match="unhashable"):
        hash(context)
    builder = gap_closing._build_gap_closing_context
    result = builder(context)
    assert result == builder.__wrapped__(context)
    assert result["health_report_present"] is True
    assert result["care_setting"] == "outpatient"
    assert builder(context) == result
    assert builder(context) is not result
    assert builder.cache_info().hits == builder.cache_info().misses == 0
    assert builder.cache_info().currsize == 0


def test_repeated_changes_to_nested_outcomes_build_fresh_unchanged_contexts():
    prior = {"drug_or_class": "imatinib", "outcome": "unknown"}
    context = _make_ctx(drug_lines=(_drug_line(report_present=True, prior_therapies=(prior,)),))
    builder = gap_closing._build_gap_closing_context
    expected = builder.__wrapped__(context)
    previous = None
    for outcome in ("unknown", "resistant", "responsive", "intolerant"):
        prior["outcome"] = outcome
        current = builder(context)
        assert current == expected
        assert current is not previous
        previous = current
    assert builder.cache_info().currsize == builder.cache_info().misses == 0


@pytest.mark.parametrize("unhashable", [False, True])
def test_builder_type_error_propagates_once_for_both_cache_paths(monkeypatch, unhashable):
    error = TypeError("builder failure, not a cache-key failure")
    calls = []

    def fail_inside_builder(*args, **kwargs):
        calls.append((args, kwargs))
        raise error

    monkeypatch.setattr(gap_closing, "normalize_facility_tier", fail_inside_builder)
    drugs = ((_drug_line(prior_therapies=({"drug_or_class": "imatinib"},)),)
             if unhashable else ())
    with pytest.raises(TypeError) as caught:
        gap_closing._build_gap_closing_context(_make_ctx(drug_lines=drugs))
    assert caught.value is error
    assert len(calls) == 1
    assert gap_closing._build_gap_closing_context.cache_info().currsize == 0
