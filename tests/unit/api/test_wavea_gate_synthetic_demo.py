"""The synthetic demo shows its draft Wave A evidence; every other provenance keeps the receipt gate."""

from __future__ import annotations

import pytest

from src.bilun.api.routes import provenance, wavea_gate

pytestmark = pytest.mark.unit

_DEMO = {"mode": "synthetic_demo", "is_synthetic": True, "label": "demo", "notice": "Demo data only."}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (_DEMO, True),
        ({"mode": "real_claims", "is_synthetic": False}, False),
        ({"mode": "unavailable", "is_synthetic": None}, False),
        ({"mode": "synthetic_demo", "is_synthetic": False}, False),
        ({"mode": "synthetic_demo", "is_synthetic": "true"}, False),
        ({"mode": "synthetic_demo"}, False),
        ({"is_synthetic": True}, False),
        ({}, False),
    ],
)
def test_only_the_synthetic_demo_provenance_serves_draft_evidence(monkeypatch, source, expected):
    monkeypatch.setattr(wavea_gate, "read_active_bilun_data_source", lambda *_a, **_k: source)
    assert wavea_gate.synthetic_demo_serves_draft_evidence(object(), "build") is expected


def test_an_unreadable_provenance_keeps_the_gate_closed(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("cache unreadable")

    monkeypatch.setattr(wavea_gate, "read_active_bilun_data_source", boom)
    assert wavea_gate.synthetic_demo_serves_draft_evidence(object(), "build") is False


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ({"data_source": _DEMO}, True),
        ({"data_source": {"mode": "real_claims", "is_synthetic": False}}, False),
        # The provenance normalizer refuses a synthetic claim that is not marked synthetic.
        ({"data_source": {"mode": "synthetic_demo", "is_synthetic": False}}, False),
        # A cache that records no provenance is not a demo cache.
        ({}, False),
        (None, False),
    ],
)
def test_the_decision_reads_the_provenance_the_reports_carry(monkeypatch, stored, expected):
    monkeypatch.setattr(provenance, "read_cache_json_payload", lambda *_a, **_k: stored)
    assert wavea_gate.synthetic_demo_serves_draft_evidence(object(), "build") is expected
