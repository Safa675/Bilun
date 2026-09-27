"""Classification consumes observations; it never re-evaluates a broad engine."""

import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

import polars as pl
import pytest

from src.bilun.domain.billing import broad_rule_classification as policy
from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.billing.dental_rule_evaluations import evaluate_dental_rules
from src.bilun.domain.billing.drug_combination_evaluations import evaluate_drug_combinations
from src.bilun.domain.billing.fatura_inceleme_evaluations import evaluate_fatura_inceleme
from src.bilun.domain.billing.gap_closing_evaluations import evaluate_gap_closing
from src.bilun.domain.billing.payment_traceability_evaluations import (
    evaluate_payment_method_traceability,
)
from src.bilun.domain.billing.rule_findings import RuleEvaluation
from src.bilun.domain.billing.treatment_pricing_evaluations import evaluate_treatment_pricing
from tests.unit.domain.billing.test_dental_rule_evaluations import _context, _single

pytestmark = pytest.mark.unit
PRECIOUS = "2.4.1.(1).precious_metal_no_pay"
ADAPTERS = (
    evaluate_dental_rules,
    evaluate_drug_combinations,
    evaluate_fatura_inceleme,
    evaluate_gap_closing,
    evaluate_payment_method_traceability,
    evaluate_treatment_pricing,
)


def _test_attestation():
    # Synthetic classifier-boundary evidence, NOT a production legal review.
    return policy.SourceApplicabilityAttestation(
        clause_text_sha256="10e6c764fd9f71cff7e1f8ef9e1bc5b700da119ac7f82d4916add48143c72ba3",
        official_docx_sha256="e6697a42cb24e20335c0a59ef9f9b7554d95a2db9a0280a90617564df9538821",
        service_date_from=date(2026, 7, 10),
        service_date_through=date(2026, 7, 10),
        review_evidence_id="synthetic-test-only",
        source_manifest_sha256="a" * 64,
    )


def _dental(name="altın", charge="120"):
    ctx = _single()
    return replace(
        ctx,
        material_lines=(
            replace(ctx.material_lines[0], material_name=name, billed_amount_try=Decimal(charge)),
        ),
    )


def _classify(ctx, *, attestation=True):
    batch = evaluate_dental_rules("P1", ctx)
    evaluation = next(row for row in batch.evaluations if row.rule_id == PRECIOUS)
    raw = next((row for row in batch.legacy_rows if row.rule_id == PRECIOUS), None)
    return policy.BroadRuleClassifier(ctx, _test_attestation() if attestation else None).classify(
        evaluation, raw
    )


def test_exact_sourced_material_is_unpriced_with_real_line_identity():
    result = _classify(_dental())
    assert result.disposition == "unpriced_compliance"
    assert result.finding.line_id == "M1"
    assert result.finding.claim_id == "C1"
    assert result.finding.risk_amount_try is None
    assert result.finding.savings_try is None
    assert result.legacy_row["risk_amount"] == 120.0


@pytest.mark.parametrize("name", ["altın köprü", "altın renkli plastik", "platin görünümlü"])
def test_ambiguous_free_text_cannot_become_confirmed(name):
    result = _classify(_dental(name))
    assert result.disposition == "review_only"
    assert result.reason == "exact_source_named_material_or_verified_composition_required"
    assert result.finding is None


def test_dict_adapter_defaults_do_not_become_service_or_charge_proof():
    ctx = _dental()
    ctx = replace(ctx, claims=(replace(ctx.claims[0], scenario_tag="validate_claim_adapter"),))
    result = _classify(ctx)
    assert result.disposition == "unavailable"
    assert result.reason == "request_field_provenance_unavailable"
    assert result.finding is None


def test_snapshots_alone_do_not_attest_a_legal_service_interval():
    result = _classify(_dental(), attestation=False)
    assert result.disposition == "unavailable"
    assert result.reason == "source_version_applicability_required"
    assert result.finding is None


@pytest.mark.parametrize(
    "name",
    [
        "altın",
        "platin",
        "paladyum+platin",
        "irrudyum+platin",
        "iropal",
        "argenco 23",
        "bego gold EWL",
        "polliag-M",
    ],
)
def test_exact_official_names_with_attested_dates_can_be_unpriced_findings(name):
    result = _classify(_dental(name))
    assert result.disposition == "unpriced_compliance"
    assert result.source_status == "primary_meaning_and_date_verified"
    fields = asdict(result.finding)
    assert all(value is None for key, value in fields.items() if key.endswith("_try"))
    assert fields["regulatory_source"]["applicability_review_evidence_id"] == "synthetic-test-only"


