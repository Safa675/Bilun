"""Per-bill (claim-scoped) billing report: scoping + additivity.

Verifies that ``build_bill_claim_context`` partitions a patient's claim bundle
by ``claim_id`` and that ``compute_all_bill_billing_reports`` produces per-bill
reports whose recoverable totals sum to the patient-level aggregate.

The tests run on the cohort with the bills of two more patients filed under the first one (see
``multi_bill``), so the host has bills of three kinds; the claim tables are rewritten with polars into
a temporary copy. A guest patient's later bills come along with it (S2's control visit, S32).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil

import polars as pl
import pytest

from src.bilun.domain.claims import SUTClaimDataset, load_sut_claim_dataset
from src.bilun.domain.claims.config import DEFAULT_SYNTHETIC_CLAIMS_DIR
from tests.fixtures.synthetic_cohort import role

pytestmark = pytest.mark.unit

# Host patient, then the two patients whose bills are filed under the host. S1 and S2 carry
# recoverable revenue, S5 carries the cohort's only material lines, so the bills differ in what
# they hold (procedures and drugs, materials) and in how much they recover.
_HOST_ROLE = "showcase_S1"
_GUEST_ROLES = ("showcase_S2", "showcase_S5")


@dataclass(frozen=True)
class _MultiBill:
    dataset: SUTClaimDataset
    patient_id: str
    claim_ids: tuple[str, ...]


@pytest.fixture(scope="module")
def multi_bill(tmp_path_factory: pytest.TempPathFactory) -> _MultiBill:
    """The committed cohort with the guest patients' bills filed under the host patient."""
    host = role(_HOST_ROLE)
    guests = [role(name) for name in _GUEST_ROLES]
    guest_patients = [guest.patient_id for guest in guests]
    claims_dir: Path = tmp_path_factory.mktemp("multi_bill") / "claim_export"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)
    for path in sorted(claims_dir.glob("*.parquet")):
        frame = pl.read_parquet(path)
        if path.name == "patient_copay_profiles.parquet":
            # A patient has one copay profile: the guests' own profiles go.
            frame = frame.filter(~pl.col("patient_id").is_in(guest_patients))
        else:
            frame = frame.with_columns(
                pl.when(pl.col("patient_id").is_in(guest_patients))
                .then(pl.lit(host.patient_id))
                .otherwise(pl.col("patient_id"))
                .alias("patient_id")
            )
        frame.write_parquet(path)
    # every bill of the host and of its guests (a guest's later bills, such as S2's control visit, come along)
    headers = pl.read_parquet(DEFAULT_SYNTHETIC_CLAIMS_DIR / "claim_headers.parquet", columns=["patient_id", "claim_id"])
    claim_ids = headers.filter(pl.col("patient_id").is_in([host.patient_id, *guest_patients]))["claim_id"]
    assert {host.claim_id, *(guest.claim_id for guest in guests)} <= set(claim_ids)
    return _MultiBill(
        dataset=load_sut_claim_dataset(claims_dir, mode="real_claims"),
        patient_id=host.patient_id,
        claim_ids=tuple(sorted(claim_ids)),
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


class TestBillClaimContext:
    def test_scopes_lines_to_single_claim(self, multi_bill: _MultiBill) -> None:
        from src.bilun.domain.claims.patient_context import (
            build_bill_claim_context,
            build_patient_claim_context,
        )

        dataset, pid = multi_bill.dataset, multi_bill.patient_id
        patient_ctx = build_patient_claim_context(pid, dataset)
        assert patient_ctx is not None
        assert {c.claim_id for c in patient_ctx.claims} == set(multi_bill.claim_ids)

        bill_ctxs = []
        for claim_id in multi_bill.claim_ids:
            bill_ctx = build_bill_claim_context(pid, claim_id, dataset)
            assert bill_ctx is not None
            assert [c.claim_id for c in bill_ctx.claims] == [claim_id]
            assert all(p.claim_id == claim_id for p in bill_ctx.procedure_lines)
            assert all(m.claim_id == claim_id for m in bill_ctx.material_lines)
            assert all(d.claim_id == claim_id for d in bill_ctx.drug_lines)
            # Strictly fewer lines than the full patient bundle.
            assert len(bill_ctx.procedure_lines) < len(patient_ctx.procedure_lines)
            bill_ctxs.append(bill_ctx)

        # The bills partition the patient bundle: no line is lost, none is counted twice.
        for lines in ("procedure_lines", "material_lines", "drug_lines"):
            assert sum(len(getattr(c, lines)) for c in bill_ctxs) == len(
                getattr(patient_ctx, lines)
            ), lines
            assert getattr(patient_ctx, lines), f"{lines}: the fixture needs lines of this kind"

    def test_unknown_claim_returns_none(self, multi_bill: _MultiBill) -> None:
        from src.bilun.domain.claims.patient_context import build_bill_claim_context

        pid, dataset = multi_bill.patient_id, multi_bill.dataset
        assert build_bill_claim_context(pid, "F-DOES-NOT-EXIST", dataset) is None
        # A bill of another patient is not this patient's bill.
        assert build_bill_claim_context(pid, role("showcase_S3").claim_id, dataset) is None


@pytest.mark.xdist_group("billing_heavy")
class TestPerBillAdditivity:
    """Cohort-level orchestrator tests.

    All tests consume the same expensive orchestrator output (patient-level
    + bill-level billing reports across the cohort's patients and bills). The
    ``_orchestrator_outputs`` class-scoped fixture computes it ONCE for the
    class — without it, each test would re-run ``compute_all_bill_billing_reports``
    for identical work.

    ``xdist_group("billing_heavy")`` keeps these tests on a single xdist
    worker: they share the module-scope ``multi_bill`` dataset and the
    orchestrator is CPU-bound, so running them concurrently across workers
    would contend rather than speed up.
    """

    @pytest.fixture(scope="class")
    def _orchestrator_outputs(self, multi_bill: _MultiBill):
        from src.bilun.domain.billing import (
            compute_all_bill_billing_reports,
            compute_all_billing_reports,
        )

        cache = _cache_for(multi_bill.dataset)
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
            assert (
                abs(per_patient.get(pid, 0.0) - float(patient_report.total_recoverable_try)) < 0.01
            ), f"per-bill recoverable != patient total for {pid}"

    def test_multi_bill_patient_splits_recoverable(
        self, multi_bill: _MultiBill, _orchestrator_outputs
    ) -> None:
        patient_reports, bill_reports = _orchestrator_outputs
        pid = multi_bill.patient_id
        # The patient has several bills, and a report exists for each of its claims.
        assert len(multi_bill.dataset.claims_by_patient[pid]) == len(multi_bill.claim_ids) > 1
        keys = {k for k in bill_reports if k.startswith(f"{pid}::")}
        assert keys == {f"{pid}::{claim_id}" for claim_id in multi_bill.claim_ids}
        # The recoverable amount is split over the bills: at least two of them carry money, and
        # together they make the patient's total.
        amounts = [float(bill_reports[key].total_recoverable_try) for key in sorted(keys)]
        assert sum(amount > 0 for amount in amounts) >= 2
        assert abs(sum(amounts) - float(patient_reports[pid].total_recoverable_try)) < 0.01

    def test_public_projection_preserves_cohort_business_results_and_cached_nulls(
        self, _orchestrator_outputs
    ):
        """Real cohort patient-level and per-bill results survive JSON/cache projection.

        Sharing the orchestrator fixture adds no extra engine run. Unknown
        nested fields must stay private while money, uncertainty, identity,
        corrective actions and citation references keep their exact values.
        """
        from src.bilun.api.public_responses import project_public_response

        business_keys = {
            "patient_id",
            "claim_id",
            "severity",
            "exactness_status",
            "evaluation_status",
            "applicability_status",
            "unavailable_reason",
            "required_inputs_missing",
            "required_inputs",
            "missing_inputs",
            "confirmed_amount_try",
            "risk_amount",
            "money_semantics",
            "amount_status",
            "observed_amount_basis",
            "currency",
            "headline_relation",
            "detail",
            "recommended_action_tr",
            "clause_ref",
            "clause_key",
            "clause_coordinate",
            "sut_section",
            "sut_section_id",
        }
        business_blocks = {
            "opportunities",
            "recommendations",
            "findings",
            "evaluations",
            "violations",
            "rows",
            "required_documents",
            "corrective_steps_tr",
            "items",
            "entries",
        }

        def inject(value):
            if isinstance(value, dict):
                return {
                    **{key: inject(item) for key, item in value.items()},
                    "private_injected": {"domain_modules": ["secret.py"]},
                }
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
                            assert sum(row[status] for row in value.values()) == sum(
                                row[status] for row in public[key].values()
                            )
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
        null_payload = {
            "claim_reviews": {
                "available": False,
                "rows": [
                    {
                        "confirmed_amount_try": None,
                        "amount_status": "not_confirmed",
                        "observed_billed_amount_try": None,
                    },
                ],
            }
        }
        assert project_public_response(null_payload, "get_billing_report") == null_payload
