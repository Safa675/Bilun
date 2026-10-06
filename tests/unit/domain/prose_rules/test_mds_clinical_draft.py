"""Source-proven candidate boundaries and always-gated MDS runtime."""
from dataclasses import fields
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unicodedata
from xml.etree import ElementTree as ET
import zipfile

import polars as pl
import pytest

from src.bilun.domain.claims.mds_evidence import MdsEvidence
from src.bilun.domain.prose_rules._drug_indication import clinical_mds as draft
from tests.unit.domain.claims.test_mds_evidence_transport import DAY, facts

REPORT = "4.2.9.mds_esa_hematology_report"
INITIATION = "4.2.9.mds_esa_initiation_hematology_report"
ROOT = Path(__file__).resolve().parents[4]


def line(drug="epoetin alfa", *, evidence=None, **changes):
    return SimpleNamespace(**{
        "drug_name": drug, "drug_claim_date": DAY,
        "mds_evidence": facts() if evidence is None else evidence,
        "drug_specialty_board_report_present": True,
        "prescriber_specialty": "hematoloji", **changes,
    })


def candidate(evidence=None, *, drug="epoetin alfa", rule=REPORT, codes=None, **changes):
    return draft.evaluate_mds_clinical_candidate(line(drug, evidence=evidence, **changes), rule, codes=codes)


def authority(monkeypatch, status="admitted"):
    calls = []

    def resolve(family, service):
        calls.append((family, service))
        return SimpleNamespace(status=status, model_dump=lambda: {
            "family_id": family, "status": status,
            "service_date": service.isoformat() if service else None,
        })

    monkeypatch.setattr(draft, "resolve_source_authority", resolve)
    return calls


