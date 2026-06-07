"""Unit tests for MEDULA rejection playbook detector."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, MedulaRejectionEvent
from src.bilun.domain.prose_rules.medula_rejection import (
    detect_medula_rejection_playbook_entries,
    match_playbook_template,
)

pytestmark = pytest.mark.unit


def _claim() -> ClaimHeader:
    return ClaimHeader(
        claim_id="F-DEMO-001",
        patient_id="P1",
        episode_id="E1",
        claim_type="poliklinik",
        facility_tier="2_basamak_kamu",
        provider_type="Kamu",
        department="Genel",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date(2024, 7, 15),
        claim_end_date=date(2024, 7, 15),
        primary_icd10="A49.9",
        package_candidate=False,
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("100"),
        expected_denial_reason="",
        scenario_tag="medula_rejection_1688_molecular_microbiology",
    )


def _event() -> MedulaRejectionEvent:
    return MedulaRejectionEvent(
        rejection_event_id="MEDULA-F-DEMO-001-001",
        claim_id="F-DEMO-001",
        patient_id="P1",
        episode_id="E1",
        medula_stage="fatura_kayit",
        sonuc_kodu="1688",
        hata_kodu="1688",
        hata_mesaji="Moleküler mikrobiyoloji işlemi için zorunlu rapor eksik",
        rejection_timestamp=date(2024, 7, 15),
        related_procedure_code="600150",
        related_procedure_line_id="ISL-F-DEMO-001-001",
    )


class TestMedulaRejectionPlaybook:
    def test_match_playbook_template_for_1688(self) -> None:
        template = match_playbook_template(_event())
        assert template is not None
        assert template["playbook_key"] == "1688_molecular_microbiology"

    def test_detect_builds_operational_entry(self) -> None:
        entries = detect_medula_rejection_playbook_entries(_claim(), [_event()])
        assert len(entries) == 1
        row = entries[0]
        assert row["sonuc_kodu"] == "1688"
        assert row["included_in_sgk_total"] is False
        assert row["recommendation_kind"] == "corrective_rebill_template"
        assert row["rebill_permitted"] is True
        assert row["corrective_steps_tr"]