def test_authored_spelling_does_not_invent_an_official_source_alias():
    result = _classify(_dental("iridyum+platin"))
    assert result.disposition == "review_only"
    assert result.finding is None


@pytest.mark.parametrize(
    "charge,expected",
    [
        ("0", "not_applicable"),
        ("-1", "not_applicable"),
        ("NaN", "unavailable"),
        ("Infinity", "unavailable"),
        ("0.01", "unpriced_compliance"),
    ],
)
def test_positive_actual_charge_is_required(charge, expected):
    result = _classify(_dental(charge=charge))
    assert result.disposition == expected
    assert (result.finding is not None) == (expected == "unpriced_compliance")


@pytest.mark.parametrize("field", ["material_date", "procedure_date"])
@pytest.mark.parametrize("day", [None, date(2026, 7, 9), date(2026, 7, 11)])
def test_each_service_date_must_be_inside_attested_interval(field, day):
    ctx = _dental()
    if field == "material_date":
        ctx = replace(ctx, material_lines=(replace(ctx.material_lines[0], material_date=day),))
    else:
        ctx = replace(ctx, procedure_lines=(replace(ctx.procedure_lines[0], procedure_date=day),))
    result = _classify(ctx)
    assert result.disposition == "unavailable"
    assert result.reason == "source_version_applicability_required"


@pytest.mark.parametrize(
    "change",
    [
        {"clause_text_sha256": "b" * 64},
        {"official_docx_sha256": "b" * 64},
    ],
)
def test_attestation_must_pin_reviewed_clause_and_official_snapshot(change):
    ctx = _dental()
    batch = evaluate_dental_rules("P1", ctx)
    result = policy.BroadRuleClassifier(ctx, replace(_test_attestation(), **change)).classify(
        batch.evaluations[0], batch.legacy_rows[0]
    )
    assert result.reason == "source_version_applicability_required"
    assert result.finding is None


@pytest.mark.parametrize(
    "change",
    [
        {"review_evidence_id": ""},
        {"source_manifest_sha256": "short"},
        {"service_date_from": date(2026, 7, 11)},
    ],
)
def test_attestation_rejects_incomplete_or_reversed_evidence(change):
    with pytest.raises(ValueError, match="Source attestation"):
        replace(_test_attestation(), **change)


@pytest.mark.parametrize(
    "mutation", ["heading", "amendment", "text", "missing", "duplicate", "version"]
)
def test_changed_unresolved_or_heading_source_cannot_promote(tmp_path, monkeypatch, mutation):
    frame = pl.read_parquet(policy.SUT_CLAUSES_PATH).filter(
        pl.col("clause_key") == "2.4.1.(1)#10e6c764"
    )
    if mutation == "missing":
        frame = frame.head(0)
    elif mutation == "duplicate":
        frame = pl.concat([frame, frame])
    else:
        key, value = {
            "heading": ("is_heading", True),
            "amendment": ("is_amendment", True),
            "text": ("in_force_text", "changed"),
            "version": ("source_effective_date", "2027-01-01"),
        }[mutation]
        frame = frame.with_columns(pl.lit(value).alias(key))
    path = tmp_path / "clauses.parquet"
    frame.write_parquet(path)
    monkeypatch.setattr(policy, "SUT_CLAUSES_PATH", path)
    assert _classify(_dental()).finding is None
    assert _classify(_dental()).disposition == "unavailable"


def test_missing_source_is_not_cached_after_it_becomes_available(tmp_path, monkeypatch):
    original = policy.SUT_CLAUSES_PATH
    path = tmp_path / "clauses.parquet"
    monkeypatch.setattr(policy, "SUT_CLAUSES_PATH", path)
    assert _classify(_dental()).disposition == "unavailable"
    shutil.copyfile(original, path)
    assert _classify(_dental()).disposition == "unpriced_compliance"


