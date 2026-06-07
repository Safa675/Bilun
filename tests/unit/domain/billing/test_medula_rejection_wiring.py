"""Wiring tests for MEDULA rejection playbook billing block."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.billing.claim_medula_rejection import (
    recommend_medula_rejection_playbook_from_claims,
)
from src.bilun.domain.billing.types import EXACTNESS_STATUS_EXACT, EXACTNESS_STATUS_NOT_APPLICABLE
from src.bilun.domain.claims.models import ClaimHeader, MedulaRejectionEvent
from src.bilun.domain.claims.patient_context import PatientClaimContext


def _ctx(*, with_events: bool = True) -> PatientClaimContext:
    claim = ClaimHeader(
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
    events = ()
    if with_events:
        events = (
            MedulaRejectionEvent(
                rejection_event_id="MEDULA-F-DEMO-001-001",
                claim_id="F-DEMO-001",
                patient_id="P1",
                episode_id="E1",
                medula_stage="fatura_kayit",
                sonuc_kodu="1688",
                hata_kodu="1688",
                hata_mesaji="Moleküler mikrobiyoloji işlemi için zorunlu rapor eksik",
                rejection_timestamp=date(2024, 7, 15),
            ),
        )
    return PatientClaimContext(
        patient_id="P1",
        claims=(claim,),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
        medula_rejection_events=events,
    )


class TestMedulaRejectionWiring:
    def test_missing_events_returns_not_applicable(self) -> None:
        block = recommend_medula_rejection_playbook_from_claims(_ctx(with_events=False))
        assert block.exactness_status == EXACTNESS_STATUS_NOT_APPLICABLE
        assert block.entry_count == 0

    def test_recommend_returns_playbook_entry(self) -> None:
        block = recommend_medula_rejection_playbook_from_claims(_ctx())
        assert block.exactness_status == EXACTNESS_STATUS_EXACT
        assert block.entry_count == 1
        assert block.entries[0]["sonuc_kodu"] == "1688"
        assert block.rebill_permitted_count == 1
