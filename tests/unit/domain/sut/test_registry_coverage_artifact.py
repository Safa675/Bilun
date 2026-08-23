"""Pin the committed SUT registry coverage parquet to the live RULE_REGISTRY.

A registry entry without a row in ``sut_registry_coverage.parquet`` renders as
"⚠ 0 hüküm" in Kural Veritabanı. If this test fails after adding a rule to
RULE_REGISTRY, run ``python scripts/sut/build_sut_coverage.py`` and commit the
regenerated parquet set.
"""

from __future__ import annotations

import polars as pl
import pytest

from src.bilun.domain.constants import SUT_REGISTRY_COVERAGE_PATH
from src.bilun.domain.sut import rules_catalog as rc
from src.bilun.domain.sut.rule_registry import RULE_BY_ID


@pytest.fixture(autouse=True)
def _clear_cache():
    rc.reset_cache()
    yield
    rc.reset_cache()


def _load_registry_coverage() -> pl.DataFrame:
    if not SUT_REGISTRY_COVERAGE_PATH.exists():
        pytest.fail(
            "sut_registry_coverage.parquet is missing; run "
            "`python scripts/sut/build_sut_coverage.py` and commit the output."
        )
    return pl.read_parquet(SUT_REGISTRY_COVERAGE_PATH)


class TestRegistryCoverageArtifact:
    def test_parquet_rule_ids_match_registry_exactly(self) -> None:
        frame = _load_registry_coverage()
        parquet_ids = set(frame["rule_id"].to_list())
        registry_ids = set(RULE_BY_ID)
        assert parquet_ids == registry_ids, (
            "sut_registry_coverage.parquet is out of sync with RULE_REGISTRY: "
            f"missing={sorted(registry_ids - parquet_ids)} "
            f"extra={sorted(parquet_ids - registry_ids)}"
        )

    @pytest.mark.parametrize(
        "rule_id",
        ["blood_component_isbt128_barcode", "yatak_icu_overlap"],
    )
    def test_recent_engines_carry_clause_mappings(self, rule_id: str) -> None:
        frame = _load_registry_coverage()
        rows = frame.filter(pl.col("rule_id") == rule_id)
        assert rows.height == 1, f"expected exactly one row for {rule_id}"
        assert rows["matched_clause_count"][0] > 0, (
            f"{rule_id} has a registry row but no matched SUT clauses; "
            "a no-op row insert cannot satisfy this pin"
        )