def _norm(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def test_pinned_docx_independent_strike_aware_source_proof_and_exact_corpus_binding():
    proof = json.loads((ROOT / "data/gazette/clinical_sources/mds_candidate_2026_10.json").read_text())
    raw = (ROOT / proof["source_docx"]["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573"
    corpus_path = ROOT / proof["source_corpus"]["path"]
    assert hashlib.sha256(corpus_path.read_bytes()).hexdigest() == "40b2b7ebdb44c2483867d5413f7af3d97bb55c92d43d3a4be2737d80135425ec"
    with zipfile.ZipFile(ROOT / proof["source_docx"]["path"]) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        styles = ET.fromstring(archive.read("word/styles.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    w = "{" + ns["w"] + "}"
    paragraphs = document.findall(".//w:p", ns)
    corpus = pl.read_parquet(corpus_path)
    assert len(proof["paragraphs"]) == 7
    assert not styles.findall(".//w:strike", ns) and not styles.findall(".//w:dstrike", ns)
    for source in proof["paragraphs"]:
        paragraph = paragraphs[source["paragraph_index"]]
        assert paragraph.get("{http://schemas.microsoft.com/office/word/2010/wordml}paraId") == source["xml_para_id"]
        assert not paragraph.findall(".//w:del", ns) and not paragraph.findall(".//w:dstrike", ns)
        operative, struck, pending = [], [], ""
        for run in paragraph.findall(".//w:r", ns):
            text = "".join(node.text or "" for node in run.findall(".//w:t", ns))
            if not text:
                continue
            strike = run.find("w:rPr/w:strike", ns)
            active = strike is not None and strike.get(w + "val", "true").casefold() not in {"false", "0", "off"}
            if active:
                pending += text
            else:
                if pending:
                    struck.append(re.sub(r"\s+", " ", pending).strip())
                    pending = ""
                operative.append(text)
        if pending:
            struck.append(re.sub(r"\s+", " ", pending).strip())
        text = _norm("".join(operative))
        digest = hashlib.sha256(text.encode()).hexdigest()
        assert text == source["operative_text"]
        assert digest == source["operative_text_sha256"]
        assert struck == source["struck_fragments"]
        rows = corpus.filter(pl.col("clause_key") == source["source_ref"])
        assert rows.height == 1 and _norm(rows["in_force_text"][0]) == text
    mds = proof["paragraphs"][-1]
    assert mds["paragraph_index"] == 4489 and mds["xml_para_id"] == "3108F0FD"
    assert mds["source_ref"] == "4.2.9.A-2#17efb08b"
    assert "Eritropoietin alfa-beta için maksimum doz haftada 900 IU/kg" in mds["operative_text"]
    assert "hematoloji uzman hekimi tarafından düzenlenen uzman hekim raporuna dayanılarak" in mds["operative_text"]
    assert "darbepoetin için maksimum doz haftada 150 µg" in mds["struck_fragments"][0]
    assert mds["struck_fragments"][1] == "ve darbepoetin"
    assert proof["clinical_eligibility_complete"] is False
    assert proof["mechanical_family_admission"] is False
    assert proof["admitted_service_date_windows"] == []
    assert proof["independent_interpretation_status"] == "pending"


@pytest.mark.parametrize("drug,substance", [
    ("epoetin alfa", "epoetin_alfa"), ("epoetin beta", "epoetin_beta"),
    ("eritropoietin alfa", "epoetin_alfa"), (" ERITROPOIETIN BETA ", "epoetin_beta"),
])
@pytest.mark.parametrize("rule", [REPORT, INITIATION])
def test_exact_substance_candidate_passes_only_incomplete_experimental_checks(drug, substance, rule):
    outcome = candidate(facts(substance=substance), drug=drug, rule=rule)
    assert outcome["criterion_status"] == "criterion_clear"
    assert outcome["constraint_set"] == "mds_epoetin"
    assert all(check["status"] == "pass" for check in outcome["checks"])
    assert outcome["missing_inputs"] == []
    assert outcome["clinical_eligibility_complete"] is False
    assert outcome["verification_status"] == "ai_generated_pending_review"
    assert "4.2.9.A.(2)#8b36884a" in outcome["source_refs"]
    assert "source_authority" not in outcome and "runtime_coverage" not in outcome
    assert not any("value" in check for check in outcome["checks"])


@pytest.mark.parametrize("field,values", [
    ("hb_value", [(10.999, "criterion_clear"), (11, "restriction_not_met"), (12, "restriction_not_met")]),
    ("blast_value", [(4.999, "criterion_clear"), (5, "restriction_not_met"), (5.001, "restriction_not_met")]),
    ("serum_epo_value", [(499.999, "criterion_clear"), (500, "restriction_not_met"), (500.001, "restriction_not_met")]),
    ("weekly_dose_value", [(899.999, "criterion_clear"), (900, "criterion_clear"), (900.001, "restriction_not_met")]),
])
def test_proven_initiation_and_weekly_dose_boundaries(field, values):
    for value, status in values:
        outcome = candidate(facts(**{field: value}))
        assert outcome["criterion_status"] == status
        assert outcome["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("hb,status", [(11, "criterion_clear"), (12, "criterion_clear"), (12.001, "restriction_not_met")])
def test_continuation_stop_is_strictly_above_twelve_not_at_target_equality(hb, status):
    outcome = candidate(facts(phase="continuation", hb_value=hb, blast_value=None, serum_epo_value=None))
    assert outcome["criterion_status"] == status
    assert not any(check["field"] in {"mds_evidence.blast_value", "mds_evidence.serum_epo_value"} for check in outcome["checks"])


@pytest.mark.parametrize("phase,missing", [(None, "phase"), ("invalid", "phase"), ("restart", "phase_interpretation")])
def test_invalid_missing_and_unsupported_restart_phase_stop_before_predicates(monkeypatch, phase, missing):
    monkeypatch.setattr(draft.Reader, "test", lambda *_: pytest.fail("phase gate attempted a predicate"))
    outcome = candidate(facts(phase=phase, hb_value=99, weekly_dose_value=999))
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == ["mds_evidence." + missing]
    assert outcome["checks"] == [{"field": "mds_evidence.phase", "status": "unknown"}]


def test_initiation_only_selected_rule_cannot_evaluate_continuation():
    outcome = candidate(facts(phase="continuation", hb_value=99), rule=INITIATION)
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == ["mds_evidence.phase_context_reconciliation"]


@pytest.mark.parametrize("name", ["hb", "blast", "serum_epo", "weekly_dose"])
@pytest.mark.parametrize("bad", [None, True, "900", -1, float("nan"), float("inf")])
def test_invalid_numeric_fields_are_unknown_instead_of_compared(name, bad):
    outcome = candidate(facts(**{name + "_value": bad}))
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == ["mds_evidence." + name + "_value"]
    assert {"field": "mds_evidence." + name + "_value", "status": "unknown"} in outcome["checks"]


@pytest.mark.parametrize("name", ["hb", "blast", "serum_epo", "weekly_dose"])
@pytest.mark.parametrize("bad", [None, "wrong", True])
def test_missing_or_wrong_units_never_clear_even_numeric_values_in_range(name, bad):
    outcome = candidate(facts(**{name + "_unit": bad}))
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == ["mds_evidence." + name + "_unit"]


@pytest.mark.parametrize("name", ["hb", "blast", "serum_epo", "report", "hemogram"])
@pytest.mark.parametrize("bad", [None, "2026-02-30", DAY + timedelta(days=1)])
def test_missing_invalid_and_future_document_or_measurement_dates_are_unknown(name, bad):
    outcome = candidate(facts(**{name + "_date": bad}))
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == ["mds_evidence." + name + "_date"]


def test_source_does_not_establish_arbitrary_test_recency_or_calendar_month_day_conversion():
    prior = date(2020, 1, 1)
    assert candidate(facts(hb_date=prior, blast_date=prior, serum_epo_date=prior,
                           report_date=prior, hemogram_date=prior))["criterion_status"] == "criterion_clear"
    assert candidate(facts(prescribed_supply_months=1))["criterion_status"] == "criterion_clear"
    assert candidate(facts(prescribed_supply_months=1.001))["criterion_status"] == "restriction_not_met"
    assert candidate(facts(prescribed_supply_months=None), prescribed_supply_days=30)["criterion_status"] == "unknown"


@pytest.mark.parametrize("field", [field.name for field in fields(MdsEvidence) if field.type == "bool | None"])
def test_each_explicit_source_documentary_condition_is_required_and_unknown_is_distinct(field):
    missing = candidate(facts(**{field: None}))
    assert missing["criterion_status"] == "unknown"
    assert missing["missing_inputs"] == ["mds_evidence." + field]
    assert candidate(facts(**{field: False}))["criterion_status"] == "restriction_not_met"


@pytest.mark.parametrize("specialty,status", [("hematology", "criterion_clear"), ("internal_medicine", "restriction_not_met"), ("other", "restriction_not_met"), (None, "unknown")])
def test_report_requires_hematology_specialist_not_internal_medicine(specialty, status):
    assert candidate(facts(report_author_specialty=specialty))["criterion_status"] == status


@pytest.mark.parametrize("specialty,status", [("hematology", "criterion_clear"), ("internal_medicine", "criterion_clear"), ("other", "restriction_not_met"), (None, "unknown")])
def test_prescribing_specialist_can_be_hematology_or_internal_medicine(specialty, status):
    assert candidate(facts(prescribed_by_specialty=specialty))["criterion_status"] == status


@pytest.mark.parametrize("drug", ["epoetin", "eritropoietin", "epoetin zeta", "darbepoetin", "ARANESP", "EPREX", "binocrit", "neo recormon", "mircera", "metoksipolietilen glikol epoetin beta", "epoetin beta like"])
def test_generic_esa_brand_darbepoetin_and_peg_names_never_receive_substance_checks(drug):
    assert candidate(drug=drug) is None
    assert draft.evaluate_mds_clinical_draft(line(drug), REPORT) is None


@pytest.mark.parametrize("rule", [None, "4.2.9.esa_indication_equivalence", "4.2.9.A-2.darbepoetin_mds_source_review", "4.2.9.ckd_esa_report"])
def test_only_exact_selected_mds_rule_pairs_receive_candidate(rule):
    assert candidate(rule=rule) is None


def test_exact_substance_binding_cannot_be_supplied_by_generic_or_mismatched_evidence():
    for substance in (None, "epoetin", "epoetin_beta"):
        outcome = candidate(facts(substance=substance, hb_value=99))
        assert outcome["criterion_status"] == "unknown"
        assert "mds_evidence.substance_context_reconciliation" in outcome["missing_inputs"]
        assert not any(check["status"] == "fail" for check in outcome["checks"])


@pytest.mark.parametrize("codes", [None, [], ["D46"], ["D46.1"], ["D47"]])
def test_diagnosis_codes_never_supply_explicit_source_mds_indication(codes):
    outcome = candidate(facts(indication=None, hb_value=99), codes=codes)
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == ["mds_evidence.indication"]


@pytest.mark.parametrize("evidence,codes", [
    (facts(indication="ckd_anemia"), None), (facts(indication=None), ["N18.5"]),
    (facts(indication="ckd_anemia"), ["N18.5"]),
])
def test_pure_ckd_never_acquires_mds_restriction(evidence, codes):
    assert candidate(evidence, codes=codes) is None
    assert draft.evaluate_mds_clinical_draft(line(evidence=evidence), REPORT, codes=codes) is None


@pytest.mark.parametrize("evidence,codes", [
    (facts(), ["D46.1", "N18.5"]), (facts(), ["N18.5"]),
    (facts(indication="ckd_anemia"), ["D46.1"]),
])
def test_mixed_or_conflicting_mds_ckd_context_stays_review_before_negative_clinical_values(evidence, codes):
    outcome = candidate(evidence, codes=codes)
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == ["mds_evidence.indication_context_reconciliation"]
    assert outcome["checks"] == [{"field": "mds_evidence.indication", "status": "unknown"}]


@pytest.mark.parametrize("changes,missing", [
    ({"drug_claim_date": None}, "drug_claim_date"),
    ({"drug_claim_date": "2026-10-02T00:00:00"}, "drug_claim_date"),
    ({"evidence": facts(applies_on=DAY - timedelta(days=1))}, "mds_evidence.applies_on"),
    ({"evidence": facts(assessment_date=None)}, "mds_evidence.assessment_date"),
    ({"evidence": facts(assessment_date=DAY + timedelta(days=1))}, "mds_evidence.assessment_date"),
])
def test_candidate_requires_explicit_service_scope_and_nonfuture_assessment(changes, missing):
    outcome = candidate(**changes)
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["checks"] == []
    assert outcome["missing_inputs"] == [missing]


@pytest.mark.parametrize("service", [None, date(2013, 10, 4), date(2024, 5, 16), date(2024, 5, 17), DAY, date(2026, 10, 5), date(2026, 10, 6)])
def test_existing_twelve_family_renewal_never_admits_mds_or_fills_historical_gaps(monkeypatch, service):
    monkeypatch.setattr(draft.Reader, "test", lambda *_: pytest.fail("unadmitted source attempted predicates"))
    evidence = facts(applies_on=service, assessment_date=service)
    outcome = draft.evaluate_mds_clinical_draft(line(evidence=evidence, drug_claim_date=service), REPORT)
    assert outcome["source_authority"]["family_id"] == "mds_epoetin"
    assert outcome["source_authority"]["status"] == "review_required"
    assert outcome["criterion_status"] == "not_evaluated" and outcome["checks"] == []
    assert "verified_source_for_service_date" in outcome["missing_inputs"]
    assert "mds_clinical_interpretation_release" in outcome["missing_inputs"]
    assert outcome["clinical_eligibility_complete"] is False


def test_mocked_source_admission_and_request_release_flags_cannot_enable_predicates(monkeypatch):
    calls = authority(monkeypatch)
    monkeypatch.setattr(draft.Reader, "test", lambda *_: pytest.fail("unreleased interpretation attempted predicates"))
    outcome = draft.evaluate_mds_clinical_draft(line(
        evidence=facts(hb_value=99), mds_clinical_interpretation_release=True,
        clinical_eligibility_complete=True, source_admitted=True,
    ), REPORT)
    assert calls == [("mds_epoetin", DAY)]
    assert outcome["criterion_status"] == "not_evaluated" and outcome["checks"] == []
    assert outcome["missing_inputs"] == ["mds_clinical_interpretation_release"]
    assert outcome["clinical_eligibility_complete"] is False


def test_test_only_interpretation_release_still_requires_source_admission(monkeypatch):
    authority(monkeypatch, "review_required")
    monkeypatch.setattr(draft, "_MDS_CLINICAL_INTERPRETATION_RELEASED", True)
    monkeypatch.setattr(draft.Reader, "test", lambda *_: pytest.fail("failed source gate attempted predicates"))
    outcome = draft.evaluate_mds_clinical_draft(line(), REPORT)
    assert outcome["criterion_status"] == "not_evaluated" and outcome["checks"] == []
    assert outcome["missing_inputs"] == ["verified_source_for_service_date"]


def test_test_only_both_gate_release_still_keeps_partial_review(monkeypatch):
    authority(monkeypatch)
    monkeypatch.setattr(draft, "_MDS_CLINICAL_INTERPRETATION_RELEASED", True)
    outcome = draft.evaluate_mds_clinical_draft(line(), REPORT)
    assert outcome["criterion_status"] == "criterion_clear"
    assert outcome["clinical_eligibility_complete"] is False
    assert outcome["verification_status"] == "ai_generated_pending_review"
