"""Exact BILUN claim-line loading, configuration, and aggregation.

The package exposes typed rows, runtime validation, and exact per-claim /
per-patient totals for billing-native BILUN claim datasets.
"""

from __future__ import annotations

from src.bilun.domain.claims.config import (
    DEFAULT_SYNTHETIC_CLAIMS_DIR,
    DEFAULT_SYNTHETIC_CLEAN_DIR,
    REAL_CLAIMS_MODE,
    SUTDataSourceConfig,
    SUTDataSourceConfigError,
    SUTDataSourceMetadata,
    SYNTHETIC_DEMO_MODE,
    resolve_sut_claims_dir,
    resolve_sut_data_source,
)
from src.bilun.domain.claims.errors import ClaimValidationError
from src.bilun.domain.claims.loader import SUTClaimDataset, load_sut_claim_dataset, read_claim_tables
from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    ClaimTotals,
    DrugClaimLine,
    ExpectedRuleOutput,
    MaterialClaimLine,
    PatientSUTClaimTotals,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import (
    CohortClaimContext,
    PatientClaimContext,
    build_cohort_claim_context,
    build_patient_claim_context,
)
from src.bilun.domain.claims.provenance import (
    UNAVAILABLE_BILUN_DATA_MODE,
    attach_bilun_data_source_metadata,
    configured_bilun_data_source_metadata,
    normalize_bilun_data_source_metadata,
    unavailable_bilun_data_source_metadata,
)

__all__ = [
    "ClaimHeader",
    "ClaimDiagnosis",
    "ClaimTotals",
    "ClaimValidationError",
    "CohortClaimContext",
    "DEFAULT_SYNTHETIC_CLAIMS_DIR",
    "DEFAULT_SYNTHETIC_CLEAN_DIR",
    "DrugClaimLine",
    "ExpectedRuleOutput",
    "MaterialClaimLine",
    "PatientSUTClaimTotals",
    "PatientClaimContext",
    "ProcedureClaimLine",
    "REAL_CLAIMS_MODE",
    "SUTDataSourceConfig",
    "SUTDataSourceConfigError",
    "SUTDataSourceMetadata",
    "SUTClaimDataset",
    "SYNTHETIC_DEMO_MODE",
    "UNAVAILABLE_BILUN_DATA_MODE",
    "attach_bilun_data_source_metadata",
    "build_cohort_claim_context",
    "build_patient_claim_context",
    "configured_bilun_data_source_metadata",
    "load_sut_claim_dataset",
    "normalize_bilun_data_source_metadata",
    "read_claim_tables",
    "resolve_sut_claims_dir",
    "resolve_sut_data_source",
    "unavailable_bilun_data_source_metadata",
]