def test_same_size_source_replacement_with_preserved_mtime_invalidates_proof(tmp_path, monkeypatch):
    frame = pl.read_parquet(policy.SUT_CLAUSES_PATH).filter(
        pl.col("clause_key") == "2.4.1.(1)#10e6c764"
    )
    path = tmp_path / "clauses.parquet"
    frame.write_parquet(path, compression="uncompressed")
    original = path.read_bytes()
    stat = path.stat()
    monkeypatch.setattr(policy, "SUT_CLAUSES_PATH", path)
    assert _classify(_dental()).disposition == "unpriced_compliance"
    changed = frame.with_columns(
        pl.col("in_force_text").str.replace("Diş", "Xiş").alias("in_force_text")
    )
    changed.write_parquet(path, compression="uncompressed")
    assert path.stat().st_size == stat.st_size
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert path.stat().st_mtime_ns == stat.st_mtime_ns
    assert path.read_bytes() != original
    result = _classify(_dental())
    assert result.disposition == "unavailable"
    assert result.reason == "effective_source_proof_changed"
    assert result.finding is None
    path.write_bytes(original)
    assert _classify(_dental()).disposition == "unpriced_compliance"


@pytest.mark.parametrize("mutation", ["orphan", "foreign_patient", "duplicate", "blank"])
def test_context_source_ownership_is_not_assumed(mutation):
    ctx = _dental()
    line = ctx.material_lines[0]
    if mutation == "orphan":
        ctx = replace(ctx, claims=())
    elif mutation == "duplicate":
        ctx = replace(ctx, material_lines=(line, line))
    else:
        ctx = replace(
            ctx,
            material_lines=(
                replace(
                    line,
                    **{
                        "patient_id"
                        if mutation == "foreign_patient"
                        else "material_line_id": "other" if mutation == "foreign_patient" else "",
                    },
                ),
            ),
        )
    with pytest.raises(ValueError):
        policy.BroadRuleClassifier(ctx)


def test_forged_observation_or_raw_line_is_rejected():
    ctx = _dental()
    batch = evaluate_dental_rules("P1", ctx)
    classifier = policy.BroadRuleClassifier(ctx, _test_attestation())
    evaluation, raw = batch.evaluations[0], batch.legacy_rows[0]
    with pytest.raises(ValueError, match="foreign source material"):
        classifier.classify(replace(evaluation, line_id="invented"), raw)
    with pytest.raises(ValueError, match="source material mismatch"):
        classifier.classify(evaluation, replace(raw, material_line_id="invented"))
    with pytest.raises(ValueError, match="material name differs"):
        classifier.classify(
            evaluation, replace(raw, legacy_row={**raw.legacy_row, "material_name": "other"})
        )
    with pytest.raises(ValueError, match="Legacy observation patient_id mismatch"):
        classifier.classify(evaluation, raw.legacy_row)


def test_real_procedure_link_is_required_even_when_legacy_used_a_category_proxy():
    ctx = _dental()
    ctx = replace(
        ctx,
        material_lines=(
            replace(
                ctx.material_lines[0],
                procedure_line_id="absent",
                specialty_category="dental_restoration",
            ),
        ),
    )
    result = _classify(ctx)
    assert result.finding is None
    assert result.disposition == "unavailable"


def test_raw_rows_are_value_preserved_without_mutable_aliases():
    ctx = _dental()
    batch = evaluate_dental_rules("P1", ctx)
    raw = batch.legacy_rows[0]
    before = deepcopy(raw.legacy_row)
    result = policy.classify_broad_observation(
        batch.evaluations[0], raw, ctx, applicability=_test_attestation()
    )
    assert result.legacy_row == before
    result.legacy_row["risk_amount"] = -999
    assert raw.legacy_row == before
    assert result.finding.risk_amount_try is None


def test_all_496_policies_have_exact_authored_identity_and_explicit_gates():
    matrix = policy.load_broad_classification_policy()
    catalog = load_broad_rule_catalog()
    assert len(matrix) == 496
    assert list(matrix) == [row.rule_id for row in catalog]
    assert all(row.gates for row in matrix.values())
    assert (
        sum(
            row.authored_verification_status == "ai_generated_pending_review"
            for row in matrix.values()
        )
        == 31
    )
    with pytest.raises(TypeError):
        matrix[PRECIOUS] = matrix[PRECIOUS]


