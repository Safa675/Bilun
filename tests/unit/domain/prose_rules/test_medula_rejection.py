"""Unit tests for MEDULA rejection playbook detector."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, MedulaRejectionEvent
from src.bilun.domain.constants import _DATA_DIR
from src.bilun.domain.prose_rules.medula_rejection import (
    detect_medula_rejection_playbook_entries,
    load_medula_rejection_playbook,
    match_playbook_template,
)

pytestmark = pytest.mark.unit


def _claim(scenario_tag: str = "medula_rejection_1688_molecular_microbiology") -> ClaimHeader:
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
        scenario_tag=scenario_tag,
    )


def _event(
    *,
    sonuc_kodu: str = "1688",
    hata_mesaji: str = "Moleküler mikrobiyoloji işlemi için zorunlu rapor eksik",
    medula_stage: str = "fatura_kayit",
) -> MedulaRejectionEvent:
    return MedulaRejectionEvent(
        rejection_event_id="MEDULA-F-DEMO-001-001",
        claim_id="F-DEMO-001",
        patient_id="P1",
        episode_id="E1",
        medula_stage=medula_stage,
        sonuc_kodu=sonuc_kodu,
        hata_kodu=sonuc_kodu,
        hata_mesaji=hata_mesaji,
        rejection_timestamp=date(2024, 7, 15),
        related_procedure_code="600150",
        related_procedure_line_id="ISL-F-DEMO-001-001",
        related_line_type="procedure",
        related_line_id="ISL-F-DEMO-001-001",
    )


class TestMedulaRejectionPlaybookCorpus:
    def test_playbook_has_top_ten_templates(self) -> None:
        playbook = load_medula_rejection_playbook()
        assert len(playbook.get("entries", [])) >= 10
        assert playbook.get("version") == 2

    def test_golden_top10_playbook_keys(self) -> None:
        golden_path = _DATA_DIR / "medula" / "golden" / "rejection_playbook_top10.json"
        payload = json.loads(golden_path.read_text(encoding="utf-8"))
        playbook = load_medula_rejection_playbook()
        keys_by_code = {
            str(entry["sonuc_kodu"]): entry["playbook_key"]
            for entry in playbook.get("entries", [])
        }
        for case in payload["cases"]:
            assert keys_by_code.get(case["sonuc_kodu"]) == case["playbook_key"]

    def test_playbook_json_matches_loader(self) -> None:
        path = _DATA_DIR / "medula" / "rejection_playbook.json"
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
        assert load_medula_rejection_playbook() == raw


class TestMedulaRejectionPlaybook:
    def test_match_playbook_template_for_1688(self) -> None:
        template = match_playbook_template(_event())
        assert template is not None
        assert template["playbook_key"] == "1688_molecular_microbiology"

    @pytest.mark.parametrize(
        ("sonuc_kodu", "hata_mesaji", "expected_key"),
        [
            (
                "0612",
                "Uzmanlık sağlık kurulu raporu eksik",
                "0612_board_report_missing",
            ),
            (
                "1205",
                "Hizmet tarihi uyumsuz — provizyon ile eşleşmiyor",
                "1205_service_date_mismatch",
            ),
            (
                "0521",
                "Provizyon onay alınmamış",
                "0521_provision_not_obtained",
            ),
            (
                "0315",
                "Branş uyumsuz — uzmanlık bilgisi hatalı",
                "0315_specialty_mismatch",
            ),
            (
                "0901",
                "Mükerrer işlem — aynı gün tekrar faturalandırılamaz",
                "0901_duplicate_procedure",
            ),
            (
                "0704",
                "Malzeme ÜTS barkod kaydı eksik veya geçersiz",
                "0704_uts_barcode_missing",
            ),
            (
                "0320",
                "Paket kapsamındaki işlem ayrı faturalandırılamaz",
                "0320_package_bundled_procedure",
            ),
            (
                "0411",
                "İlaç endikasyon raporu eksik — sağlık kurulu onayı gerekli",
                "0411_drug_report_missing",
            ),
            (
                "1102",
                "Sözleşmesiz kurum — SGK anlaşması bulunamadı",
                "1102_uncontracted_facility",
            ),
        ],
    )
    def test_match_playbook_template_for_expanded_codes(
        self,
        sonuc_kodu: str,
        hata_mesaji: str,
        expected_key: str,
    ) -> None:
        template = match_playbook_template(
            _event(sonuc_kodu=sonuc_kodu, hata_mesaji=hata_mesaji)
        )
        assert template is not None
        assert template["playbook_key"] == expected_key

    def test_detect_builds_operational_entry(self) -> None:
        entries = detect_medula_rejection_playbook_entries(_claim(), [_event()])
        assert len(entries) == 1
        row = entries[0]
        assert row["sonuc_kodu"] == "1688"
        assert row["included_in_sgk_total"] is False
        assert row["recommendation_kind"] == "corrective_rebill_template"
        assert row["rebill_permitted"] is True
        assert row["corrective_steps_tr"]

    def test_unmatched_event_is_skipped(self) -> None:
        unknown = _event(sonuc_kodu="9999", hata_mesaji="Bilinmeyen red")
        entries = detect_medula_rejection_playbook_entries(_claim(), [unknown])
        assert entries == []
