"""Persistent storage layer for BILUN analytics builds.

Wraps a DuckDB database and exposes the build lifecycle, schema DDL,
generic table I/O, patient alerts subsystem, patient meta reads,
and hashing utilities used for build identity.
"""

from ._internal import (
    BUILD_COMPLETE,
    BUILD_FAILED,
    BUILD_PENDING,
    BUILD_RUNNING,
    BUILD_SUPERSEDED,
)
from .builds import (
    cleanup_build_lifecycle,
    complete_build,
    complete_and_activate_build,
    create_build,
    fail_build,
    get_active_build_id,
    get_previous_build_id,
    prune_old_builds,
    set_active_build,
)
from .connection import BuildInfo, connect
from .hashing import config_hash_from_env, source_hash_from_files
from .patient_alerts import (
    ensure_patient_alert_summary,
    ensure_patient_alert_tables,
    has_patient_alert_tables,
    read_patient_alert_rows_page,
    read_patient_alerts_summary,
    write_patient_alert_tables,
)
from .patient_meta import (
    read_all_patient_ids,
    read_patient_detail,
    read_patient_diagnoses,
    read_patient_meta,
    read_patient_meta_by_ids,
    read_patient_outcome_base,
    read_patient_outcome_expensive,
    search_patient_ids,
)
from .schema import init_schema
from .tables import (
    has_json_payload,
    has_json_payload_rows,
    read_json_payload,
    read_json_payload_entry,
    read_json_payload_row,
    read_validation_payload,
    upsert_single_json_table,
    write_json_payload_rows,
    write_json_payload_rows_serialized,
    write_dataframe,
    write_validation_payload,
)

__all__ = [
    # Build status constants
    "BUILD_PENDING",
    "BUILD_RUNNING",
    "BUILD_COMPLETE",
    "BUILD_FAILED",
    "BUILD_SUPERSEDED",
    # Connection
    "BuildInfo",
    "connect",
    # Schema
    "init_schema",
    # Build lifecycle
    "create_build",
    "cleanup_build_lifecycle",
    "complete_build",
    "complete_and_activate_build",
    "fail_build",
    "set_active_build",
    "get_active_build_id",
    "get_previous_build_id",
    "prune_old_builds",
    # Generic table I/O
    "upsert_single_json_table",
    "write_dataframe",
    "write_validation_payload",
    "read_validation_payload",
    "read_json_payload",
    "has_json_payload",
    "has_json_payload_rows",
    "read_json_payload_entry",
    "read_json_payload_row",
    "write_json_payload_rows",
    "write_json_payload_rows_serialized",
    # Patient alerts
    "write_patient_alert_tables",
    "read_patient_alerts_summary",
    "ensure_patient_alert_summary",
    "has_patient_alert_tables",
    "ensure_patient_alert_tables",
    "read_patient_alert_rows_page",
    # Patient meta reads
    "read_patient_meta",
    "read_patient_meta_by_ids",
    "read_patient_diagnoses",
    "read_all_patient_ids",
    "search_patient_ids",
    "read_patient_detail",
    "read_patient_outcome_base",
    "read_patient_outcome_expensive",
    # Hashing
    "source_hash_from_files",
    "config_hash_from_env",
]