@pytest.mark.parametrize(
    "rule_id,surface,reason",
    [
        (
            "4.6.(4).blood_components_bundled_in_drg",
            "withheld_adverse",
            "blood_component_partial_payment_exceptions_not_checked",
        ),
        (
            "2.2.2.B-1.(d).inpatient_medications_bundled",
            "withheld_adverse",
            "drug_package_exceptions_not_checked",
        ),
        ("2.4.4.H.(3).icu_pacu_no_icu_fee", "withheld_adverse", "icu_fee_billing_not_established"),
        (
            "2.4.4.F-3.(1).private_provider_physio_compliance_with_F1_F2",
            "review_only",
            "applicability_reminder_not_breach",
        ),
    ],
)
def test_reviewed_source_semantics_block_specific_false_promotions(rule_id, surface, reason):
    row = policy.load_broad_classification_policy()[rule_id]
    assert row.matched_surface == surface
    assert row.gates[0] == reason


@pytest.mark.parametrize("which", ["policy", "condition", "action", "source", "verification"])
def test_changed_reviewed_policy_or_corpus_fails_closed(tmp_path, which):
    if which == "policy":
        path = tmp_path / "policy.json"
        payload = json.loads(policy._POLICY_PATH.read_text())
        payload["rules"][1]["matched_surface"] = "dental_precious_metal_proof"
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError, match="policy digest changed"):
            policy.load_broad_classification_policy(policy_path=path)
        return
    corpus = tmp_path / "prose"
    corpus.mkdir()
    for filename in {row.source_file.rsplit("/", 1)[-1] for row in load_broad_rule_catalog()}:
        shutil.copyfile(policy._PROSE_RULES_DIR / filename, corpus / filename)
    path = corpus / "dental_2_4_1.json"
    payload = json.loads(path.read_text())
    row = payload["rules"][0]
    if which in ("condition", "action"):
        row[which]["unreviewed"] = True
    elif which == "source":
        row["gate_b_sources"] = ["2.4.1.(2)"]
    else:
        row["verification_status"] = "ai_generated_pending_review"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="authored rule digest changed"):
        policy.load_broad_classification_policy(prose_rules_dir=corpus)


def test_first_policy_load_is_complete_and_cached_under_concurrency(monkeypatch):
    policy._load_policy.cache_clear()
    original = policy.load_broad_rule_catalog
    calls = []

    def counted(**kwargs):
        calls.append(True)
        return original(**kwargs)

    monkeypatch.setattr(policy, "load_broad_rule_catalog", counted)
    with ThreadPoolExecutor(max_workers=8) as pool:
        matrices = list(pool.map(lambda _: policy.load_broad_classification_policy(), range(20)))
    assert len(calls) == 1
    assert all(len(matrix) == 496 and matrix is matrices[0] for matrix in matrices)


@pytest.mark.parametrize("rule_id", [row.rule_id for row in load_broad_rule_catalog()])
def test_every_authored_matched_policy_requires_its_own_semantic_proof(rule_id):
    # Adversarial classification-boundary observation, NOT an invented clinical
    # trigger. Actual adapter observations are separately covered below.
    ctx = _dental()
    classifier = policy.BroadRuleClassifier(ctx)
    entry = policy.load_broad_classification_policy()[rule_id]
    dental = entry.family == "dental_2_4_1"
    evaluation = RuleEvaluation(
        patient_id="P1",
        claim_id="C1",
        rule_id=rule_id,
        evaluation_status="evaluated",
        required_inputs=[],
        missing_inputs=[],
        decision="matched",
        line_kind="material" if dental else "claim",
        line_id="M1" if dental else None,
    )
    raw = SimpleNamespace(
        patient_id="P1",
        claim_id="C1",
        rule_id=rule_id,
        family=entry.family,
        material_line_id="M1",
        legacy_row={"rule_id": rule_id, "material_name": "altın", "risk_amount": 999},
    )
    result = classifier.classify(evaluation, raw)
    assert result.finding is None
    assert result.legacy_row == raw.legacy_row
    if entry.authored_verification_status == "ai_generated_pending_review":
        assert result.reason == "authored_source_pending_independent_review"
    elif entry.matched_surface in ("withheld_adverse", "dental_precious_metal_proof"):
        assert result.disposition == "unavailable"
        assert result.reason in entry.gates
    else:
        assert result.disposition == entry.matched_surface


