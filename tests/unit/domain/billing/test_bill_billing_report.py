"""Per-bill (claim-scoped) billing report: scoping + additivity.

Verifies that ``build_bill_claim_context`` partitions a patient's claim bundle
by ``claim_id`` and that ``compute_all_bill_billing_reports`` produces per-bill
reports whose recoverable totals sum to the patient-level aggregate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import json

import polars as pl
import pytest

pytestmark = pytest.mark.unit

try:
    from src.bilun.domain.claims.loader import load_sut_claim_dataset

    _DATASET = load_sut_claim_dataset()
except Exception:  # pragma: no cover - dataset optional in some envs
    _DATASET = None

_needs_dataset = pytest.mark.skipif(
    _DATASET is None, reason="synthetic SUT claim dataset not available"
)


def _cache_for(dataset) -> dict:
    pids = sorted(dataset.claims_by_patient)
    return {
        "sut_claim_dataset": dataset,
        "sut_by_pid": {pid: {} for pid in pids},
        "patient_alerts_cache": {
            "patients": [
                {
                    "patient_id": pid,
                    "copay_exemption": {
                        "exempt": False,
                        "n_qualifying": 0,
                        "qualifying_diagnoses": [],
                    },
                    "icd10_chapters": [],
                }
                for pid in pids
            ]
        },
        "lab_df_pl": pl.DataFrame(),
    }


@_needs_dataset
class TestBillClaimContext:
    def test_scopes_lines_to_single_claim(self) -> None:
        from src.bilun.domain.claims.patient_context import (
            build_bill_claim_context,
            build_patient_claim_context,
        )

        pid = next(
            p for p, claims in _DATASET.claims_by_patient.items() if len(claims) > 1
        )
        patient_ctx = build_patient_claim_context(pid, _DATASET)
        claim_id = patient_ctx.claims[0].claim_id

        bill_ctx = build_bill_claim_context(pid, claim_id, _DATASET)
        assert bill_ctx is not None
        assert [c.claim_id for c in bill_ctx.claims] == [claim_id]
        assert all(p.claim_id == claim_id for p in bill_ctx.procedure_lines)
        assert all(m.claim_id == claim_id for m in bill_ctx.material_lines)
        assert all(d.claim_id == claim_id for d in bill_ctx.drug_lines)
        # Strictly fewer (or equal) lines than the full patient bundle.
        assert len(bill_ctx.procedure_lines) <= len(patient_ctx.procedure_lines)

    def test_unknown_claim_returns_none(self) -> None:
        from src.bilun.domain.claims.patient_context import build_bill_claim_context

        pid = next(iter(_DATASET.claims_by_patient))
        assert build_bill_claim_context(pid, "F-DOES-NOT-EXIST", _DATASET) is None


@_needs_dataset
@pytest.mark.xdist_group("billing_heavy")
class TestPerBillAdditivity:
    """Cohort-level orchestrator tests.

    Both tests consume the same expensive orchestrator output (patient-level
    + bill-level billing reports across all 50 synthetic patients, ~68s). The
    ``_orchestrator_outputs`` class-scoped fixture computes it ONCE for the
    class — without it, the second test re-ran ``compute_all_bill_billing_reports``
    (~20s) for identical work.

    ``xdist_group("billing_heavy")`` keeps these tests on a single xdist
    worker: they share the module-scope ``_DATASET`` and the orchestrator is
    CPU-bound, so running them concurrently across workers would contend
    rather than speed up.
    """

    @pytest.fixture(scope="class")
    def _orchestrator_outputs(self):
        from src.bilun.domain.billing import (
            compute_all_bill_billing_reports,
            compute_all_billing_reports,
        )

        cache = _cache_for(_DATASET)
        patient_reports, _ = compute_all_billing_reports(cache)
        bill_reports = compute_all_bill_billing_reports(cache)
        return patient_reports, bill_reports

    def test_recoverable_sums_to_patient_total(self, _orchestrator_outputs) -> None:
        patient_reports, bill_reports = _orchestrator_outputs

        assert bill_reports, "expected at least one per-bill report"
        # every bill key is "{pid}::{claim_id}"
        assert all("::" in key for key in bill_reports)

        per_patient = defaultdict(float)
        for key, report in bill_reports.items():
            per_patient[key.split("::", 1)[0]] += report.total_recoverable_try

        for pid, patient_report in patient_reports.items():
            assert abs(
                per_patient.get(pid, 0.0) - float(patient_report.total_recoverable_try)
            ) < 0.01, f"per-bill recoverable != patient total for {pid}"

    def test_multi_bill_patient_splits_recoverable(self, _orchestrator_outputs) -> None:
        _, bill_reports = _orchestrator_outputs
        # At least one patient should have multiple bills.
        multi = [p for p, c in _DATASET.claims_by_patient.items() if len(c) > 1]
        assert multi
        # Reports exist for each of that patient's claims.
        pid = multi[0]
        keys = {k for k in bill_reports if k.startswith(f"{pid}::")}
        assert len(keys) == len(_DATASET.claims_by_patient[pid])

    def test_public_projection_preserves_cohort_business_results_and_cached_nulls(self, _orchestrator_outputs):
        """Real 50-patient and per-bill results survive JSON/cache projection.

        Sharing the orchestrator fixture adds no extra engine run. Unknown
        nested fields must stay private while money, uncertainty, identity,
        corrective actions and citation references keep their exact values.
        """
        from src.bilun.api.public_responses import project_public_response

        business_keys = {
            "patient_id", "claim_id", "severity", "exactness_status", "evaluation_status",
            "applicability_status", "unavailable_reason", "required_inputs_missing",
            "required_inputs", "missing_inputs", "confirmed_amount_try", "risk_amount",
            "money_semantics", "amount_status", "observed_amount_basis", "currency",
            "headline_relation", "detail", "recommended_action_tr", "clause_ref",
            "clause_key", "clause_coordinate", "sut_section", "sut_section_id",
        }
        business_blocks = {"opportunities", "recommendations", "findings", "evaluations",
                           "violations", "rows", "required_documents", "corrective_steps_tr",
                           "items", "entries"}

        def inject(value):
            if isinstance(value, dict):
                return {**{key: inject(item) for key, item in value.items()}, "private_injected": {"domain_modules": ["secret.py"]}}
            if isinstance(value, list):
                return [inject(item) for item in value]
            return value

        def assert_business(raw, public, path=""):
            if isinstance(raw, dict):
                for key, value in raw.items():
                    # Coverage inventories and private file provenance are
                    # intentionally omitted, not financial result records.
                    if key in {"coverage_scope", "specialty_coverage_scope", "data_source"}:
                        continue
                    if key == "by_group":
                        for status in ("evaluated", "missing_inputs", "unavailable"):
                            assert sum(row[status] for row in value.values()) == sum(row[status] for row in public[key].values())
                        continue
                    if key in business_blocks:
                        assert key in public, path + "." + key
                        assert_business(value, public[key], path + "." + key)
                    elif key in business_keys or key.endswith("_try"):
                        assert key in public, path + "." + key
                        assert public[key] == value, path + "." + key
                    elif key in public:
                        assert_business(value, public[key], path + "." + key)
            elif isinstance(raw, list):
                assert len(raw) == len(public), path
                for index, (left, right) in enumerate(zip(raw, public, strict=True)):
                    assert_business(left, right, path + f"[{index}]")

        patient_reports, bill_reports = _orchestrator_outputs
        for reports in (patient_reports, bill_reports):
            for report in reports.values():
                raw = json.loads(json.dumps(asdict(report)))
                raw.pop("wavea_evidence_detail", None)
                result = project_public_response(raw, "get_billing_report")
                assert set(result) == set(raw), "Every report section remains available"
                assert_business(raw, result)
                assert project_public_response(inject(raw), "get_billing_report") == result
                assert "private_injected" not in raw
        null_payload = {"claim_reviews": {"available": False, "rows": [
            {"confirmed_amount_try": None, "amount_status": "not_confirmed", "observed_billed_amount_try": None},
        ]}}
        assert project_public_response(null_payload, "get_billing_report") == null_payload
