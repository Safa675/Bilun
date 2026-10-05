"""Read-only same-input legacy parity and Wave A cache evidence checkpoint.

This is deliberately not a release authorization. It inventories every
patient, bill, and persisted evidence row and names the remaining broad-rule,
input-scope, and source/rollback gates. A later checkpoint must independently
derive claim/material scopes from the pinned input Parquets before it can
remove those blockers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb

from scripts.deploy.verify_candidate_cache import _CODE_SHA, _candidate_db_hash, _parse_json
from scripts.deploy.verify_same_input import (
    normalize_attested_data_source,
    verify_same_input_rosters,
)
from scripts.deploy.verify_candidate_scopes import (
    verify_pinned_claim_scopes,
    verify_pinned_evidence_lines,
)
from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.billing.cohort_compliance import build_cohort_compliance_index
from src.bilun.domain.billing.focused_rule_projection import FOCUSED_RULE_SPECS
from src.bilun.domain.billing.wavea_full_evidence import (
    FULL_EVIDENCE_SCHEMA_VERSION,
    FULL_ROSTER_VERSION,
    build_full_wavea_evidence_index,
    validate_full_wavea_evidence_detail,
)
from src.bilun.domain.billing.wavea_evidence import (
    DEFAULT_DETAIL_LIMIT,
    EVIDENCE_SCHEMA_VERSION,
    ORIGINAL_FIVE_RULE_IDS,
    build_wavea_evidence_index,
    original_five_report_payload,
    validate_wavea_evidence_detail,
)

_PATIENT_TABLES = (
    "patient_billing_report_rows",
    "patient_detail_cache",
    "patient_outcome_base",
)
_SINGLETON_TABLES = (
    "cohort_optimization_summary",
    "patient_alerts_summary",
    "cohort_recovery_summary",
)
_ROW_TABLES = (
    "cohort_sut_summary",
    "validation_payload",
    "patient_meta",
    "cohort_sut_exposure",
    "patient_alerts_payload",
    "patient_diagnoses",
    "patient_alert_rows",
    "patient_billing_reports",
)
_NEW_REPORT_FIELDS = frozenset(
    {"claim_reviews", "claim_advisories", "financial_findings", "wavea_coverage"}
)
_EVIDENCE_TABLES = (
    "wavea_evidence_detail", "wavea_bill_evidence_detail", "wavea_evidence_index",
)
_ORIGINAL_FIVE_CONTRACT = "original-five"


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_metadata(con: duckdb.DuckDBPyConnection, build_id: str) -> dict[str, str]:
    rows = con.execute(
        "SELECT status, build_scope, source_hash, config_hash, code_sha, schema_version "
        "FROM build_meta WHERE build_id = ?",
        [build_id],
    ).fetchall()
    if len(rows) != 1 or rows[0][0:2] != ("complete", "bilun"):
        raise ValueError("Selected baseline/candidate build is not complete in Bilun scope")
    if any(not isinstance(value, str) or not value for value in rows[0][2:]):
        raise ValueError("Selected build lacks input/config identity")
    if not _CODE_SHA.fullmatch(rows[0][4]):
        raise ValueError("Selected build has malformed code SHA")
    if rows[0][5] != "v1":
        raise ValueError("Selected build has unknown or incomplete cache schema version")
    return {"source_hash": rows[0][2], "config_hash": rows[0][3], "code_sha": rows[0][4]}


def _payload_rows(
    con: duckdb.DuckDBPyConnection, table: str, build_id: str
) -> dict[str, dict[str, Any]]:
    if table not in (
        *_PATIENT_TABLES,
        "patient_bill_billing_report_rows",
        "wavea_evidence_detail",
        "wavea_bill_evidence_detail",
    ):
        raise ValueError(f"Unsupported patient payload table: {table}")
    cursor = con.execute(
        f'SELECT patient_id, payload_json FROM "{table}" WHERE build_id = ? ORDER BY patient_id',
        [build_id],
    )
    rows: dict[str, dict[str, Any]] = {}
    while batch := cursor.fetchmany(256):
        for key, raw in batch:
            if not isinstance(key, str) or not key or key in rows:
                raise ValueError(f"Malformed or duplicate {table} key")
            payload = _parse_json(raw, context=f"{table}.{key}")
            if not isinstance(payload, dict):
                raise ValueError(f"Malformed {table} payload")
            rows[key] = payload
    return rows


def _singleton(con: duckdb.DuckDBPyConnection, table: str, build_id: str) -> dict[str, Any]:
    if table not in (*_SINGLETON_TABLES, "cohort_compliance_index", "wavea_evidence_index"):
        raise ValueError(f"Unsupported singleton table: {table}")
    rows = con.execute(
        f'SELECT payload_json FROM "{table}" WHERE build_id = ?', [build_id]
    ).fetchall()
    if len(rows) != 1:
        raise ValueError(f"Expected one {table} row for selected build")
    payload = _parse_json(rows[0][0], context=table)
    if not isinstance(payload, dict):
        raise ValueError(f"Malformed {table} payload")
    return payload


def _legacy_report(payload: dict[str, Any]) -> dict[str, Any]:
    if "wavea_evidence_detail" in payload:
        raise ValueError("Exhaustive Wave A detail leaked into default billing report")
    return original_five_report_payload(
        {key: value for key, value in payload.items() if key not in _NEW_REPORT_FIELDS}
    )


def _baseline_has_only_original_five(payload: dict[str, Any]) -> bool:
    block = payload.get("claim_compliance")
    if not isinstance(block, dict):
        return False
    return all(
        isinstance(rows, list)
        and all(
            isinstance(row, dict) and row.get("rule_id") in ORIGINAL_FIVE_RULE_IDS for row in rows
        )
        for rows in (block.get("findings"), block.get("evaluations"))
    )


def _without_data_source(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "data_source"}


def _legacy_row_table(con: duckdb.DuckDBPyConnection, table: str, build_id: str) -> list[dict]:
    if table not in _ROW_TABLES:
        raise ValueError("Unsupported legacy row table")
    columns = [row[1] for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()]
    if "build_id" not in columns:
        raise ValueError(f"Legacy {table} lacks build identity")
    fields = [column for column in columns if column != "build_id"]
    quoted = ", ".join(f'"{field}"' for field in fields)
    cursor = con.execute(f'SELECT {quoted} FROM "{table}" WHERE build_id = ?', [build_id])
    rows: list[dict] = []
    while batch := cursor.fetchmany(256):
        for values in batch:
            row = dict(zip(fields, values, strict=True))
            for column in fields:
                if column.endswith("_json") and row[column] is not None:
                    row[column] = _parse_json(row[column], context=f"{table}.{column}")
            rows.append(row)
    return sorted(rows, key=lambda row: _digest(row))


def _baseline_contract(con: duckdb.DuckDBPyConnection, build_id: str) -> str:
    """Recognize persisted contracts, never infer a version from API visibility."""
    versions = set()
    for table in ("patient_billing_report_rows", "patient_bill_billing_report_rows"):
        reports = _payload_rows(con, table, build_id)
        if not reports:
            raise ValueError("Baseline patient/bill contract is incomplete")
        for report in reports.values():
            if "wavea_evidence_detail" in report:
                raise ValueError("Exhaustive Wave A detail leaked into default billing report")
            fields = _NEW_REPORT_FIELDS & report.keys()
            if not fields:
                if not _baseline_has_only_original_five(report):
                    raise ValueError("Baseline claim compliance is not the original-five contract")
                versions.add(_ORIGINAL_FIVE_CONTRACT)
            else:
                coverage = report.get("wavea_coverage")
                if (
                    fields != _NEW_REPORT_FIELDS
                    or not isinstance(coverage, dict)
                    or coverage.get("schema_version") != FULL_EVIDENCE_SCHEMA_VERSION
                ):
                    raise ValueError("Baseline has an unknown or incomplete Wave A contract")
                versions.add(FULL_EVIDENCE_SCHEMA_VERSION)
    if len(versions) != 1:
        raise ValueError("Baseline patient/bill schema versions are mixed")
    version = versions.pop()
    if version == _ORIGINAL_FIVE_CONTRACT:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        for table in _EVIDENCE_TABLES:
            if table in tables and con.execute(
                f'SELECT count(*) FROM "{table}" WHERE build_id = ?', [build_id]
            ).fetchone()[0]:
                raise ValueError("Original-five baseline contains mixed Wave A evidence")
    return version


def _current_content_parity(
    baseline: duckdb.DuckDBPyConnection,
    baseline_build: str,
    candidate: duckdb.DuckDBPyConnection,
    candidate_build: str,
    *,
    same_input: dict[str, Any] | None = None,
    clinical_transition: Any = None,
) -> tuple[dict[str, str], dict[str, dict[str, Any]], int]:
    """Compare all current payloads, including every unbounded evidence row.

    Only evidence's selected, independently checked top-level build identity
    may differ. Source paths require the separate byte-attested input proof;
    all other source metadata and nested identity fields remain exact.
    """
    if _baseline_contract(candidate, candidate_build) != FULL_EVIDENCE_SCHEMA_VERSION:
        raise ValueError("Current baseline/candidate schema versions differ")
    digests = {}
    reports = {}
    bill_count = 0
    for table in (
        *_PATIENT_TABLES, "patient_bill_billing_report_rows",
        "cohort_compliance_index", *_SINGLETON_TABLES, *_ROW_TABLES, *_EVIDENCE_TABLES,
    ):
        old_schema = baseline.execute(f"PRAGMA table_info('{table}')").fetchall()
        new_schema = candidate.execute(f"PRAGMA table_info('{table}')").fetchall()
        if not old_schema or old_schema != new_schema:
            raise ValueError(f"Current {table} schema differs or is missing")
        if table not in _ROW_TABLES:
            expected = ["build_id", "payload_json"] if table in (
                "cohort_compliance_index", *_SINGLETON_TABLES, "wavea_evidence_index",
            ) else ["build_id", "patient_id", "payload_json"]
            if [row[1] for row in old_schema] != expected:
                raise ValueError(f"Current {table} has unverified columns")
        values = []
        for con, build_id, side in (
            (baseline, baseline_build, "baseline"),
            (candidate, candidate_build, "candidate"),
        ):
            if table in _ROW_TABLES:
                value = _legacy_row_table(con, table, build_id)
            elif table in ("cohort_compliance_index", *_SINGLETON_TABLES, "wavea_evidence_index"):
                value = _singleton(con, table, build_id)
            else:
                value = _payload_rows(con, table, build_id)
            if table == "patient_billing_report_rows" and side == "candidate":
                reports = value
            if table == "patient_bill_billing_report_rows" and side == "candidate":
                bill_count = len(value)
            if table == "cohort_compliance_index":
                expected_cohort = build_cohort_compliance_index(
                    _payload_rows(con, "patient_billing_report_rows", build_id)
                )
                if _digest(_without_data_source(value)) != _digest(expected_cohort):
                    raise ValueError(f"Current {side} cohort compliance disagrees with patient rows")
            if clinical_transition is not None:
                from scripts.deploy.verify_source_refresh_transition import normalize_transition_content
                value = normalize_transition_content(
                    table, value, side=side, proof=clinical_transition,
                    patient_reports=(_payload_rows(con, "patient_billing_report_rows", build_id)
                                     if table == "cohort_compliance_index" else None),
                )
            if table in _EVIDENCE_TABLES:
                payloads = {"index": value} if table == "wavea_evidence_index" else value
                normalized = {}
                for key, payload in payloads.items():
                    if payload.get("build_id") != build_id:
                        raise ValueError(f"Current {table} build identity differs: {key}")
                    normalized[key] = {
                        field: item for field, item in payload.items() if field != "build_id"
                    }
                value = normalized["index"] if table == "wavea_evidence_index" else normalized
            if same_input is not None:
                value = normalize_attested_data_source(value, same_input["paths"][side])
                # Row-table ordering must follow normalized content, not physical input paths.
                if table in _ROW_TABLES:
                    value = sorted(value, key=_digest)
            values.append(value)
        if _digest(values[0]) != _digest(values[1]):
            raise ValueError(f"Current {table} payload drift")
        digests[table] = _digest(values[1])
    return digests, reports, bill_count


def verify_serving_baseline_equivalence(
    serving_db: Path,
    *,
    serving_build_id: str,
    baseline_db: Path,
    baseline_build_id: str,
) -> dict[str, Any]:
    """Bridge the protected serving cache to a separately rebuilt baseline.

    Historical serving and rebuilt caches may have different build IDs, code
    SHAs, and input path hashes. The release can use the rebuilt cache for its
    same-input proof only if every persisted content table in the explicitly
    verified schema is identical to the cache serving before activation.
    """
    if serving_db.resolve() == baseline_db.resolve():
        raise ValueError("Serving and rebuilt baseline caches must be independent")
    serving_sha = _candidate_db_hash(serving_db)
    baseline_sha = _candidate_db_hash(baseline_db)
    table_digests: dict[str, str] = {}
    with duckdb.connect(str(serving_db), read_only=True) as serving:
        with duckdb.connect(str(baseline_db), read_only=True) as baseline:
            serving_meta = _build_metadata(serving, serving_build_id)
            baseline_meta = _build_metadata(baseline, baseline_build_id)
            contract = _baseline_contract(serving, serving_build_id)
            if _baseline_contract(baseline, baseline_build_id) != contract:
                raise ValueError("Serving and rebuilt baseline schema versions differ")
            patient_count = bill_count = 0
            for table in (
                *_PATIENT_TABLES, "patient_bill_billing_report_rows",
                "cohort_compliance_index", *_SINGLETON_TABLES, *_ROW_TABLES,
            ):
                old_schema = serving.execute(f"PRAGMA table_info('{table}')").fetchall()
                rebuilt_schema = baseline.execute(f"PRAGMA table_info('{table}')").fetchall()
                if old_schema != rebuilt_schema:
                    raise ValueError(f"Serving and rebuilt legacy {table} schema differs")
                columns = [row[1] for row in old_schema]
                expected = (
                    ["build_id", "patient_id", "payload_json"]
                    if table in (*_PATIENT_TABLES, "patient_bill_billing_report_rows")
                    else ["build_id", "payload_json"]
                    if table in ("cohort_compliance_index", *_SINGLETON_TABLES)
                    else None
                )
                if expected is not None and columns != expected:
                    raise ValueError(f"Serving legacy {table} has unverified columns")
            for table in (*_PATIENT_TABLES, "patient_bill_billing_report_rows"):
                old_rows = _payload_rows(serving, table, serving_build_id)
                rebuilt_rows = _payload_rows(baseline, table, baseline_build_id)
                if table in ("patient_billing_report_rows", "patient_bill_billing_report_rows"):
                    if table == "patient_billing_report_rows":
                        patient_count = len(old_rows)
                    else:
                        bill_count = len(old_rows)
                if _digest(old_rows) != _digest(rebuilt_rows):
                    raise ValueError(f"Serving and rebuilt legacy {table} differ")
                table_digests[table] = _digest(old_rows)
            for table in ("cohort_compliance_index", *_SINGLETON_TABLES):
                old_payload = _singleton(serving, table, serving_build_id)
                rebuilt_payload = _singleton(baseline, table, baseline_build_id)
                if _digest(old_payload) != _digest(rebuilt_payload):
                    raise ValueError(f"Serving and rebuilt legacy {table} differ")
                table_digests[table] = _digest(old_payload)
            for table in _ROW_TABLES:
                old_rows = _legacy_row_table(serving, table, serving_build_id)
                rebuilt_rows = _legacy_row_table(baseline, table, baseline_build_id)
                if _digest(old_rows) != _digest(rebuilt_rows):
                    raise ValueError(f"Serving and rebuilt legacy {table} differ")
                table_digests[table] = _digest(old_rows)
            if contract == FULL_EVIDENCE_SCHEMA_VERSION:
                table_digests, reports, bill_count = _current_content_parity(
                    serving, serving_build_id, baseline, baseline_build_id,
                )
                for con, build_id in ((serving, serving_build_id), (baseline, baseline_build_id)):
                    _check_evidence(
                        con, build_id, _payload_rows(con, "patient_billing_report_rows", build_id),
                        None,
                    )
    expected_tables = 19 if contract == FULL_EVIDENCE_SCHEMA_VERSION else 16
    if patient_count < 1 or bill_count < 1 or len(table_digests) != expected_tables:
        raise ValueError("Serving baseline legacy inventory is incomplete")
    if (
        _candidate_db_hash(serving_db) != serving_sha
        or _candidate_db_hash(baseline_db) != baseline_sha
    ):
        raise ValueError("Serving or rebuilt baseline cache changed during verification")
    return {
        "status": "serving_baseline_legacy_equivalent",
        "comparison_contract": contract,
        "serving_build_id": serving_build_id,
        "serving_code_sha": serving_meta["code_sha"],
        "serving_cache_sha256": serving_sha,
        "baseline_build_id": baseline_build_id,
        "baseline_code_sha": baseline_meta["code_sha"],
        "baseline_cache_sha256": baseline_sha,
        "patient_count": patient_count,
        "bill_count": bill_count,
        "table_digests": table_digests,
    }


def _check_legacy_parity(
    baseline: duckdb.DuckDBPyConnection,
    baseline_build: str,
    candidate: duckdb.DuckDBPyConnection,
    candidate_build: str,
    *,
    same_input: dict[str, Any] | None = None,
    clinical_transition: Any = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    old_meta = _build_metadata(baseline, baseline_build)
    new_meta = _build_metadata(candidate, candidate_build)
    if same_input is None and any(
        old_meta[key] != new_meta[key] for key in ("source_hash", "config_hash")
    ):
        raise ValueError("Same-input baseline and candidate build metadata differ")
    if same_input is not None and any(
        same_input[name][key] != meta[key]
        for name, meta in (("baseline", old_meta), ("candidate", new_meta))
        for key in ("source_hash", "config_hash")
    ):
        raise ValueError("Same-input proof differs from selected build metadata")

    def comparable(value: Any, build: str) -> Any:
        return (
            normalize_attested_data_source(value, same_input["paths"][build])
            if same_input is not None else value
        )

    def same_legacy_json(old: Any, new: Any) -> bool:
        # Python considers 12 == 12.0 and False == 0. Persisted JSON does not:
        # retain number representation, nulls, and sign of rounded zero.
        return _digest(old) == _digest(new)
    contract = _baseline_contract(baseline, baseline_build)
    if contract == FULL_EVIDENCE_SCHEMA_VERSION:
        digests, reports, bill_count = _current_content_parity(
            baseline, baseline_build, candidate, candidate_build, same_input=same_input,
            clinical_transition=clinical_transition,
        )
        _check_evidence(
            baseline, baseline_build,
            _payload_rows(baseline, "patient_billing_report_rows", baseline_build), None,
        )
        return {
            "source_hash": new_meta["source_hash"],
            "config_hash": new_meta["config_hash"],
            "candidate_build_id": candidate_build,
            "candidate_code_sha": new_meta["code_sha"],
            "comparison_contract": contract,
            "patient_count": len(reports),
            "bill_count": bill_count,
            "table_semantic_sha256": digests,
            "financial_rounding_and_null_parity": "verified_all_legacy_rows",
            "full_evidence_parity": "verified_all_current_rows",
        }, reports
    if clinical_transition is not None:
        raise ValueError("Clinical transition requires the complete current nineteen-table contract")
    reports: dict[str, dict[str, Any]] = {}
    table_digests: dict[str, str] = {}
    for table in (*_PATIENT_TABLES, "patient_bill_billing_report_rows"):
        old_rows = _payload_rows(baseline, table, baseline_build)
        new_rows = _payload_rows(candidate, table, candidate_build)
        if set(old_rows) != set(new_rows):
            raise ValueError(f"Legacy {table} key set changed")
        if table in ("patient_billing_report_rows", "patient_bill_billing_report_rows"):
            if any(_NEW_REPORT_FIELDS & old_rows[key].keys() for key in old_rows):
                raise ValueError("Baseline billing report already contains Wave A display fields")
            if any(not _baseline_has_only_original_five(row) for row in old_rows.values()):
                raise ValueError("Baseline claim compliance is not the original-five contract")
            for key in old_rows:
                if not same_legacy_json(
                    comparable(_legacy_report(old_rows[key]), "baseline"),
                    comparable(_legacy_report(new_rows[key]), "candidate"),
                ):
                    raise ValueError(f"Legacy {table} payload drift: {key}")
            if table == "patient_billing_report_rows":
                reports = new_rows
            comparison = {
                key: comparable(_legacy_report(new_rows[key]), "candidate")
                for key in sorted(new_rows)
            }
        else:
            if not same_legacy_json(
                comparable(old_rows, "baseline"), comparable(new_rows, "candidate")
            ):
                raise ValueError(f"Legacy {table} payload drift")
            comparison = comparable(new_rows, "candidate")
        table_digests[table] = _digest(comparison)
    for table in _SINGLETON_TABLES:
        old_payload = _singleton(baseline, table, baseline_build)
        new_payload = _singleton(candidate, table, candidate_build)
        if not same_legacy_json(
            comparable(old_payload, "baseline"), comparable(new_payload, "candidate")
        ):
            raise ValueError(f"Legacy {table} payload drift")
        table_digests[table] = _digest(comparable(new_payload, "candidate"))
    for table in _ROW_TABLES:
        old_columns = [
            row[1] for row in baseline.execute(f"PRAGMA table_info('{table}')").fetchall()
        ]
        new_columns = [
            row[1] for row in candidate.execute(f"PRAGMA table_info('{table}')").fetchall()
        ]
        if old_columns != new_columns:
            raise ValueError(f"Legacy {table} column roster changed")
        old_rows = _legacy_row_table(baseline, table, baseline_build)
        new_rows = _legacy_row_table(candidate, table, candidate_build)
        if not same_legacy_json(
            comparable(old_rows, "baseline"), comparable(new_rows, "candidate")
        ):
            raise ValueError(f"Legacy {table} payload drift")
        table_digests[table] = _digest(comparable(new_rows, "candidate"))
    old_cohort = _singleton(baseline, "cohort_compliance_index", baseline_build)
    new_cohort = _singleton(candidate, "cohort_compliance_index", candidate_build)
    baseline_reports = _payload_rows(baseline, "patient_billing_report_rows", baseline_build)
    expected_old = build_cohort_compliance_index(baseline_reports)
    expected_new = build_cohort_compliance_index(reports)
    if not same_legacy_json(_without_data_source(old_cohort), expected_old):
        raise ValueError("Baseline cohort compliance disagrees with baseline patient rows")
    if not same_legacy_json(_without_data_source(new_cohort), expected_new):
        raise ValueError("Candidate cohort compliance disagrees with candidate patient rows")
    if not same_legacy_json(
        build_cohort_compliance_index(
            {patient_id: _legacy_report(report) for patient_id, report in reports.items()}
        ), expected_old,
    ):
        raise ValueError("Original-five cohort compliance drifted")
    for key in ("billed_at_risk_try",):
        if not same_legacy_json(new_cohort.get(key), old_cohort.get(key)):
            raise ValueError("Existing cohort compliance amount drifted")
    if any(
        not same_legacy_json(
            new_cohort.get("by_surface", {}).get(surface, {}).get("billed_try"),
            values.get("billed_try"),
        )
        for surface, values in old_cohort.get("by_surface", {}).items()
    ):
        raise ValueError("Existing cohort compliance surface amount drifted")
    table_digests["cohort_compliance_original_five"] = _digest(expected_old)
    return {
        "source_hash": new_meta["source_hash"],
        "config_hash": new_meta["config_hash"],
        "candidate_build_id": candidate_build,
        "candidate_code_sha": new_meta["code_sha"],
        "comparison_contract": contract,
        "patient_count": len(reports),
        "bill_count": len(
            _payload_rows(candidate, "patient_bill_billing_report_rows", candidate_build)
        ),
        "table_semantic_sha256": table_digests,
        "financial_rounding_and_null_parity": "verified_all_legacy_rows",
    }, reports


def _check_bounded_block(block: Any, detail: dict[str, Any], field: str) -> None:
    if not isinstance(block, dict):
        raise ValueError(f"Default {field} is missing")
    collection = {
        "claim_reviews": "reviews",
        "claim_advisories": "advisories",
        "financial_findings": "financial_rows",
    }.get(field)
    if collection is None:
        raise ValueError(f"Unsupported bounded evidence field: {field}")
    full_rows = detail[collection]
    available = detail.get("available") is True
    expected_count = len(full_rows) if available else None
    shown = block.get("rows")
    if (
        block.get("available") is not available
        or block.get("unavailable_reason") != detail.get("unavailable_reason")
        or block.get("total_rows") != expected_count
        or not isinstance(shown, list)
        or len(shown) > DEFAULT_DETAIL_LIMIT
        or shown != (full_rows[:DEFAULT_DETAIL_LIMIT] if available else [])
        or block.get("has_more") is not (available and len(full_rows) > DEFAULT_DETAIL_LIMIT)
    ):
        raise ValueError(f"Default {field} disagrees with exhaustive Wave A detail")


def _check_full_bill_evidence(
    candidate: duckdb.DuckDBPyConnection,
    build_id: str,
    patient_details: dict[str, dict[str, Any]],
    rule_groups: dict[str, str],
) -> dict[str, dict[str, Any]]:
    bills = _payload_rows(candidate, "patient_bill_billing_report_rows", build_id)
    bill_details = _payload_rows(candidate, "wavea_bill_evidence_detail", build_id)
    if set(bills) != set(bill_details):
        raise ValueError("Wave A bill detail keys differ from bill report keys")
    for key, bill in bills.items():
        if "::" not in key:
            raise ValueError("Wave A bill row lacks claim identity")
        patient_id, claim_id = key.split("::", 1)
        patient_detail = patient_details.get(patient_id)
        detail = bill_details[key]
        if (
            patient_detail is None
            or not claim_id
            or bill.get("patient_id") != patient_id
            or ("claim_id" in bill and bill["claim_id"] != claim_id)
            or detail.get("build_id") != build_id
            or detail.get("data_source") != bill.get("data_source")
            or detail.get("data_source") != patient_detail.get("data_source")
        ):
            raise ValueError(f"Wave A bill source identity differs: {key}")
        validate_full_wavea_evidence_detail(detail, patient_id)
        patient_claims = {
            row["claim_id"]: row
            for row in patient_detail["claim_scope_inventory"]["claims"]
        }
        claim_scope = patient_claims.get(claim_id)
        if detail["claim_scope_inventory"] != {
            "context_state": "available",
            "claims": [claim_scope],
        }:
            raise ValueError(f"Wave A bill scope differs from patient source scope: {key}")
        for field in ("claim_reviews", "claim_advisories", "financial_findings"):
            _check_bounded_block(bill.get(field), detail, field)
        counts = detail["counts"]
        expected_coverage = {
            "schema_version": FULL_EVIDENCE_SCHEMA_VERSION,
            "available": detail["available"],
            "unavailable_reason": detail["unavailable_reason"],
            "tracked_rule_count": len(rule_groups),
            "evaluation_count": counts["evaluation_count"],
            "by_group": counts["by_group"],
        }
        if bill.get("wavea_coverage") != expected_coverage:
            raise ValueError(f"Wave A bill coverage differs from its own detail: {key}")
    return bill_details


def _check_evidence(
    candidate: duckdb.DuckDBPyConnection,
    build_id: str,
    reports: dict[str, dict[str, Any]],
    source_roster: Path | None,
) -> tuple[dict[str, Any], list[str]]:
    details = _payload_rows(candidate, "wavea_evidence_detail", build_id)
    if set(details) != set(reports):
        raise ValueError("Wave A detail patient keys differ from billing reports")
    index = _singleton(candidate, "wavea_evidence_index", build_id)
    if index.get("build_id") != build_id:
        raise ValueError("Wave A index belongs to a different build")
    blockers: set[str] = set()
    focused = FOCUSED_RULE_SPECS
    broad = load_broad_rule_catalog()
    focused_rules = {item.rule_id for item in focused}
    broad_rules = {item.rule_id for item in broad}
    focused_groups = {item.group for item in focused}
    broad_groups = {item.family for item in broad}
    if (
        len(focused) != 32
        or len(broad) != 496
        or len(focused_rules) != 32
        or len(broad_rules) != 496
        or len(focused_groups) != 18
        or len(broad_groups) != 7
        or focused_rules & broad_rules
        or focused_groups & broad_groups
    ):
        raise ValueError("Source-authored Wave A roster differs from 25 groups/528 IDs")
    all_rules = focused_rules | broad_rules
    all_groups = focused_groups | broad_groups
    rule_groups = {
        **{item.rule_id: item.group for item in focused},
        **{item.rule_id: item.family for item in broad},
    }
    schema_versions = {detail.get("schema_version") for detail in details.values()}
    if len(schema_versions) != 1:
        raise ValueError("Wave A detail schema versions differ across patients")
    schema_version = next(iter(schema_versions))
    if schema_version not in (EVIDENCE_SCHEMA_VERSION, FULL_EVIDENCE_SCHEMA_VERSION):
        raise ValueError("Wave A detail schema version is unknown or incomplete")
    if index.get("schema_version") != schema_version:
        raise ValueError("Wave A index and detail schema versions differ")
    full_schema = schema_versions == {FULL_EVIDENCE_SCHEMA_VERSION}
    for patient_id, detail in details.items():
        if detail.get("build_id") != build_id:
            raise ValueError(f"Wave A detail build identity mismatch: {patient_id}")
        if detail.get("data_source") != reports[patient_id].get("data_source"):
            raise ValueError(f"Wave A detail source identity mismatch: {patient_id}")
        if full_schema:
            validate_full_wavea_evidence_detail(detail, patient_id)
            if detail.get("roster_version") != FULL_ROSTER_VERSION:
                raise ValueError(f"Wave A detail roster differs: {patient_id}")
        else:
            validate_wavea_evidence_detail(detail, patient_id)
        report = reports[patient_id]
        _check_bounded_block(report.get("claim_reviews"), detail, "claim_reviews")
        if full_schema:
            _check_bounded_block(report.get("claim_advisories"), detail, "claim_advisories")
        elif report.get("claim_advisories") is not None:
            raise ValueError("Draft focused report has unsupported advisory rows")
        _check_bounded_block(report.get("financial_findings"), detail, "financial_findings")
        coverage = report.get("wavea_coverage")
        if not isinstance(coverage, dict) or coverage.get("schema_version") != detail.get(
            "schema_version"
        ):
            raise ValueError(f"Wave A default coverage is malformed: {patient_id}")
        counts = detail.get("counts")
        if not isinstance(counts, dict):
            blockers.add("patient_evidence_counts_unavailable")
            continue
        if (
            coverage.get("available") != detail.get("available")
            or coverage.get("unavailable_reason") != detail.get("unavailable_reason")
            or coverage.get("evaluation_count") != counts.get("evaluation_count")
            or coverage.get("by_group") != counts.get("by_group")
        ):
            raise ValueError(f"Wave A default coverage disagrees with detail: {patient_id}")
        if (
            set(counts.get("by_rule") or {}) != all_rules
            or set(counts.get("by_group") or {}) != all_groups
            or coverage.get("tracked_rule_count") != len(all_rules)
        ):
            blockers.add("complete_25_group_status_roster_missing")
        if not isinstance(detail.get("claim_scope_inventory"), dict):
            blockers.add("independent_claim_material_scope_inventory_missing")
    expected_index = (
        build_full_wavea_evidence_index(details)
        if full_schema
        else build_wavea_evidence_index(details)
    )
    if full_schema and index.get("capability") != "draft":
        raise ValueError("Wave A v2 cache capability must remain draft until sidecar attestation")
    normalized_index = {
        **{key: value for key, value in index.items() if key not in ("build_id", "data_source")},
        "capability": "draft",
    }
    if normalized_index != expected_index:
        raise ValueError("Wave A singleton index disagrees with exhaustive patient details")
    if index.get("data_source") != next(
        (report.get("data_source") for report in reports.values()),
        index.get("data_source"),
    ):
        raise ValueError("Wave A singleton source identity differs")
    if full_schema:
        blockers.add("independent_release_attestation_missing")
    elif index.get("capability") != "complete-25-v1":
        blockers.add("complete_25_capability_not_activated")
    pinned_scopes = None
    pinned_lines = None
    if not full_schema:
        blockers.add("full_25_evidence_v2_missing")
    if source_roster is None or not full_schema:
        blockers.add("claim_material_scopes_not_checked_against_pinned_parquets")
    else:
        pinned_scopes = verify_pinned_claim_scopes(source_roster, details)
    bill_details = (
        _check_full_bill_evidence(candidate, build_id, details, rule_groups)
        if full_schema
        else {}
    )
    if source_roster is not None and full_schema:
        pinned_lines = verify_pinned_evidence_lines(source_roster, details, bill_details)
    else:
        blockers.add("focused_source_lines_not_checked_against_pinned_parquets")
        blockers.add("observed_billed_amounts_not_reconciled_to_pinned_lines")
    return {
        "schema_version": next(iter(schema_versions), None),
        "focused_rule_ids": len(focused_rules),
        "broad_authored_rule_ids": len(broad_rules),
        "groups": len(all_groups),
        "detail_patient_count": len(details),
        "bill_evidence_count": len(bill_details) if full_schema else None,
        "index_evidence_count": len(index.get("evidence_rows") or []),
        "index_semantic_sha256": _digest(index),
        "pinned_claim_scopes": pinned_scopes,
        "pinned_line_evidence": pinned_lines,
    }, sorted(blockers)


def verify_candidate_semantic_checkpoint(
    baseline_db: Path,
    *,
    baseline_build_id: str,
    candidate_db: Path,
    candidate_build_id: str,
    source_roster: Path | None = None,
    baseline_roster: Path | None = None,
    build_config_environment: dict[str, str] | None = None,
    baseline_build_config_environment: dict[str, str] | None = None,
    clinical_transition: dict[str, Any] | None = None,
    python_executable: Path | None = None,
    dependency_roots: tuple[Path, ...] = (),
) -> dict[str, Any]:
    """Compare complete cached datasets while leaving release readiness false."""
    if baseline_db.resolve() == candidate_db.resolve():
        raise ValueError("Baseline and candidate must be independent cache files")
    baseline_sha = _candidate_db_hash(baseline_db)
    candidate_sha = _candidate_db_hash(candidate_db)
    if (baseline_roster is None) != (build_config_environment is None):
        raise ValueError("Same-input proof needs baseline roster and build environment")
    if baseline_roster is not None and source_roster is None:
        raise ValueError("Same-input proof needs the candidate source roster")
    if baseline_build_config_environment is not None and baseline_roster is None:
        raise ValueError("Baseline configuration proof needs a baseline source roster")
    from scripts.deploy.verify_source_refresh_transition import (
        validate_transition_request, verify_transition,
    )
    transition_request = validate_transition_request(clinical_transition)
    transition_proof = None
    with duckdb.connect(str(baseline_db), read_only=True) as baseline:
        with duckdb.connect(str(candidate_db), read_only=True) as candidate:
            same_input = (
                verify_same_input_rosters(
                    baseline_roster,
                    source_roster,
                    baseline_meta=_build_metadata(baseline, baseline_build_id),
                    candidate_meta=_build_metadata(candidate, candidate_build_id),
                    build_config_environment=build_config_environment,
                    baseline_build_config_environment=baseline_build_config_environment,
                )
                if baseline_roster is not None else None
            )
            if transition_request is not None:
                if same_input is None or python_executable is None:
                    raise ValueError("Clinical transition requires source/config/input proof and an explicit runtime")
                transition_proof = verify_transition(
                    request=transition_request,
                    baseline_roster=baseline_roster, candidate_roster=source_roster,
                    baseline_meta=_build_metadata(baseline, baseline_build_id),
                    candidate_meta=_build_metadata(candidate, candidate_build_id),
                    same_input=same_input, python_executable=python_executable,
                    dependency_roots=dependency_roots,
                    expected_candidate_sha=transition_request["expected_candidate_sha"],
                    expected_verifier_sha=transition_request["expected_verifier_sha"],
                )
            legacy, reports = _check_legacy_parity(
                baseline,
                baseline_build_id,
                candidate,
                candidate_build_id,
                same_input=same_input,
                clinical_transition=transition_proof,
            )
            evidence, blockers = _check_evidence(
                candidate, candidate_build_id, reports, source_roster
            )
    if _candidate_db_hash(baseline_db) != baseline_sha:
        raise ValueError("Baseline cache changed during semantic verification")
    if _candidate_db_hash(candidate_db) != candidate_sha:
        raise ValueError("Candidate cache changed during semantic verification")
    if same_input is None:
        blockers.append("same_input_baseline_byte_attestation_missing")
    blockers.append("candidate_api_browser_and_rollback_rehearsal_pending")
    result = {
        "status": "semantic_checkpoint_verified",
        "release_ready": False,
        "remaining_gates": sorted(set(blockers)),
        "baseline_database_sha256": baseline_sha,
        "candidate_database_sha256": candidate_sha,
        "candidate_identity": {
            "build_id": candidate_build_id,
            "code_sha": legacy["candidate_code_sha"],
            "source_hash": legacy["source_hash"],
            "source_roster_sha256": (evidence.get("pinned_line_evidence") or {}).get(
                "source_roster_sha256"
            ),
            "cache_sha256": candidate_sha,
        },
        "legacy": legacy,
        "same_input": same_input,
        "wavea_evidence": evidence,
    }
    if transition_proof is not None:
        result["clinical_transition"] = transition_proof.report
    return result
