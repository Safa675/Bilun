"""The cohort table's "Top action": the motor that carries a patient's money, on both paths.

`_get_top_action_type` reads a live report; `patient_recovery_summary_from_payload` reads a cached payload and
must name the same motor (audit finding #12). The cache keeps dataclass fields only (`json_ready`), so a payload
has none of the amounts the live path reads as properties: the second path rebuilds each block from its rows.
The showcase bills are read through the registry (`tests/fixtures/synthetic_cohort.py`): a role name and the
registry's fault record, never an id or an amount typed here.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.bilun.api.routes.billing import _serialize_billing_report
from src.bilun.cache.build_streaming import json_ready
from src.bilun.domain.billing import recovery_summary
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.recovery_summary import (
    patient_recovery_summary_entry,
    patient_recovery_summary_from_payload,
)
from src.bilun.domain.billing.types import (
    AnesteziPuaniReview,
    BillingActionReport,
    BillingStrategyRecommendation,
    IcuPuaniReview,
    RefakatciReview,
    YatakPuaniReview,
    YenidoganYatakReview,
)
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.claims.patient_context import build_bill_claim_context
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_STORIES = tuple(f"S{number}" for number in range(1, 9))
_COPAY = {
    False: {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []},
    True: {
        "exempt": True,
        "n_qualifying": 1,
        "qualifying_diagnoses": [{"code": "E03.9", "disease": "Endokrin", "range": "E00-E90"}],
    },
}
# The registry names the engine rule of a story's fault; the cohort table names the motor by this key.
_TOP_ACTION_OF_RULE = {"billing_strategy": "strategy", "procedure_capture_gap": "capture_gap"}
# The keys `_get_top_action_type` weighs, in order: `max` keeps the first of equal amounts.
_KEYS = [
    "session_uplift",
    "drg_uplift",
    "blood_uplift",
    "yatak_puani",
    "material_uplift",
    "procedure_addon_uplift",
    "strategy",
    "capture_gap",
    "package_adequacy_review",
    "medula_playbook",
    "lab",
    "copay",
    "icu_puani",
    "yenidogan_yatak",
    "refakatci",
    "anestezi_puani",
]


@pytest.fixture(scope="module")
def reports() -> dict[tuple[str, bool], BillingActionReport]:
    """The report of each showcase bill with the copay exempt and not (16 reports)."""
    dataset = load_sut_claim_dataset()
    out: dict[tuple[str, bool], BillingActionReport] = {}
    for story in _STORIES:
        role = cohort.role(f"showcase_{story}")
        ctx = build_bill_claim_context(role.patient_id, role.claim_id, dataset)
        assert ctx is not None
        for exempt in (False, True):
            out[story, exempt] = compute_patient_billing_report(
                ctx.patient_id, claim_context=ctx, copay_exemption=_COPAY[exempt]
            )
    return out


def _cache_payload(report: BillingActionReport) -> dict[str, Any]:
    """The report as the cache builder stores it (`patient_billing_report_rows`), read back from JSON text."""
    return json.loads(json.dumps(json_ready(report)))


def _api_payload(report: BillingActionReport) -> dict[str, Any]:
    """The report as the billing endpoint serializes a live report."""
    return json.loads(json.dumps(_serialize_billing_report(report)))


def _payloads(report: BillingActionReport) -> dict[str, dict[str, Any]]:
    return {"cache": _cache_payload(report), "api": _api_payload(report)}


def _both_paths(report: BillingActionReport) -> dict[str, str]:
    """top_action_type of the live report and of both payload shapes."""
    out = {"live": patient_recovery_summary_entry(report)["top_action_type"]}
    for shape, payload in _payloads(report).items():
        out[shape] = patient_recovery_summary_from_payload(payload)["top_action_type"]
    return out


class TestShowcaseBills:
    @pytest.mark.parametrize("exempt", [False, True])
    @pytest.mark.parametrize("story", _STORIES)
    def test_the_top_action_is_the_motor_of_the_registry_fault(
        self, reports, story: str, exempt: bool
    ) -> None:
        fault = cohort.fault(story)
        if fault["effect_kind"] == "revenue_uplift":
            expected = _TOP_ACTION_OF_RULE.get(fault["engine_rule"], fault["engine_rule"])
        else:
            expected = "none"  # over-billing and compliance faults carry no SGK uplift
        assert _both_paths(reports[story, exempt]) == {
            "live": expected,
            "cache": expected,
            "api": expected,
        }

    def test_the_anaesthesia_and_companion_stories_name_their_motors(self, reports) -> None:
        """S3 and S4 read `none` next to 928.09 and 370.50 TL recoverable before the four puan motors had a key."""
        for story, motor in (("S3", "anestezi_puani"), ("S4", "refakatci")):
            assert cohort.fault(story)["engine_rule"] == motor
            for exempt in (False, True):
                report = reports[story, exempt]
                assert report.sgk_uplift_try and report.sgk_uplift_try > 0
                assert patient_recovery_summary_entry(report)["top_action_type"] == motor

    @pytest.mark.parametrize("exempt", [False, True])
    @pytest.mark.parametrize("story", _STORIES)
    def test_cached_payload_summary_equals_the_live_summary(
        self, reports, story: str, exempt: bool
    ) -> None:
        report = reports[story, exempt]
        live = patient_recovery_summary_entry(report)
        for shape, payload in _payloads(report).items():
            assert patient_recovery_summary_from_payload(payload) == live, (story, exempt, shape)

    def test_the_cohort_has_stories_that_exercise_old_and_new_keys(self, reports) -> None:
        """The parity above is not vacuous: the cohort names a puan motor, the old strategy/yatak keys and none."""
        tops = {
            patient_recovery_summary_entry(report)["top_action_type"]
            for report in reports.values()
        }
        assert {"strategy", "yatak_puani", "anestezi_puani", "refakatci", "none"} <= tops


class TestBothPathsWeighTheSameKeys:
    def test_same_keys_in_the_same_order_with_the_same_amounts(self, reports, monkeypatch) -> None:
        """Ties in `max` go to the first key, so the order is part of the mirror; so is every amount."""
        seen: list[dict[str, float]] = []
        real = recovery_summary._top_action_type_from_savings

        def spy(savings: dict[str, float]) -> str:
            seen.append(dict(savings))
            return real(savings)

        monkeypatch.setattr(recovery_summary, "_top_action_type_from_savings", spy)
        for (story, exempt), report in reports.items():
            seen.clear()
            patient_recovery_summary_entry(report)
            for shape, payload in _payloads(report).items():
                patient_recovery_summary_from_payload(payload)
            live, *cached = seen
            assert list(live) == _KEYS, (story, exempt)
            for savings in cached:
                assert list(savings) == _KEYS, (story, exempt)
                assert savings == live, (story, exempt)

    def test_the_cache_payload_carries_no_block_amounts_so_the_rows_are_read(self, reports) -> None:
        """Why `_block_amount` rebuilds blocks: `json_ready` keeps fields, not the amount properties."""
        payload = _cache_payload(reports["S3", False])
        for block, amount in (
            ("anestezi_puani", "confirmed_anestezi_try"),
            ("refakatci", "confirmed_refakat_try"),
            ("icu_puani", "confirmed_icu_try"),
            ("yenidogan_yatak", "confirmed_yenidogan_yatak_try"),
            ("yatak_puani", "confirmed_yatak_try"),
            ("billing_strategy", "uplift_savings_try"),
            ("session_uplift", "total_uplift_try"),
        ):
            assert amount not in payload[block], (block, amount)
        assert payload["anestezi_puani"]["opportunities"], "the rows are there"
        assert patient_recovery_summary_from_payload(payload)["top_action_type"] == "anestezi_puani"

    def test_an_amount_the_payload_carries_is_used_as_it_is(self, reports) -> None:
        """Endpoint-shaped payloads carry some amounts (`_serialize_billing_report`); they were always read."""
        payload = _cache_payload(reports["S3", False])
        payload["billing_strategy"]["uplift_savings_try"] = 99999.0
        assert patient_recovery_summary_from_payload(payload)["top_action_type"] == "strategy"
        # An absent or null amount falls back to the rows.
        payload["billing_strategy"]["uplift_savings_try"] = None
        assert patient_recovery_summary_from_payload(payload)["top_action_type"] == "anestezi_puani"
        del payload["billing_strategy"]["uplift_savings_try"]
        assert patient_recovery_summary_from_payload(payload)["top_action_type"] == "anestezi_puani"


def _report(**blocks: Any) -> BillingActionReport:
    return BillingActionReport(patient_id="PT-TOP", **blocks)


# motor -> (block class, an opportunity row of the amount the block's own `confirmed_*` total reads)
_MOTORS: dict[str, tuple[type, dict[str, Any]]] = {
    "icu_puani": (IcuPuaniReview, {"recoverable_uplift_try": 125.0}),
    "yenidogan_yatak": (YenidoganYatakReview, {"expected_try": 200.0}),
    "refakatci": (RefakatciReview, {"recoverable_uplift_try": 74.1}),
    "anestezi_puani": (AnesteziPuaniReview, {"recoverable_uplift_try": 300.0}),
}


class TestTheFourPuanMotors:
    @pytest.mark.parametrize("motor", sorted(_MOTORS))
    def test_a_motor_with_counted_money_names_itself(self, motor: str) -> None:
        block_type, row = _MOTORS[motor]
        report = _report(**{motor: block_type(opportunities=[{**row, "included_in_sgk_total": True}])})
        assert _both_paths(report) == {"live": motor, "cache": motor, "api": motor}

    @pytest.mark.parametrize("motor", sorted(_MOTORS))
    def test_money_kept_out_of_the_sgk_total_names_nothing(self, motor: str) -> None:
        block_type, row = _MOTORS[motor]
        report = _report(**{motor: block_type(opportunities=[{**row, "included_in_sgk_total": False}])})
        assert _both_paths(report) == {"live": "none", "cache": "none", "api": "none"}

    @pytest.mark.parametrize("motor", sorted(_MOTORS))
    def test_a_motor_wins_only_with_the_largest_amount(self, motor: str) -> None:
        block_type, row = _MOTORS[motor]
        amount = next(iter(row.values()))

        def strategy(amount_try: float) -> BillingStrategyRecommendation:
            return BillingStrategyRecommendation(
                recommendations=[
                    {
                        "type": "optional_override",
                        "recommendation_kind": "optional_override",
                        "savings_try": amount_try,
                        "included_in_sgk_total": True,
                    }
                ]
            )

        block = block_type(opportunities=[row])
        smaller = _report(billing_strategy=strategy(amount - 1), **{motor: block})
        larger = _report(billing_strategy=strategy(amount + 1), **{motor: block})
        assert _both_paths(smaller) == {"live": motor, "cache": motor, "api": motor}
        assert _both_paths(larger) == {"live": "strategy", "cache": "strategy", "api": "strategy"}

    @pytest.mark.parametrize("motor", sorted(_MOTORS))
    def test_a_tie_goes_to_the_key_it_went_to_before(self, motor: str) -> None:
        """Adding a key must not move any patient whose top amounts are equal: the new keys come last."""
        block_type, row = _MOTORS[motor]
        amount = next(iter(row.values()))
        bed = YatakPuaniReview(opportunities=[{"recoverable_uplift_try": amount}])
        report = _report(yatak_puani=bed, **{motor: block_type(opportunities=[row])})
        assert _both_paths(report) == {"live": "yatak_puani", "cache": "yatak_puani", "api": "yatak_puani"}

    def test_a_payload_without_the_blocks_names_nothing(self) -> None:
        assert patient_recovery_summary_from_payload({"patient_id": "PT-TOP"})["top_action_type"] == "none"
        nulls = {block: None for block in ("icu_puani", "yenidogan_yatak", "refakatci", "anestezi_puani")}
        assert patient_recovery_summary_from_payload(nulls)["top_action_type"] == "none"
        rowless = {block: {"opportunities": None} for block in nulls}
        assert patient_recovery_summary_from_payload(rowless)["top_action_type"] == "none"
