"""Unit tests for SUT prose coverage matrix (Phase 2)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.sut.prose.classify import classify_clause_row, classify_clauses
from scripts.sut.prose.coverage import build_sut_coverage, build_registry_coverage_summary
from scripts.sut.prose.rule_registry import RULE_BY_ID

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLAUSES_PATH = _REPO_ROOT / "data" / "gazette" / "sut_clauses.parquet"


def _sample_row(**overrides: object) -> pd.Series:
    base = {
        "clause_id": "C000001",
        "section_id": "1.8.2",
        "section_path": "1.8/1.8.2",
        "section_title": "Katılım payı",
        "annex_refs": "[]",
        "text_tr": "(1) Kurumca bedeli karşılanan ilaçlar için %10 ve %20 katılım payı alınır.",
        "deontic_modality": "COPAY_REQUIRED",
        "clause_type": "fikra",
    }
    base.update(overrides)
    return pd.Series(base)


class TestClassify:
    def test_copay_general_match(self) -> None:
        result = classify_clause_row(_sample_row())
        assert result["primary_rule_id"] == "copay_rate_general"

    def test_ek1a_annex_match(self) -> None:
        row = _sample_row(
            section_id="1.8.5",
            section_path="1.8/1.8.5",
            annex_refs='["EK-1/A"]',
            text_tr="EK-1/A listesinde yer alan kronik hastalıklarda katılım payı alınmaz.",
            deontic_modality="NO_COPAY",
        )
        result = classify_clause_row(row)
        assert "copay_exemption_ek1a" in json.loads(result["matched_rule_ids"])

    def test_payment_method_package(self) -> None:
        row = _sample_row(
            section_id="2.2.1.B-1",
            section_path="2.2/2.2.1/2.2.1.B-1",
            annex_refs='["EK-2/C"]',
            text_tr="EK-2/C Listesinde yer alması halinde tanıya dayalı işlem üzerinden faturalandırılır.",
            deontic_modality="MUST_BILL",
        )
        result = classify_clause_row(row)
        assert result["primary_rule_id"] == "payment_method_package"

    def test_tier_override_rule_classifies(self) -> None:
        row = _sample_row(
            section_id="2.2.2",
            section_path="2.2/2.2.2",
            annex_refs='["EK-2/B", "EK-2/C"]',
            text_tr=(
                "Üçüncü basamak sağlık kurumları; SUT eki EK-2/C Listesinde yanında "
                "(*) işareti bulunmayan işlemleri SUT eki EK-2/B Listesinden de "
                "faturalandırabilir."
            ),
            deontic_modality="MAY_BILL",
        )
        result = classify_clause_row(row)
        matched = json.loads(result["matched_rule_ids"])
        assert "payment_method_tier_override" in matched


    def test_procedure_pairing_section_match(self) -> None:
        row = _sample_row(
            section_id="2.2.2.A.(5)",
            section_path="2.2/2.2.2/2.2.2.A.(5)",
            annex_refs='["EK-2/B"]',
            text_tr="Aynı seansta kolonoskopik polipektomi ilave ücret ile faturalandırılır.",
            deontic_modality="MAY_BILL",
        )
        result = classify_clause_row(row)
        matched = json.loads(result["matched_rule_ids"])
        assert "procedure_pairing" in matched

    def test_material_pairing_section_match(self) -> None:
        row = _sample_row(
            section_id="3.1.1",
            section_path="3.1/3.1.1",
            annex_refs='["EK-3/C"]',
            text_tr="Malzeme ayrıca faturalandırılabilir.",
            deontic_modality="MAY_BILL",
        )
        result = classify_clause_row(row)
        matched = json.loads(result["matched_rule_ids"])
        assert "material_pairing" in matched

    def test_drg_package_adequacy_section_match(self) -> None:
        row = _sample_row(
            section_id="2.2.1.B-1.a",
            section_path="2.2/2.2.1/2.2.1.B-1.a",
            annex_refs='["EK-2/C"]',
            text_tr="609270 paket kodu tanıya dayalı işlem paketi olarak faturalandırılır.",
            deontic_modality="MUST_BILL",
        )
        result = classify_clause_row(row)
        matched = json.loads(result["matched_rule_ids"])
        assert "drg_package_adequacy" in matched

    def test_gazette_repricing_keyword_match(self) -> None:
        row = _sample_row(
            section_id="1.1",
            section_path="1.1",
            annex_refs='["EK-2/B"]',
            text_tr="Bu tebliğ yürürlük tarihinden sonra yeniden faturalandırılabilir.",
            deontic_modality="MAY_BILL",
        )
        result = classify_clause_row(row)
        matched = json.loads(result["matched_rule_ids"])
        assert "gazette_repricing" in matched

    def test_gazette_repricing_skips_generic_yururluk(self) -> None:
        row = _sample_row(
            section_id="2.2.1",
            section_path="2.2/2.2.1",
            text_tr="(1) Bu hüküm yürürlük tarihinde uygulanır.",
            deontic_modality="MUST_BILL",
        )
        result = classify_clause_row(row)
        matched = json.loads(result["matched_rule_ids"])
        assert "gazette_repricing" not in matched

    def test_bogus_section_path_does_not_match_copay(self) -> None:
        row = _sample_row(
            section_id="1",
            section_path="1",
            text_tr="1) Bünyesinde birinci basamak sağlık hizmeti sunan kurum.",
            deontic_modality="MUST_BILL",
        )
        result = classify_clause_row(row)
        assert result["primary_rule_id"] != "copay_rate_general"

    def test_copay_exemption_ek4d_annex_match(self) -> None:
        row = _sample_row(
            section_id="1.8.2",
            section_path="1.8/1.8.2",
            annex_refs='["EK-4/D"]',
            text_tr="EK-4/D listesindeki ilaçlar katılım payından muaftır.",
            deontic_modality="NO_COPAY",
        )
        result = classify_clause_row(row)
        matched = json.loads(result["matched_rule_ids"])
        assert "copay_exemption_ek4d" in matched
        assert result["primary_rule_id"] == "copay_exemption_ek4d"

    def test_medula_rejection_playbook_section_match(self) -> None:
        row = _sample_row(
            section_id="1.7.2",
            section_path="1.7/1.7.2",
            text_tr="MEDULA sistemi üzerinden provizyon alınır.",
            deontic_modality="MUST_BILL",
        )
        result = classify_clause_row(row)
        matched = json.loads(result["matched_rule_ids"])
        assert "medula_rejection_playbook" in matched

    def test_drug_indication_prose_section_match(self) -> None:
        row = _sample_row(
            section_id="4.2.14.C",
            section_path="4.2/4.2.14/4.2.14.C",
            annex_refs='["EK-4/A"]',
            text_tr="Endikasyon ve rapor ile birlikte kullanılması halinde ödenir.",
            deontic_modality="MUST_BILL",
        )
        result = classify_clause_row(row)
        assert result["primary_rule_id"] == "drug_indication_prose"
        matched = json.loads(result["matched_rule_ids"])
        assert "drug_indication_prose" in matched


class TestCoverage:
    def test_enriches_status_from_registry(self) -> None:
        clauses = pd.DataFrame([_sample_row()])
        coverage, _, _, _ = build_sut_coverage(clauses)
        assert coverage.iloc[0]["coverage_status"] == "implemented"
        assert "billing/claim_copay.py" in coverage.iloc[0]["domain_modules"]

    def test_non_algorithmic_primary_has_no_gap(self) -> None:
        row = _sample_row(
            section_id="4.1",
            section_path="4.1",
            annex_refs='["EK-4/A"]',
            text_tr="EK-4/A listesindeki ilaçlar Kurumca karşılanır.",
            deontic_modality="MUST_BILL",
        )
        coverage, _, _, _ = build_sut_coverage(pd.DataFrame([row]))
        drug_rows = coverage[coverage["primary_rule_id"] == "drug_ek4a"]
        if not drug_rows.empty:
            assert drug_rows.iloc[0]["coverage_status"] == "non_algorithmic"
            assert drug_rows.iloc[0]["has_algorithmic_gap"] == False

    def test_billing_documents_non_algorithmic_no_gap(self) -> None:
        row = _sample_row(
            section_id="5.2.1",
            section_path="5.2/5.2.1",
            text_tr="Fatura belgelerinde zorunlu alanlar yer alır.",
            deontic_modality="MUST_BILL",
            clause_type="fikra",
        )
        coverage, _, _, _ = build_sut_coverage(pd.DataFrame([row]))
        doc_rows = coverage[coverage["primary_rule_id"] == "billing_documents"]
        assert not doc_rows.empty
        assert doc_rows.iloc[0]["coverage_status"] == "non_algorithmic"
        assert doc_rows.iloc[0]["has_algorithmic_gap"] == False

    def test_registry_summary_lists_all_rules(self) -> None:
        clauses = pd.DataFrame([_sample_row()])
        coverage, _, _, registry = build_sut_coverage(clauses)
        assert len(registry) == len(RULE_BY_ID)
        assert registry["rule_id"].nunique() == len(RULE_BY_ID)


@pytest.mark.skipif(not _CLAUSES_PATH.exists(), reason="sut_clauses.parquet not present")
class TestFullCoverageBuild:
    @pytest.fixture(scope="class")
    def coverage(self) -> pd.DataFrame:
        clauses = pd.read_parquet(_CLAUSES_PATH)
        coverage, _, _, _ = build_sut_coverage(clauses)
        return coverage

    def test_majority_classified(self, coverage: pd.DataFrame) -> None:
        assert coverage["is_classified"].mean() > 0.7

    def test_implemented_rules_present(self, coverage: pd.DataFrame) -> None:
        assert (coverage["coverage_status"] == "implemented").any()

    def test_gap_flags_exist(self, coverage: pd.DataFrame) -> None:
        assert coverage["has_algorithmic_gap"].sum() > 100

    def test_payment_method_implemented(self, coverage: pd.DataFrame) -> None:
        payment = coverage[coverage["primary_rule_id"] == "payment_method_package"]
        assert not payment.empty
        assert (payment["coverage_status"] == "implemented").all()
        assert payment["has_algorithmic_gap"].sum() == 0

    def test_material_bundling_prose_implemented_not_false_gap(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/material_bundling_prose.json"
        assert prose_json.is_file(), "material_bundling_prose.json must exist on disk"

        bundling = coverage[coverage["primary_rule_id"] == "material_bundling_prose"]
        assert not bundling.empty
        assert (bundling["coverage_status"] == "implemented").all()
        assert bundling["has_algorithmic_gap"].sum() == 0

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["material_bundling_prose"].coverage_status == "implemented"

    def test_specialty_materials_prose_implemented_not_false_gap(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/specialty_materials_prose.json"
        assert prose_json.is_file(), "specialty_materials_prose.json must exist on disk"

        specialty = coverage[coverage["primary_rule_id"] == "specialty_materials_prose"]
        assert not specialty.empty
        assert (specialty["coverage_status"] == "implemented").all()
        assert specialty["has_algorithmic_gap"].sum() == 0

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["specialty_materials_prose"].coverage_status == "implemented"

    def test_drg_package_adequacy_implemented_not_false_gap(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/drg_package_adequacy_prose.json"
        assert prose_json.is_file()

        rows = coverage[coverage["primary_rule_id"] == "drg_package_adequacy"]
        matched = coverage[coverage["matched_rule_ids"].str.contains("drg_package_adequacy", regex=False)]
        assert not matched.empty
        if not rows.empty:
            assert (rows["coverage_status"] == "implemented").all()
            assert rows["has_algorithmic_gap"].sum() == 0

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["drg_package_adequacy"].coverage_status == "implemented"

    def test_gazette_repricing_partial_has_mapping(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/gazette_repricing_prose.json"
        assert prose_json.is_file()

        matched = coverage[coverage["matched_rule_ids"].str.contains("gazette_repricing", regex=False)]
        assert not matched.empty
        primary = coverage[coverage["primary_rule_id"] == "gazette_repricing"]
        if not primary.empty:
            assert (primary["coverage_status"] == "partial").all()
            assert primary["has_algorithmic_gap"].all()

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["gazette_repricing"].coverage_status == "partial"

    def test_procedure_pairing_partial_has_mapping(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/procedure_pairing_prose.json"
        assert prose_json.is_file()

        matched = coverage[coverage["matched_rule_ids"].str.contains("procedure_pairing", regex=False)]
        assert not matched.empty

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["procedure_pairing"].coverage_status == "partial"

    def test_material_pairing_partial_has_mapping(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/material_pairing_uplift.json"
        assert prose_json.is_file()

        matched = coverage[coverage["matched_rule_ids"].str.contains("material_pairing", regex=False)]
        assert not matched.empty

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["material_pairing"].coverage_status == "partial"

    def test_lab_billing_extended_has_mapping(self, coverage: pd.DataFrame) -> None:
        matched = coverage[coverage["matched_rule_ids"].str.contains("lab_billing", regex=False)]
        assert not matched.empty

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        entry = RULE_BY_ID["lab_billing"]
        assert any("lab_capture_gap" in module for module in entry.domain_modules)

    def test_drug_ek4a_non_algorithmic_not_false_gap(self, coverage: pd.DataFrame) -> None:
        drug = coverage[coverage["primary_rule_id"] == "drug_ek4a"]
        assert not drug.empty
        assert (drug["coverage_status"] == "non_algorithmic").all()
        assert drug["has_algorithmic_gap"].sum() == 0

    def test_billing_documents_non_algorithmic_not_false_gap(self, coverage: pd.DataFrame) -> None:
        docs = coverage[coverage["primary_rule_id"] == "billing_documents"]
        assert not docs.empty
        assert (docs["coverage_status"] == "non_algorithmic").all()
        assert docs["has_algorithmic_gap"].sum() == 0

    def test_copay_exemption_ek4d_implemented_has_mapping(self, coverage: pd.DataFrame) -> None:
        matched = coverage[coverage["matched_rule_ids"].str.contains("copay_exemption_ek4d", regex=False)]
        assert not matched.empty

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["copay_exemption_ek4d"].coverage_status == "implemented"
        primary = coverage[coverage["primary_rule_id"] == "copay_exemption_ek4d"]
        if not primary.empty:
            assert primary["has_algorithmic_gap"].sum() == 0

    def test_medula_rejection_playbook_partial_has_mapping(self, coverage: pd.DataFrame) -> None:
        matched = coverage[coverage["matched_rule_ids"].str.contains("medula_rejection_playbook", regex=False)]
        assert not matched.empty

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["medula_rejection_playbook"].coverage_status == "partial"

    def test_drug_indication_prose_classified_partial(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/drug_indication_prose.json"
        assert prose_json.is_file()

        matched = coverage[coverage["matched_rule_ids"].str.contains("drug_indication_prose", regex=False)]
        assert not matched.empty
        primary = coverage[coverage["primary_rule_id"] == "drug_indication_prose"]
        assert not primary.empty
        assert (primary["coverage_status"] == "partial").all()
        assert primary["has_algorithmic_gap"].sum() > 0

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["drug_indication_prose"].coverage_status == "partial"

    def test_surcharge_general_implemented_not_false_gap(self, coverage: pd.DataFrame) -> None:
        rows = coverage[coverage["primary_rule_id"] == "surcharge_general"]
        assert not rows.empty
        assert (rows["coverage_status"] == "implemented").all()
        assert rows["has_algorithmic_gap"].sum() == 0

    def test_unclassified_gaps_reduced_from_tier2_baseline(self, coverage: pd.DataFrame) -> None:
        uncl = coverage[
            (coverage["primary_rule_category"] == "unclassified")
            & coverage["has_algorithmic_gap"]
        ]
        assert len(uncl) < 598

    def test_ek2c_prose_drg_locked_implemented_has_mapping(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/ek2c_prose_drg_locked_codes.json"
        assert prose_json.is_file()

        matched = coverage[coverage["matched_rule_ids"].str.contains("ek2c_prose_drg_locked", regex=False)]
        assert not matched.empty

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["ek2c_prose_drg_locked"].coverage_status == "implemented"
        primary = coverage[coverage["primary_rule_id"] == "ek2c_prose_drg_locked"]
        if not primary.empty:
            assert primary["has_algorithmic_gap"].sum() == 0

    def test_copay_rate_general_implemented_not_false_gap(self, coverage: pd.DataFrame) -> None:
        rows = coverage[coverage["primary_rule_id"] == "copay_rate_general"]
        assert not rows.empty
        assert (rows["coverage_status"] == "implemented").all()
        assert rows["has_algorithmic_gap"].sum() == 0
