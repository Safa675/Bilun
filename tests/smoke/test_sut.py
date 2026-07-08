"""SUT Optimization MVP integration tests (pytest version).

Tests SUT claim validation, material pricing, and bundled consumables
for correct response shapes and business logic.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest


_SKIP_PATTERNS = (
    "legacy eager _load_pipeline",
    "Could not set lock on file",
    "bilun.duckdb",
    "cache not ready",
)


def _assert_keys(data: dict, keys: set[str] | list[str], label: str):
    missing = set(keys) - set(data.keys())
    assert not missing, f"{label}: missing keys {missing} in {list(data.keys())}"


@contextmanager
def _skip_if_unavailable():
    try:
        yield
    except Exception as exc:
        msg = str(exc)
        if any(p in msg for p in _SKIP_PATTERNS):
            pytest.skip(f"Pipeline/cache unavailable: {msg[:120]}")
        raise


def _get_json(resp):
    if hasattr(resp, "status_code") and resp.status_code != 200:
        text = resp.text if hasattr(resp, "text") else str(resp.content)
        if any(p in text for p in _SKIP_PATTERNS):
            pytest.skip("Analytics pipeline not available in TESTING mode")
        assert resp.status_code == 200, (
            f"Unexpected status {resp.status_code}: {text[:300]}"
        )
    return resp.json()


@pytest.mark.smoke
class TestSutClaimValidation:
    def test_cardiac_stent_separately_payable_per_3_1_4g(self, api_client):
        """Coronary stents are NOT bundled — per SUT §3.1.4(2)/C002801 they are
        'dâhil olmayan' (excluded from the diagnosis-based payment) and 'Kurumca
        karşılanır' (paid separately). The §3.1.4(g) rule fires and flags the
        stent at severity=info (review), not as a bundling violation/error.
        """
        with _skip_if_unavailable():
            body = {
                "claim_id": "TEST-STENT-001",
                "procedure_code": "520.021",
                "materials": [
                    {
                        "name": "STENT, KORONER, BALONA MONTE EDİLMİŞ ÇIPLAK",
                        "code": "KR1150",
                        "unit_price": 800,
                        "quantity": 1,
                    },
                ],
            }
            res = _get_json(api_client.post("/api/validate-claim", json=body))
            assert res["claim_id"] == "TEST-STENT-001"
            assert len(res["violations"]) >= 1
            assert any(v["severity"] == "info" for v in res["violations"])
            assert isinstance(res["material_lines"], list)

    def test_bundled_consumables_detected(self, api_client):
        with _skip_if_unavailable():
            body = {
                "claim_id": "TEST-BUNDLE-001",
                "procedure_code": "520.021",
                "materials": [
                    {"name": "Koroner stent", "unit_price": 800, "quantity": 1},
                    {"name": "Enjektör", "unit_price": 5, "quantity": 10},
                    {"name": "Eldiven", "unit_price": 3, "quantity": 20},
                ],
            }
            res = _get_json(api_client.post("/api/validate-claim", json=body))
            assert res["claim_id"] == "TEST-BUNDLE-001"
            assert len(res["violations"]) >= 1
            assert any(v["severity"] in ("warning", "error") for v in res["violations"])
            assert res["total_savings_try"] > 0 or res["total_risk_try"] > 0

    def test_empty_materials(self, api_client):
        with _skip_if_unavailable():
            body = {
                "claim_id": "TEST-EMPTY-001",
                "procedure_code": "GENERIC",
                "materials": [],
            }
            res = _get_json(api_client.post("/api/validate-claim", json=body))
            assert res["is_valid"] is True
            assert len(res["violations"]) == 0

    def test_full_response_shape(self, api_client):
        with _skip_if_unavailable():
            body = {
                "claim_id": "TEST-SHAPE-001",
                "procedure_code": "520.021",
                "materials": [
                    {"name": "Bistüri", "unit_price": 15, "quantity": 5},
                ],
            }
            res = _get_json(api_client.post("/api/validate-claim", json=body))
            _assert_keys(
                res,
                {
                    "claim_id",
                    "is_valid",
                    "total_claim_amount",
                    "total_savings_try",
                    "total_risk_try",
                    "n_bundling_violations",
                    "n_exclusion_violations",
                    "validation_time_ms",
                    "summary",
                    "violations",
                    "material_lines",
                },
                "validate-claim shape",
            )
            assert isinstance(res["validation_time_ms"], (int, float))

    def test_material_estimate_fields(self, api_client):
        with _skip_if_unavailable():
            body = {
                "claim_id": "TEST-FIELDS-001",
                "procedure_code": "520.021",
                "materials": [
                    {
                        "name": "Koroner stent",
                        "unit_price": 800,
                        "quantity": 1,
                        "code": "090301",
                    },
                ],
            }
            res = _get_json(api_client.post("/api/validate-claim", json=body))
            if len(res["material_lines"]) > 0:
                line = res["material_lines"][0]
                _assert_keys(
                    line,
                    {
                        "material_code",
                        "material_name",
                        "unit_price",
                        "quantity",
                        "total_price",
                        "is_reimbursable",
                        "is_bundled",
                        "source",
                        "exactness_status",
                        "notes",
                    },
                    "material line",
                )


@pytest.mark.smoke
class TestSutMaterialPricing:
    def test_search_stent(self, api_client):
        with _skip_if_unavailable():
            res = _get_json(api_client.get("/api/material/stent/pricing"))
            assert res["n_matches"] > 0
            assert isinstance(res["materials"], list)
            first = res["materials"][0]
            assert "material_name" in first
            assert "price_try" in first

    def test_search_nonexistent(self, api_client):
        with _skip_if_unavailable():
            res = _get_json(
                api_client.get("/api/material/zzz_no_such_item/pricing")
            )
            assert res["n_matches"] == 0
            assert len(res["materials"]) == 0

    def test_search_by_code(self, api_client):
        with _skip_if_unavailable():
            res = _get_json(api_client.get("/api/material/0903/pricing"))
            assert isinstance(res["materials"], list)
            assert "n_matches" in res
            assert "query" in res


@pytest.mark.smoke
class TestSutBundledConsumables:
    def test_loads_catalog(self, api_client):
        with _skip_if_unavailable():
            res = _get_json(api_client.get("/api/bundled-consumables"))
            bc = res["bundled_consumables"]
            ec = res["exclusion_categories"]
            assert bc["count"] > 0
            assert ec["count"] > 0
            assert isinstance(bc["items"], list)
            assert isinstance(ec["categories"], list)
            assert "item_name" in bc["items"][0]

    def test_count_matches_items_length(self, api_client):
        with _skip_if_unavailable():
            res = _get_json(api_client.get("/api/bundled-consumables"))
            bc = res["bundled_consumables"]
            assert bc["count"] == len(bc["items"])
            ec = res["exclusion_categories"]
            assert ec["count"] == len(ec["categories"])
