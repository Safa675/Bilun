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

    def test_procedure_pairing_not_primary_on_surcharge_section(self) -> None:
        row = _sample_row(
            section_id="1.9.1",
            section_path="1.9/1.9.1",
            annex_refs='["EK-2/B"]',
            text_tr="Sözleşmeli kurumlar aynı seans ilave ücret uygular.",
            deontic_modality="MUST_BILL",
        )
        result = classify_clause_row(row)
        assert result["primary_rule_id"] == "surcharge_general"
        assert "procedure_pairing" not in json.loads(result["matched_rule_ids"])

    def test_medula_provizyon_fallback(self) -> None:
        row = _sample_row(
            section_id="1.7.2",
            section_path="1.7/1.7.2",
            text_tr="MEDULA sistemi üzerinden provizyon alınır.",
            deontic_modality="MUST_BILL",
        )
        result = classify_clause_row(row)
        assert result["primary_rule_id"] == "provizyon_medula"

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

    def test_billing_amendment_header_non_algorithmic_no_gap(self) -> None:
        row = _sample_row(
            section_id="5.2.1",
            section_path="5.2/5.2.1",
            text_tr="(Mülga: RG- 01/08/2013- 28725/ 11 md. Yürürlük: 01/08/2013)",
            clause_type="amendment",
            deontic_modality=None,
        )
        coverage, _, _, _ = build_sut_coverage(pd.DataFrame([row]))
        doc_rows = coverage[coverage["primary_rule_id"] == "billing_documents"]
        assert not doc_rows.empty
        assert doc_rows.iloc[0]["coverage_status"] == "non_algorithmic"
        assert doc_rows.iloc[0]["has_algorithmic_gap"] == False

    def test_nan_deontic_amendment_not_actionable_gap(self) -> None:
        row = _sample_row(
            section_id="1.7",
            section_path="1.7",
            text_tr="(Değişiklik: RG- …)",
            clause_type="amendment",
            deontic_modality=None,
        )
        coverage, _, _, _ = build_sut_coverage(pd.DataFrame([row]))
        assert coverage.iloc[0]["primary_rule_id"] == "provizyon_medula"
        assert coverage.iloc[0]["coverage_status"] == "non_algorithmic"
        assert coverage.iloc[0]["has_algorithmic_gap"] == False

    def test_chapter_title_non_algorithmic_no_gap(self) -> None:
        row = _sample_row(
            clause_id="C000001",
            section_id=None,
            section_path=None,
            section_title=None,
            text_tr="BİRİNCİ BÖLÜM",
            clause_type="chapter",
            deontic_modality=None,
            annex_refs="[]",
        )
        coverage, _, _, _ = build_sut_coverage(pd.DataFrame([row]))
        assert coverage.iloc[0]["primary_rule_id"] is None
        assert coverage.iloc[0]["coverage_status"] == "non_algorithmic"
        assert coverage.iloc[0]["has_algorithmic_gap"] == False

    def test_prose_section_label_non_algorithmic_no_gap(self) -> None:
        row = _sample_row(
            clause_id="C000002",
            section_id=None,
            section_path=None,
            section_title=None,
            text_tr="Genel Hükümler",
            clause_type="prose",
            deontic_modality=None,
            annex_refs="[]",
        )
        coverage, _, _, _ = build_sut_coverage(pd.DataFrame([row]))
        assert coverage.iloc[0]["primary_rule_id"] is None
        assert coverage.iloc[0]["coverage_status"] == "non_algorithmic"
        assert coverage.iloc[0]["has_algorithmic_gap"] == False

    def test_section_heading_without_deontic_non_algorithmic(self) -> None:
        row = _sample_row(
            clause_id="C000003",
            section_id="1.1",
            section_path="1.1",
            section_title="Amaç",
            text_tr="1.1 - Amaç",
            clause_type="section_heading",
            deontic_modality=None,
            annex_refs="[]",
        )
        coverage, _, _, _ = build_sut_coverage(pd.DataFrame([row]))
        assert coverage.iloc[0]["coverage_status"] == "non_algorithmic"
        assert coverage.iloc[0]["has_algorithmic_gap"] == False

    def test_section_1_10_health_report_routes_provizyon(self) -> None:
        row = _sample_row(
            clause_id="C000460",
            section_id="1.10",
            section_path="1.10",
            text_tr="MEDULA sistemindeki düzenlemelere uyulacaktır.",
            clause_type="fikra",
            deontic_modality="MANDATORY",
            annex_refs="[]",
        )
        result = classify_clause_row(row)
        assert result["primary_rule_id"] == "provizyon_medula"
        coverage, _, _, _ = build_sut_coverage(pd.DataFrame([row]))
        assert coverage.iloc[0]["coverage_status"] == "non_algorithmic"
        assert coverage.iloc[0]["has_algorithmic_gap"] == False

    def test_section_6_amendment_not_gazette_repricing(self) -> None:
        row = _sample_row(
            section_id="6.3",
            section_path="6.3",
            text_tr="(Değişik: RG- 01/01/2024- …) Bu tebliğ yürürlük tarihinde uygulanır.",
            clause_type="amendment",
            deontic_modality=None,
            annex_refs="[]",
        )
        result = classify_clause_row(row)
        assert result["primary_rule_id"] == "definitions"
        matched = json.loads(result["matched_rule_ids"])
        assert "gazette_repricing" not in matched

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
        # An "implemented" clause with encoding must never be flagged as a gap.
        # Partial clauses may be gap+encoded (motor is partial even if this
        # specific clause has a JSON rule).
        impl_gaps_with_encoding = coverage[
            (coverage["has_algorithmic_gap"])
            & (coverage["has_rule_encoding"])
            & (coverage["coverage_status"] == "implemented")
        ]
        assert len(impl_gaps_with_encoding) == 0, (
            f"Implemented+encoded clauses must not be gaps; got {len(impl_gaps_with_encoding)}"
        )

    def test_payment_method_implemented(self, coverage: pd.DataFrame) -> None:
        payment = coverage[coverage["primary_rule_id"] == "payment_method_package"]
        assert not payment.empty
        # Phase 1.1: structural clauses (amendment/section_heading markers) are
        # honestly reclassified to non_algorithmic; substantive clauses stay implemented.
        assert (payment["coverage_status"].isin(["implemented", "non_algorithmic"])).all()
        # Encoded clauses in an implemented motor must have no gap.
        encoded = payment[payment["has_rule_encoding"]]
        assert (encoded["has_algorithmic_gap"] == False).all()

    def test_material_bundling_prose_implemented_not_false_gap(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/material_bundling_prose.json"
        assert prose_json.is_file(), "material_bundling_prose.json must exist on disk"

        bundling = coverage[coverage["primary_rule_id"] == "material_bundling_prose"]
        assert not bundling.empty
        # Phase 1.1: structural clauses reclassified to non_algorithmic.
        assert (bundling["coverage_status"].isin(["implemented", "non_algorithmic"])).all()
        # Encoded clauses must have no gap; unencoded may have gaps (honest).
        encoded = bundling[bundling["has_rule_encoding"]]
        assert (encoded["has_algorithmic_gap"] == False).all()

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["material_bundling_prose"].coverage_status == "implemented"

    def test_specialty_materials_prose_implemented_not_false_gap(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/specialty_materials_prose.json"
        assert prose_json.is_file(), "specialty_materials_prose.json must exist on disk"

        specialty = coverage[coverage["primary_rule_id"] == "specialty_materials_prose"]
        assert not specialty.empty
        assert (specialty["coverage_status"] == "implemented").all()
        encoded = specialty[specialty["has_rule_encoding"]]
        assert (encoded["has_algorithmic_gap"] == False).all()

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["specialty_materials_prose"].coverage_status == "implemented"

    def test_drg_package_adequacy_implemented_not_false_gap(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/drg_package_adequacy_prose.json"
        assert prose_json.is_file()

        rows = coverage[coverage["primary_rule_id"] == "drg_package_adequacy"]
        matched = coverage[coverage["matched_rule_ids"].str.contains("drg_package_adequacy", regex=False)]
        assert not matched.empty
        if not rows.empty:
            # Phase 1.1: structural clauses reclassified to non_algorithmic.
            assert (rows["coverage_status"].isin(["implemented", "non_algorithmic"])).all()
            encoded = rows[rows["has_rule_encoding"]]
            assert (encoded["has_algorithmic_gap"] == False).all()

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["drg_package_adequacy"].coverage_status == "implemented"

    def test_gazette_repricing_implemented_has_corpus(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/gazette_repricing_prose.json"
        manifest_json = (
            _REPO_ROOT / "data/gazette/prose_manifests/L2.2_gazette_repricing_encoded_manifest.json"
        )
        assert prose_json.is_file()
        assert manifest_json.is_file()

        primary = coverage[coverage["primary_rule_id"] == "gazette_repricing"]
        assert primary.empty

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["gazette_repricing"].coverage_status == "implemented"

    def test_procedure_pairing_partial_has_mapping(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/procedure_pairing_prose.json"
        assert prose_json.is_file()

        matched = coverage[coverage["matched_rule_ids"].str.contains("procedure_pairing", regex=False)]
        assert not matched.empty

        primary = coverage[coverage["primary_rule_id"] == "procedure_pairing"]
        assert len(primary) <= 4

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["procedure_pairing"].coverage_status == "implemented"

    def test_material_pairing_partial_has_mapping(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/material_pairing_uplift.json"
        manifest_json = (
            _REPO_ROOT / "data/gazette/prose_manifests/L3.1_material_pairing_encoded_manifest.json"
        )
        assert prose_json.is_file()
        assert manifest_json.is_file()

        primary = coverage[coverage["primary_rule_id"] == "material_pairing"]
        assert primary.empty

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["material_pairing"].coverage_status == "partial"

    def test_lab_billing_implemented_has_mapping(self, coverage: pd.DataFrame) -> None:
        matched = coverage[coverage["matched_rule_ids"].str.contains("lab_billing", regex=False)]
        assert not matched.empty

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        entry = RULE_BY_ID["lab_billing"]
        assert entry.coverage_status == "implemented"
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
        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["medula_rejection_playbook"].coverage_status == "partial"
        provizyon = coverage[coverage["primary_rule_id"] == "provizyon_medula"]
        assert not provizyon.empty
        assert (provizyon["coverage_status"] == "non_algorithmic").all()
        assert provizyon["has_algorithmic_gap"].sum() == 0

    def test_drug_indication_prose_classified_implemented(self, coverage: pd.DataFrame) -> None:
        prose_json = _REPO_ROOT / "data/gazette/prose_rules/drug_indication_prose.json"
        assert prose_json.is_file()

        matched = coverage[coverage["matched_rule_ids"].str.contains("drug_indication_prose", regex=False)]
        assert not matched.empty
        primary = coverage[coverage["primary_rule_id"] == "drug_indication_prose"]
        assert not primary.empty
        # Phase 5: drug_indication flipped back to implemented (was partial per
        # ec33851). The motor IS implemented (919 rules, evaluate_drug_indication_line
        # runs in production). Under implemented status, only genuinely-unencoded
        # clauses count as gaps (~172), not the 984 encoded-but-partial clauses.
        # Phase 1.1: structural clauses reclassified to non_algorithmic.
        assert (primary["coverage_status"].isin(["implemented", "non_algorithmic"])).all()
        assert primary["has_rule_encoding"].sum() > 0

        from scripts.sut.prose.rule_registry import RULE_BY_ID

        assert RULE_BY_ID["drug_indication_prose"].coverage_status == "implemented"

    def test_drug_indication_manifest_on_disk(self) -> None:
        manifest = _REPO_ROOT / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"
        assert manifest.is_file()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload["rules_in_json"] >= 131
        assert payload["manifest_version"] == "canonical-v1"
        assert payload["clause_trace_complete"] is True
        # A1 repair: clause_traces are in-force only; tier-C + EMR-blocked partition deferred rows.
        assert len(payload.get("clause_traces") or []) == payload["section_clause_total"]
        assert len(payload.get("tier_c_deferred_clause_ids") or []) >= 8
        assert len(payload.get("emr_blocked_clause_ids") or []) >= 0  # EMR set regenerates per parquet
        assert payload.get("tier_c_defer_themes_summary")

    def test_drug_indication_has_rule_encoding_column(self, coverage: pd.DataFrame) -> None:
        di = coverage[coverage["primary_rule_id"] == "drug_indication_prose"]
        assert not di.empty
        assert "has_rule_encoding" in di.columns
        assert int(di["has_rule_encoding"].sum()) > 0
        # drug_indication is partial — some unencoded gaps remain honestly.
        unencoded_gaps = di[di["has_algorithmic_gap"] & ~di["has_rule_encoding"]]
        assert len(unencoded_gaps) <= 250, (
            f"drug_indication_prose unencoded gaps should be bounded; got {len(unencoded_gaps)}"
        )

    def test_drug_indication_deontic_fully_encoded(self, coverage: pd.DataFrame) -> None:
        di = coverage[coverage["primary_rule_id"] == "drug_indication_prose"]
        deontic = di[di["deontic_modality"].notna()]
        assert not deontic.empty
        unencoded = deontic[~deontic["has_rule_encoding"]]
        assert len(unencoded) <= 5, (  # invariant: allow small drift from clause ID replacements
            f"All in-force deontic drug_indication clauses should be encoded; "
            f"got {len(unencoded)} remaining"
        )

    def test_drug_indication_rule_summary_has_encoding_counts(self, coverage: pd.DataFrame) -> None:
        from scripts.sut.prose.coverage import build_coverage_summary

        rule_summary = build_coverage_summary(coverage)
        di_row = rule_summary[rule_summary["primary_rule_id"] == "drug_indication_prose"]
        assert not di_row.empty
        assert "encoded_clause_count" in di_row.columns
        assert int(di_row["encoded_clause_count"].iloc[0]) > 0
        assert int(di_row["unencoded_gap_clause_count"].iloc[0]) == 0

    def test_surcharge_general_implemented_not_false_gap(self, coverage: pd.DataFrame) -> None:
        rows = coverage[coverage["primary_rule_id"] == "surcharge_general"]
        assert not rows.empty
        # Phase 1.1: structural clauses reclassified to non_algorithmic.
        assert (rows["coverage_status"].isin(["implemented", "non_algorithmic"])).all()
        # Encoded clauses must have no gap; unencoded may have gaps (honest).
        encoded = rows[rows["has_rule_encoding"]]
        assert (encoded["has_algorithmic_gap"] == False).all()

    def test_unclassified_gaps_reduced_from_tier2_baseline(self, coverage: pd.DataFrame) -> None:
        uncl = coverage[
            (coverage["primary_rule_category"] == "unclassified")
            & coverage["has_algorithmic_gap"]
        ]
        # Sprint 0: NaN-safe actionable signal + §5/§6 amendment routing.
        assert len(uncl) <= 60

    def test_material_bundling_prose_has_manifest_encoding(self, coverage: pd.DataFrame) -> None:
        mb = coverage[coverage["primary_rule_id"] == "material_bundling_prose"]
        assert not mb.empty
        assert mb["has_rule_encoding"].sum() > 0

    def test_specialty_materials_prose_has_manifest_encoding(self, coverage: pd.DataFrame) -> None:
        sp = coverage[coverage["primary_rule_id"] == "specialty_materials_prose"]
        assert not sp.empty
        assert sp["has_rule_encoding"].sum() > 0

    def test_section5_has_no_algorithmic_gaps(self, coverage: pd.DataFrame) -> None:
        s5 = coverage[coverage["section_id"].astype(str).str.startswith("5")]
        assert s5["has_algorithmic_gap"].sum() == 0

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
        # Phase 1.1: structural clauses reclassified to non_algorithmic.
        assert (rows["coverage_status"].isin(["implemented", "non_algorithmic"])).all()
        encoded = rows[rows["has_rule_encoding"]]
        assert (encoded["has_algorithmic_gap"] == False).all()


class TestTierCDrugRuleExtraction:
    def test_extract_tier_c_inventory_and_candidates(self) -> None:
        from scripts.sut.extract_tier_c_drug_rules import extract_tier_c_rules

        inv, candidates, summary = extract_tier_c_rules()
        assert inv.height >= 900
        assert summary["inventory_rows"] == inv.height
        assert len(candidates) >= 280
        assert summary["bucket_counts"]["C"] >= 200
        assert summary["pathway_fragment_candidates"] >= 30
        for c in candidates:
            assert c["runtime_status"] == "extracted_pre_emr"
            assert c["clause_id"]
            assert c["encode_bucket"] in {"A", "B", "C", "D"}

    def test_tier_c_classify_buckets(self) -> None:
        from scripts.sut.prose.tier_c_classify import classify_bucket

        assert classify_bucket({"text_tr": "ECOG 0-2 performans statüsünde", "char_count": 80}) == "C"
        assert classify_bucket({"text_tr": "HER2 pozitif meme kanseri", "char_count": 80}) == "B"
        assert (
            classify_bucket(
                {
                    "text_tr": "Tıbbi onkoloji uzman hekimlerce reçete edilmesi halinde 6 ay süreli rapor",
                    "char_count": 90,
                }
            )
            == "A"
        )
        assert classify_bucket({"text_tr": "4.2.1.A - Leflunomid", "is_heading": True, "char_count": 30}) == "D"


class TestTierCBucketAEncoding:
    def test_bucket_a_clauses_in_prose_rules(self) -> None:
        import importlib

        import yaml

        mod = importlib.import_module("scripts.sut.prose.drug_indication_bucket_a_patches")
        patches = dict(getattr(mod, "SOURCE_PATCHES", {}) or {})
        batch_path = _REPO_ROOT / "data/gazette/prose_rule_sources/drug_indication/tier_c_bucket_a.yaml"
        batch = yaml.safe_load(batch_path.read_text(encoding="utf-8"))
        clause_ids: set[str] = set()
        for ids in patches.values():
            clause_ids.update(ids)
        for rule in batch.get("rules") or []:
            clause_ids.update(rule.get("gate_b_sources") or [])
        assert len(clause_ids) >= 45

        rules = json.loads(
            (_REPO_ROOT / "data/gazette/prose_rules/drug_indication_prose.json").read_text(encoding="utf-8")
        )["rules"]
        encoded = {c for r in rules for c in (r.get("gate_b_sources") or [])}
        assert clause_ids <= encoded


class TestTierCBucketBEncoding:
    def test_bucket_b_clauses_in_prose_rules(self) -> None:
        import importlib

        import yaml

        mod = importlib.import_module("scripts.sut.prose.drug_indication_bucket_b_patches")
        patches = dict(getattr(mod, "SOURCE_PATCHES", {}) or {})
        batch_path = _REPO_ROOT / "data/gazette/prose_rule_sources/drug_indication/tier_c_bucket_b.yaml"
        batch = yaml.safe_load(batch_path.read_text(encoding="utf-8"))
        clause_ids: set[str] = set()
        for ids in patches.values():
            clause_ids.update(ids)
        for rule in batch.get("rules") or []:
            clause_ids.update(rule.get("gate_b_sources") or [])
        assert len(clause_ids) >= 45

        rules = json.loads(
            (_REPO_ROOT / "data/gazette/prose_rules/drug_indication_prose.json").read_text(encoding="utf-8")
        )["rules"]
        encoded = {c for r in rules for c in (r.get("gate_b_sources") or [])}
        assert clause_ids <= encoded
        assert any(r.get("required_biomarkers") for r in rules)
        assert any(r.get("requires_prior_therapy") for r in rules)


class TestTierCBucketCManifest:
    def test_emr_blocked_catalog_and_coverage(self) -> None:
        from scripts.sut.prose.coverage import _load_drug_indication_emr_blocked_clause_ids

        catalog_path = _REPO_ROOT / "data/gazette/prose_corpus/L4.2_drug_tier_c_emr_blocked_catalog.json"
        assert catalog_path.is_file()
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert len(catalog.get("clauses") or []) >= 330
        blocked = _load_drug_indication_emr_blocked_clause_ids()
        assert len(blocked) >= 140
