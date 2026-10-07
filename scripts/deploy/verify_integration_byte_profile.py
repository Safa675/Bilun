"""Finite CI byte closure only. This contract never grants release admission.

Historical clinical/source verifiers deliberately do not dispatch here. A
future deployment needs a separately reviewed source-computed semantic contract,
new current-law evidence, a fresh cache and a matching frontend/backend pair.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

CONTRACT = "bilun-integration-byte-only-mainf0-20261007-v1"
BASE_SHA = "f0b2f68f48dc5cedda6e0fa449faf7ec5e36faad"
BASE_TREE = "8464e30b2edfd46e14cd37efcf5f44922d1dfef4"
PRODUCT_SHA = "7616c78a6697be2b4ddec88fc0bda99ecd2658a4"
PRODUCT_TREE = "21b9b3b618854444fd7889b6b437530b0a770e96"
VERIFIER_PATH = "scripts/deploy/verify_integration_byte_profile.py"
TOOLING_PATHS = frozenset(
    {
        VERIFIER_PATH,
        "scripts/deploy/generate_integration_byte_profile.py",
        "tests/unit/deploy/integration_historical_sources.py",
        "tests/unit/deploy/fixtures/integration_historical_sources.json",
        "tests/unit/deploy/test_clinical_semantic_transition.py",
        "tests/unit/deploy/test_raw_report_transport_source_profile.py",
        "tests/unit/deploy/test_shared_interpreter_source_profile.py",
        "tests/unit/deploy/test_integration_byte_profile.py",
    }
)
PRODUCT_CLOSURE_SHA256 = '768993b0c50089bbb8a39f7c15200edecb377809d5ce9a7086cdecbf9feffc56'
REVIEWED_CHANGED_PATHS = ('.github/workflows/ci.yml',
 '.github/workflows/deploy.yml',
 '.github/workflows/sut-monitor.yml',
 'data/gazette/clinical_sources/mds_candidate_2026_10.json',
 'data/gazette/deltas/2026-10-02_clause_diff_inputs.json',
 'data/gazette/ingest_state.json',
 'data/gazette/prose_manifests/L1.4_material_bundling_encoded_manifest.json',
 'data/gazette/prose_rule_sources/material_bundling/3.1.1.yaml',
 'data/gazette/prose_rules/golden/material_bundling_gate_b.json',
 'data/gazette/prose_rules/material_bundling_prose.json',
 'data/gazette/raw/annex=EK-4A/effective_date=2026-10-02/MULGA_EK-4A_BEDELI_ODENECEK_ILACLAR_LISTESI_Yur._02.10.2026__EK-4A.parquet',
 'data/gazette/raw/annex=EK-4A/effective_date=unknown/EK-4A_BEDELI_ODENECEK_ILACLAR_LISTESI__EK-4A.parquet',
 'data/gazette/source_authority/clinical_versions.json',
 'data/gazette/source_authority/corpus_consumer_review_pr128.json',
 'data/gazette/source_evidence/adult_gh_closed_epiphysis_candidate.json',
 'data/gazette/sut_coverage_evidence.json',
 'data/gazette/version_manifest.parquet',
 'docs/core-system/algorithms_reference.md',
 'docs/gazette/pr-168-follow-up-proposals.md',
 'docs/gazette/rule-compiler.md',
 'docs/medula/medula_overlap_gaps.md',
 'frontend/scripts/capture-screens.mjs',
 'frontend/scripts/lib/capture-routes.mjs',
 'frontend/scripts/lib/capture-routes.test.mjs',
 'frontend/scripts/lib/numbers-parity.mjs',
 'frontend/scripts/lib/numbers-parity.test.mjs',
 'frontend/scripts/lib/page-probes.mjs',
 'frontend/scripts/lib/page-probes.test.mjs',
 'frontend/scripts/lib/probe-selftest.mjs',
 'frontend/scripts/lib/safe-message.mjs',
 'frontend/scripts/lib/safe-message.test.mjs',
 'frontend/src/app/globals.css',
 'frontend/src/app/page.test.tsx',
 'frontend/src/app/page.tsx',
 'frontend/src/app/patient/[id]/billing/page.test.tsx',
 'frontend/src/app/patient/[id]/page.panes.test.tsx',
 'frontend/src/app/patient/[id]/page.tsx',
 'frontend/src/components/chat/SutInlineAIPanel.lifecycle.test.tsx',
 'frontend/src/components/chat/SutInlineAIPanel.test.tsx',
 'frontend/src/components/chat/SutInlineAIPanel.tsx',
 'frontend/src/components/cohort/CohortFilterBar.test.tsx',
 'frontend/src/components/cohort/CohortFilterBar.tsx',
 'frontend/src/components/patient/BillPicker.tsx',
 'frontend/src/components/patient/OriginalBillView.tsx',
 'frontend/src/components/patient/PatientFinancialSummary.test.tsx',
 'frontend/src/components/patient/PatientFinancialSummary.tsx',
 'frontend/src/components/patient/SutBillingReportPresentation.test.tsx',
 'frontend/src/components/patient/SutBillingReportSections.test.tsx',
 'frontend/src/components/patient/SutPatientWorkspace.tsx',
 'frontend/src/components/patient/UnifiedComplianceFindingsTable.test.tsx',
 'frontend/src/components/patient/UnifiedComplianceFindingsTable.tsx',
 'frontend/src/components/patient/WaveAEvidenceSection.test.tsx',
 'frontend/src/components/patient/WaveAEvidenceSection.tsx',
 'frontend/src/components/patient/billing-report/BillingStrategySection.tsx',
 'frontend/src/components/patient/billing-report/BillingSummary.tsx',
 'frontend/src/components/patient/billing-report/BloodComponentUpliftSection.tsx',
 'frontend/src/components/patient/billing-report/CareSettingReviewSection.tsx',
 'frontend/src/components/patient/billing-report/CopayOptimizationSection.model.ts',
 'frontend/src/components/patient/billing-report/CopayOptimizationSection.tsx',
 'frontend/src/components/patient/billing-report/DrgPackageAdequacyReviewSection.tsx',
 'frontend/src/components/patient/billing-report/DrgUpliftSection.tsx',
 'frontend/src/components/patient/billing-report/DrugIndicationReviewSection.tsx',
 'frontend/src/components/patient/billing-report/LabOptimizationSection.tsx',
 'frontend/src/components/patient/billing-report/MaterialUpliftSection.tsx',
 'frontend/src/components/patient/billing-report/MaterialsPreCheckSection.tsx',
 'frontend/src/components/patient/billing-report/MissingMoney.test.tsx',
 'frontend/src/components/patient/billing-report/OptionalOverrideSection.tsx',
 'frontend/src/components/patient/billing-report/ProcedureAddonUpliftSection.tsx',
 'frontend/src/components/patient/billing-report/ProcedureCaptureGapSection.tsx',
 'frontend/src/components/patient/billing-report/RecommendedActionsPanel.tsx',
 'frontend/src/components/patient/billing-report/SessionUpliftSection.test.tsx',
 'frontend/src/components/patient/billing-report/SessionUpliftSection.tsx',
 'frontend/src/components/patient/billing-report/SutOptimizationSection.tsx',
 'frontend/src/components/patient/billing-report/shared.tsx',
 'frontend/src/components/patient/views/AuditViewSection.tsx',
 'frontend/src/components/patient/views/ComplianceViewSection.test.tsx',
 'frontend/src/components/patient/views/ComplianceViewSection.tsx',
 'frontend/src/components/patient/views/PatientWorkspaceViews.tsx',
 'frontend/src/components/patient/views/RevenueViewSection.tsx',
 'frontend/src/components/shell/AppSidebar.test.tsx',
 'frontend/src/components/shell/AppSidebar.tsx',
 'frontend/src/components/shell/WorkspaceQuickOpen.test.tsx',
 'frontend/src/components/shell/WorkspaceSplitLayout.test.tsx',
 'frontend/src/components/shell/WorkspaceSplitLayout.tsx',
 'frontend/src/components/skeletons/SutSkeletons.tsx',
 'frontend/src/components/tables/PatientInvoiceTable.test.tsx',
 'frontend/src/components/tables/PatientInvoiceTable.tsx',
 'frontend/src/components/tabs/SUTCompliance.tsx',
 'frontend/src/components/tabs/SUTPatients.tsx',
 'frontend/src/components/tabs/SUTRevenue.tsx',
 'frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.tsx',
 'frontend/src/components/tabs/sut/operations/MedulaRejectionQueueTab.tsx',
 'frontend/src/components/tabs/sut/optimizer/RevenueRecoverySummary.test.tsx',
 'frontend/src/components/tabs/sut/optimizer/RevenueRecoverySummary.tsx',
 'frontend/src/components/tabs/sut/optimizer/SUTOptimizerTab.test.tsx',
 'frontend/src/components/tabs/sut/optimizer/SUTOptimizerTab.tsx',
 'frontend/src/components/tabs/sut/sections/AdultGhClinicalDraft.tsx',
 'frontend/src/components/tabs/sut/sections/ClaimValidatorSection.tsx',
 'frontend/src/components/tabs/sut/sections/ClinicalMaterialInputs.tsx',
 'frontend/src/components/tabs/sut/sections/ClinicalRestrictionDetails.test.tsx',
 'frontend/src/components/tabs/sut/sections/ClinicalRestrictionDetails.tsx',
 'frontend/src/components/tabs/sut/sections/MdsClinicalDraft.tsx',
 'frontend/src/components/tabs/sut/sections/adultGhClinicalDraft.test.tsx',
 'frontend/src/components/tabs/sut/sections/clinicalFields.ts',
 'frontend/src/components/tabs/sut/sections/drugInputs.ts',
 'frontend/src/components/tabs/sut/sections/mdsAdultGhApplication.test.tsx',
 'frontend/src/components/tabs/sut/sections/mdsClinicalDraft.test.tsx',
 'frontend/src/lib/api/adultGhEvidence.ts',
 'frontend/src/lib/api/clinicalEvidence.ts',
 'frontend/src/lib/api/mdsClinicalDraft.ts',
 'frontend/src/lib/api/sut.ts',
 'frontend/src/lib/billingReportFields.test.ts',
 'frontend/src/lib/billingReportFields.ts',
 'frontend/src/lib/chatDockLayout.test.ts',
 'frontend/src/lib/chatDockLayout.ts',
 'frontend/src/lib/chatDockPreference.test.ts',
 'frontend/src/lib/chatDockPreference.ts',
 'frontend/src/lib/domains/sut.ts',
 'frontend/src/lib/patientRoute.ts',
 'frontend/src/lib/sutChatPageContext.ts',
 'frontend/src/lib/workspaceSubtabs.test.ts',
 'frontend/src/lib/workspaceSubtabs.ts',
 'frontend/src/lib/workspaceTabs.ts',
 'frontend/src/lib/workspaceViews.test.ts',
 'frontend/src/lib/workspaceViews.ts',
 'frontend/src/messages/en/billing.ts',
 'frontend/src/messages/en/chat.ts',
 'frontend/src/messages/en/cohort.ts',
 'frontend/src/messages/en/home.ts',
 'frontend/src/messages/en/operations.ts',
 'frontend/src/messages/en/optimizer.ts',
 'frontend/src/messages/en/patient.ts',
 'frontend/src/messages/en/sections.ts',
 'frontend/src/messages/tr/billing.ts',
 'frontend/src/messages/tr/chat.ts',
 'frontend/src/messages/tr/cohort.ts',
 'frontend/src/messages/tr/home.ts',
 'frontend/src/messages/tr/operations.ts',
 'frontend/src/messages/tr/optimizer.ts',
 'frontend/src/messages/tr/patient.ts',
 'frontend/src/messages/tr/sections.ts',
 'frontend/src/stores/navigationContext.test.tsx',
 'frontend/src/stores/navigationContext.tsx',
 'frontend/src/stores/navigationStore.test.ts',
 'frontend/src/stores/navigationStore.ts',
 'frontend/src/stores/storeInterfaces.ts',
 'frontend/tsconfig.json',
 'plans/clinical/mds-epoetin-clinical-draft.md',
 'plans/update/2026-10-05-ek4a-ingest-idempotence.md',
 'raw data/2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/2026.10.02-Değişiklik Tebliği '
 'İşlenmiş Güncel 2013 SUT/EK-4 LİSTELERİ/EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ.xlsx',
 'raw data/2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/2026.10.02-Değişiklik Tebliği '
 'İşlenmiş Güncel 2013 SUT/EK-4 LİSTELERİ/MÜLGA EK-4 LİSTELERİ/MÜLGA EK-4A BEDELİ ÖDENECEK İLAÇLAR '
 'LİSTESİ (Yür. 02.10.2026).xlsx',
 'reports/rule-engine-surfacing/2026-09-18-rule-surfacing-matrix.json',
 'reports/sut-expansion/adult-gh-closed-epiphysis-draft-review.md',
 'reports/sut-expansion/mds-gh-prerequisite-followup-review.md',
 'reports/sut-ingest/2026-10-05-ek4a-ingest-review.md',
 'reports/sut-ingest/2026-10-05-semantic-audit.json',
 'requirements-ci-build.in',
 'requirements-ci.lock',
 'scripts/deploy/generate_integration_byte_profile.py',
 'scripts/deploy/verify_integration_byte_profile.py',
 'scripts/sut/_common.py',
 'scripts/sut/build_curated_catalogs.py',
 'scripts/sut/catalogs/simple_materials.py',
 'scripts/sut/convert_xlsx_to_parquet.py',
 'scripts/sut/sut_clause_diff.py',
 'scripts/sut/sut_delta.py',
 'scripts/sut/sut_fetch.py',
 'scripts/sut/sut_ingest_state.py',
 'scripts/sut/sut_monitor.py',
 'src/bilun/api/adult_gh_clinical_draft.py',
 'src/bilun/api/mds_clinical_draft.py',
 'src/bilun/api/routes/optimization.py',
 'src/bilun/api/routes/patients.py',
 'src/bilun/api/schemas.py',
 'src/bilun/domain/billing/claim_materials.py',
 'src/bilun/domain/billing/cohort_summary.py',
 'src/bilun/domain/billing/lab_bill_merge.py',
 'src/bilun/domain/billing/patient_report.py',
 'src/bilun/domain/billing/priority.py',
 'src/bilun/domain/billing/recovery_summary.py',
 'src/bilun/domain/billing/types.py',
 'src/bilun/domain/claim_validation_v2.py',
 'src/bilun/domain/claims/adapter.py',
 'src/bilun/domain/claims/adult_gh.py',
 'src/bilun/domain/claims/mds_evidence.py',
 'src/bilun/domain/claims/models.py',
 'src/bilun/domain/claims/parsing/row_parsers.py',
 'src/bilun/domain/pricing/material_kdv.py',
 'src/bilun/domain/prose_rules/_drug_indication/clinical.py',
 'src/bilun/domain/prose_rules/_drug_indication/clinical_mds.py',
 'src/bilun/domain/prose_rules/adult_gh_draft.py',
 'src/bilun/domain/prose_rules/material_bundling.py',
 'src/bilun/domain/rules/exclusion_rules.py',
 'src/bilun/domain/sut/coverage_evidence.py',
 'src/bilun/shared/models.py',
 'tasks/lessons.md',
 'tasks/todo.md',
 'tests/integration/deploy/test_signed_transition_startup.py',
 'tests/unit/api/test_adult_gh_clinical_draft_api.py',
 'tests/unit/api/test_bill_billing_api.py',
 'tests/unit/api/test_mds_adult_gh_application.py',
 'tests/unit/api/test_mds_clinical_draft_api.py',
 'tests/unit/api/test_sut_patient_claims_api.py',
 'tests/unit/api/test_sut_schema_exactness.py',
 'tests/unit/deploy/fixtures/integration_historical_sources.json',
 'tests/unit/deploy/integration_historical_sources.py',
 'tests/unit/deploy/test_clinical_semantic_transition.py',
 'tests/unit/deploy/test_final_source_refresh_transition.py',
 'tests/unit/deploy/test_integration_byte_profile.py',
 'tests/unit/deploy/test_raw_report_transport.py',
 'tests/unit/deploy/test_raw_report_transport_source_profile.py',
 'tests/unit/deploy/test_shared_interpreter_source_profile.py',
 'tests/unit/domain/billing/test_billing_bugfixes.py',
 'tests/unit/domain/billing/test_claim_integration.py',
 'tests/unit/domain/billing/test_honest_gaps.py',
 'tests/unit/domain/billing/test_orchestrator_claim_cohort_flow.py',
 'tests/unit/domain/claims/test_mds_evidence_transport.py',
 'tests/unit/domain/pricing/test_material_kdv.py',
 'tests/unit/domain/prose_rules/test_adult_gh_closed_epiphysis.py',
 'tests/unit/domain/prose_rules/test_adult_gh_documentary_boundaries.py',
 'tests/unit/domain/prose_rules/test_clause_linking.py',
 'tests/unit/domain/prose_rules/test_drug_indication_4206.py',
 'tests/unit/domain/prose_rules/test_material_bundling.py',
 'tests/unit/domain/prose_rules/test_material_bundling_golden.py',
 'tests/unit/domain/prose_rules/test_mds_clinical_draft.py',
 'tests/unit/domain/prose_rules/test_mds_report_relationship_followup.py',
 'tests/unit/domain/sut/test_coverage_evidence.py',
 'tests/unit/domain/test_adult_gh_evidence.py',
 'tests/unit/domain/test_billing_strategy_exactness.py',
 'tests/unit/domain/test_patient_recovery_summaries.py',
 'tests/unit/scripts/test_curated_catalog_idempotence.py',
 'tests/unit/scripts/test_ek4a_source_admission.py',
 'tests/unit/scripts/test_ingest_state.py',
 'tests/unit/scripts/test_sut_clause_diff.py',
 'tests/unit/scripts/test_sut_delta.py',
 'tests/unit/scripts/test_sut_fetch.py',
 'tests/unit/scripts/test_sut_ingest_state.py',
 'tests/unit/scripts/test_sut_monitor.py',
 'tools/ci/Dockerfile',
 'tools/ci/laptop_runner.py',
 'tools/ci/runner-entrypoint.sh')
REVIEWED_TOOLING = {'scripts/deploy/generate_integration_byte_profile.py': ('100644',
                                                         'blob',
                                                         'c8f9572942a09683d46567dc9e9a40a6987580b5'),
 'tests/unit/deploy/fixtures/integration_historical_sources.json': ('100644',
                                                                    'blob',
                                                                    '368507b183c6595a71a182b1845be6c8db2b24e2'),
 'tests/unit/deploy/integration_historical_sources.py': ('100644',
                                                         'blob',
                                                         '8c12447f75895616ce17216adf28c59912ef3439'),
 'tests/unit/deploy/test_clinical_semantic_transition.py': ('100644',
                                                            'blob',
                                                            '66f76715df185e0db5ddfc3c4ba6ad8558fae63f'),
 'tests/unit/deploy/test_integration_byte_profile.py': ('100644',
                                                        'blob',
                                                        '0320c9cc07aa62e35b785c175ef782c0d6bc6e8b'),
 'tests/unit/deploy/test_raw_report_transport_source_profile.py': ('100644',
                                                                   'blob',
                                                                   '2bb8a654e5355bba6b6e491c7b9faf3490ca58b7'),
 'tests/unit/deploy/test_shared_interpreter_source_profile.py': ('100644',
                                                                 'blob',
                                                                 '76c6637f027457792a4b15cb68a11e2babbefb24')}
REVIEWED_SELF_SHA256 = "6cedd7f634c49fdf06730a2e186c631be0da57bd959b49d9c2e664e08d97f6e3"
_SELF_SLOT = re.compile(rb'(?m)^REVIEWED_SELF_SHA256 = "([0-9a-f]{64})"$')
_SHA = re.compile(r"[0-9a-f]{40}")


def git(checkout: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(checkout), *arguments], check=True, capture_output=True
    ).stdout


def disk_entry(path: Path) -> tuple[str, str, str]:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o111:
        raise ValueError("Byte-only tooling must be a regular non-executable file")
    body = path.read_bytes()
    blob = hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest()
    return "100644", "blob", blob


def product_closure(checkout: Path, sha: str) -> bytes:
    return b"\0".join(
        row
        for row in git(checkout, "ls-tree", "-r", "-z", sha).split(b"\0")
        if row and os.fsdecode(row.split(b"\t", 1)[1]) not in TOOLING_PATHS
    )


def _entry(checkout: Path, sha: str, path: str) -> tuple[str, str, str]:
    rows = [row for row in git(checkout, "ls-tree", "-z", sha, "--", path).split(b"\0") if row]
    if len(rows) != 1 or rows[0].split(b"\t", 1)[1] != os.fsencode(path):
        raise ValueError("Byte-only tooling path is absent or ambiguous")
    fields = tuple(rows[0].split(b"\t", 1)[0].decode().split())
    if len(fields) != 3:
        raise ValueError("Byte-only tooling entry is malformed")
    return fields


def verify_self_source(source: bytes) -> None:
    matches = list(_SELF_SLOT.finditer(source))
    if len(matches) != 1 or matches[0].group(1).decode() != REVIEWED_SELF_SHA256:
        raise ValueError("Byte-only self pin has an unknown literal slot")
    start, end = matches[0].span(1)
    normalized = source[:start] + b"0" * 64 + source[end:]
    if hashlib.sha256(normalized).hexdigest() != REVIEWED_SELF_SHA256:
        raise ValueError("Byte-only verifier differs from reviewed source bytes")


def _changed(checkout: Path, before: str, after: str) -> set[str]:
    return {
        os.fsdecode(row)
        for row in git(
            checkout, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", before, after
        ).split(b"\0")
        if row
    }


def verify_candidate_history(checkout: Path, expected_sha: str) -> dict:
    if (
        not isinstance(expected_sha, str)
        or not _SHA.fullmatch(expected_sha)
        or git(checkout, "rev-parse", "HEAD").decode().strip() != expected_sha
    ):
        raise ValueError("Byte-only candidate differs from explicit immutable head")
    if git(checkout, "rev-parse", BASE_SHA + "^{tree}").decode().strip() != BASE_TREE:
        raise ValueError("Byte-only profile requires the exact main parent tree")
    parents = git(checkout, "show", "-s", "--format=%P", expected_sha).decode().split()
    if parents == [BASE_SHA]:
        form = "normal_squash"
        if _changed(checkout, BASE_SHA, expected_sha) != set(REVIEWED_CHANGED_PATHS):
            raise ValueError("Byte-only squash differs from the exact reviewed path transition")
    elif parents == [PRODUCT_SHA]:
        form = "reviewed_product_plus_tooling"
        if (
            git(checkout, "rev-parse", PRODUCT_SHA + "^{tree}").decode().strip() != PRODUCT_TREE
            or _changed(checkout, PRODUCT_SHA, expected_sha) != TOOLING_PATHS
        ):
            raise ValueError("Byte-only feature head differs from exact product/tooling transition")
    else:
        raise ValueError("Byte-only candidate has unreviewed parents or intermediate history")
    if (
        hashlib.sha256(product_closure(checkout, expected_sha)).hexdigest()
        != PRODUCT_CLOSURE_SHA256
    ):
        raise ValueError("Byte-only candidate changes the frozen whole-product closure")
    if set(REVIEWED_TOOLING) != TOOLING_PATHS - {VERIFIER_PATH}:
        raise ValueError("Byte-only profile has an unknown tooling pin roster")
    for path, expected in REVIEWED_TOOLING.items():
        if _entry(checkout, expected_sha, path) != expected:
            raise ValueError("Byte-only candidate changes reviewed tooling mode/type/blob")
    if _entry(checkout, expected_sha, VERIFIER_PATH)[:2] != ("100644", "blob"):
        raise ValueError("Byte-only verifier has an unreviewed mode/type")
    verify_self_source(git(checkout, "show", f"{expected_sha}:{VERIFIER_PATH}"))
    return {
        "contract": CONTRACT,
        "candidate_sha": expected_sha,
        "history_form": form,
        "product_closure_sha256": PRODUCT_CLOSURE_SHA256,
        "deployment_admitted": False,
        "clinical_source_extended": False,
        "semantic_release_admission": "blocked",
    }


def verify(checkout: Path, expected_sha: str) -> dict:
    checkout = checkout.resolve(strict=True)
    if Path(__file__).resolve(strict=True) != checkout / VERIFIER_PATH:
        raise ValueError("Byte-only verifier must execute from the exact candidate checkout")
    if git(checkout, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Byte-only checkout is not clean")
    result = verify_candidate_history(checkout, expected_sha)
    for path in TOOLING_PATHS:
        if disk_entry(checkout / path) != _entry(checkout, expected_sha, path):
            raise ValueError("Byte-only executing tooling differs from candidate Git bytes")
    verify_self_source(Path(__file__).read_bytes())
    if git(checkout, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Byte-only checkout changed during verification")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.checkout, args.expected_sha), sort_keys=True))


if __name__ == "__main__":
    main()