@pytest.mark.parametrize("missing", [False, True])
def test_real_adapter_observations_account_for_all_ids_and_preserve_raw(missing):
    ctx = _dental()
    if missing:
        ctx = replace(
            ctx,
            material_lines=(),
            procedure_lines=(),
            claims=(
                replace(
                    ctx.claims[0], claim_type="", provider_type="", department="", primary_icd10=""
                ),
            ),
        )
    batches = [fn("P1", ctx) for fn in ADAPTERS]
    classifier = policy.BroadRuleClassifier(ctx)
    results = []
    for batch in batches:
        rows = {
            (r.claim_id, r.rule_id, getattr(r, "material_line_id", None)): r
            for r in batch.legacy_rows
        }
        for evaluation in batch.evaluations:
            raw = rows.get((evaluation.claim_id, evaluation.rule_id, evaluation.line_id))
            result = classifier.classify(evaluation, raw)
            assert result.evaluation == evaluation
            assert result.legacy_row == (raw.legacy_row if raw else None)
            if evaluation.evaluation_status != "evaluated":
                assert result.disposition == evaluation.evaluation_status
            results.append(result)
    assert len(results) == len({r.evaluation.rule_id for r in results}) == 496
    assert all(row.finding is None for row in results)


def test_dental_material_cardinality_is_not_collapsed_to_496_statuses():
    ctx = _dental()
    ctx = replace(
        ctx,
        material_lines=ctx.material_lines
        + (replace(ctx.material_lines[0], material_line_id="M2"),),
    )
    batches = [fn("P1", ctx) for fn in ADAPTERS]
    assert sum(len(batch.evaluations) for batch in batches) == 477 + 19 * 2
    classifier = policy.BroadRuleClassifier(ctx, _test_attestation())
    dental = batches[0]
    findings = [
        classifier.classify(
            next(
                row
                for row in dental.evaluations
                if row.line_id == raw.material_line_id and row.rule_id == raw.rule_id
            ),
            raw,
        ).finding
        for raw in dental.legacy_rows
    ]
    assert len(findings) == 2
    assert len({row.finding_id for row in findings}) == 2


def test_multi_claim_observations_are_reused_without_calling_any_adapter(monkeypatch):
    ctx = _context()
    batches = [fn("P1", ctx) for fn in ADAPTERS]

    def forbidden(*args, **kwargs):
        pytest.fail("Classification called a broad adapter again")

    for fn in ADAPTERS:
        monkeypatch.setattr(import_module(fn.__module__), fn.__name__, forbidden)
    classifier = policy.BroadRuleClassifier(ctx)
    results = []
    for batch in batches:
        rows = {
            (r.claim_id, r.rule_id, getattr(r, "material_line_id", None)): r
            for r in batch.legacy_rows
        }
        results.extend(
            classifier.classify(row, rows.get((row.claim_id, row.rule_id, row.line_id)))
            for row in batch.evaluations
        )
    assert len(results) == len({r.evaluation.evaluation_id for r in results}) == 992
    for claim_id in ("C1", "C2"):
        assert (
            len({r.evaluation.rule_id for r in results if r.evaluation.claim_id == claim_id}) == 496
        )
    assert any(row.legacy_row is not None and row.disposition == "unavailable" for row in results)


def test_no_headers_has_honest_missing_status_and_no_invented_claim():
    ctx = replace(_single(), claims=(), material_lines=(), procedure_lines=())
    classifier = policy.BroadRuleClassifier(ctx)
    results = [
        classifier.classify(row, None) for fn in ADAPTERS for row in fn("P1", ctx).evaluations
    ]
    assert len(results) == 496
    assert all(
        row.disposition == "missing_inputs" and row.evaluation.claim_id is None for row in results
    )


@pytest.mark.parametrize(
    "change,match",
    [
        ({"rule_id": "unknown"}, "Unknown broad rule"),
        ({"patient_id": "foreign"}, "another patient/claim"),
        ({"claim_id": "foreign"}, "another patient/claim"),
        ({"line_kind": "claim", "line_id": None}, "incorrect claim/line scope"),
        ({"evaluation_status": "evaluated", "decision": None}, "needs a predicate decision"),
        ({"decision": "not_matched"}, "decision and legacy row disagree"),
    ],
)
def test_inconsistent_observation_cannot_be_classified(change, match):
    ctx = _dental()
    batch = evaluate_dental_rules("P1", ctx)
    with pytest.raises(ValueError, match=match):
        policy.BroadRuleClassifier(ctx).classify(
            replace(batch.evaluations[0], **change), batch.legacy_rows[0]
        )
