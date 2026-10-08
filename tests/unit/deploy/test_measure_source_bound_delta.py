"""Synthetic source ownership, typed equality and non-authorizing measurement."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts.deploy import measure_source_bound_delta as delta


BILLING = "src/bilun/domain/billing/"
RULES = "data/gazette/prose_rules/material_bundling_prose.json"
MANIFEST = "data/gazette/prose_manifests/L1.4_material_bundling_encoded_manifest.json"
REPORT = "patient_billing_report_rows"
BILL_REPORT = "patient_bill_billing_report_rows"
COHORT = "cohort_compliance_index"
PATIENT = "synthetic-patient-private"
CLAIM = "synthetic-claim-private"
BILL_KEY = PATIENT + "::" + CLAIM
RULE = "SYNTHETIC-MATERIAL-A"
OTHER_RULE = "SYNTHETIC-MATERIAL-B"
OLD_MESSAGE = "Message (\u00a73.1.1(12))."
NEW_MESSAGE = "Message (\u00a73.1.1(10))."
OLD_SOURCE = "KDV \u00a73.1.1(12)"
NEW_SOURCE = "KDV \u00a73.1.1(10)"
OLD_KDV = "Billed amount exceeds EK-3 list price + KDV (\u00a73.1.1(12))."
NEW_KDV = "Billed amount exceeds EK-3 list price + KDV (\u00a73.1.1(10))."
BUILD_PATH = "src/bilun/cache/builder.py"
OWN_TABLES = ("wavea_evidence_detail", "wavea_bill_evidence_detail", "wavea_evidence_index")
OLD_BUILD = "private-old-synthetic-build"
NEW_BUILD = "private-new-synthetic-build"
BUILDER = b"""def _normalize_wavea_bill_detail(bill_key, report, build_id):
    normalized = json_ready(detail)
    normalized['build_id'] = build_id
    return normalized

def _write_wavea_bill_details(con, raw_bill_reports, build_id, data_source, *, batch_size=4):
    rows = []
    written = 0
    for bill_key, report in raw_bill_reports.items():
        detail = _normalize_wavea_bill_detail(bill_key, report, build_id)
        rows.append((bill_key, dump_json_compact(attach_bilun_data_source_metadata(detail, data_source))))
        if len(rows) == batch_size:
            written += write_json_payload_rows_serialized(con, 'wavea_bill_evidence_detail', build_id, rows, append=written > 0)
            rows = []
    if rows or not written:
        written += write_json_payload_rows_serialized(con, 'wavea_bill_evidence_detail', build_id, rows, append=written > 0)
    return written

def run_build(args):
    try:
        for detail in wavea_details.values():
            detail['build_id'] = build.build_id
        write_json_payload_rows(con, 'wavea_evidence_detail', build.build_id,
            {patient_id: attach_bilun_data_source_metadata(detail, sut_data_source_metadata)
             for patient_id, detail in wavea_details.items()})
        wavea_bill_count = _write_wavea_bill_details(con, raw_bill_reports, build.build_id, sut_data_source_metadata)
        wavea_index = build_full_wavea_evidence_index(wavea_details)
        wavea_index['build_id'] = build.build_id
        upsert_single_json_table(con, 'wavea_evidence_index', build.build_id,
            attach_bilun_data_source_metadata(wavea_index, sut_data_source_metadata))
    finally:
        con.close()
"""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _source_files(*, candidate):
    rule = {
        "rule_id": RULE,
        "predicate": {"material_code": "SYNTHETIC-CODE", "mode": "audit"},
        "action": {
            "kind": "flag",
            "message_tr": NEW_MESSAGE if candidate else OLD_MESSAGE,
        },
        "gate_b_sources": ["3.1.1.(10)" if candidate else "3.1.1.(12)"],
    }
    other = {
        "rule_id": OTHER_RULE,
        "predicate": {"material_code": "SYNTHETIC-OTHER", "mode": "audit"},
        "action": {"kind": "flag", "message_tr": "Unchanged synthetic message"},
    }
    files = {
        RULES: _json({"rules": [rule, other]}),
        MANIFEST: _json(
            {
                "clause_traces": [
                    {
                        "clause_id": "synthetic-old-clause",
                        "linked_rule_ids": [] if candidate else [RULE],
                    },
                    {
                        "clause_id": "synthetic-new-clause",
                        "linked_rule_ids": [RULE] if candidate else [],
                    },
                    {"clause_id": "synthetic-stable-clause", "linked_rule_ids": [OTHER_RULE]},
                ]
            }
        ),
        BILLING + "types.py": (
            "class LabOptimization:\n"
            + (
                "    normative_cost_try: float | None = None\n"
                if candidate
                else "    normative_cost_try: float = 0.0\n"
            )
            + "    exactness_status: str = 'exact'\n"
            + "    required_inputs_missing: list = []\n"
            + "    computed_total_try: float = 0.0\n"
        ).encode(),
        BILLING
        + "claim_lab.py": b"def _optimize_lab_billing_from_claims(claims):\n    return LabOptimization()\n",
        BILLING + "lab_bill_merge.py": (
            "def merge(merged_lab, lab_result):\n"
            + (
                "    if lab_result.normative_cost_try is not None:\n"
                "        merged_lab.normative_cost_try = round((merged_lab.normative_cost_try or 0.0) + lab_result.normative_cost_try, 2)\n"
                if candidate
                else "    merged_lab.normative_cost_try = round(merged_lab.normative_cost_try + lab_result.normative_cost_try, 2)\n"
            )
            + "    return merged_lab\n"
        ).encode(),
        BILLING + "patient_report.py": (
            b"def build_report(result, claims):\n"
            b"    result.lab, capture = compute_lab_and_capture_gap_from_claims(claims)\n"
            b"    return result\n"
        ),
        BILLING + "billing_actions.py": (
            b"def _material_row_detail(row):\n"
            b"    return row.get('note') or row.get('message')\n"
            b"def collect_billing_actions(row):\n"
            b"    kinds = ('material_pre_auth', 'material_prose_bundling')\n"
            b"    return action(kind=kinds[1], detail=_material_row_detail(row))\n"
        ),
        BILLING
        + "cohort_compliance.py": b"def _row_from_action(action):\n    return {'detail': action.get('detail')}\n",
        "src/bilun/domain/prose_rules/clause_linking.py": b"def clause_ref_for_rule_id(rule_id):\n    return None\n",
        "src/bilun/domain/sut/rules_catalog.py": b"def get_clause(key):\n    return None\n",
        "src/bilun/domain/sut/clause_reference.py": b"SOURCE_SUT_CLAUSE = 'sut_clause'\n",
    }
    precheck = (
        "def precheck_materials_from_claims(code, preauth_codes, result, line):\n"
        + (
            "    in_preauth_catalog = code in preauth_codes\n"
            "    if in_preauth_catalog or line.requires_pre_auth:\n"
            "        row = {'note': _PREAUTH_NOTE if in_preauth_catalog else _PREAUTH_FLAG_NOTE}\n"
            if candidate
            else "    if code in preauth_codes or line.requires_pre_auth:\n        row = {'note': _PREAUTH_NOTE}\n"
        )
        + (
            f"    result.rule_source = {NEW_SOURCE!r}\n"
            if candidate
            else f"    result.rule_source = {OLD_SOURCE!r}\n"
        )
        + "    return result\n"
    )
    files[BILLING + "claim_materials.py"] = (
        "_PREAUTH_NOTE = 'Catalog citation'\n"
        + ("_PREAUTH_FLAG_NOTE = 'Flag only'\n" if candidate else "")
        + "def _append_kdv_price_reviews(result, apply_kdv):\n"
        + "    note = 'Billed amount exceeds EK-3 list price' + (' + KDV' if apply_kdv else ' (KDV exempt path)')"
        + (" + ' (\u00a73.1.1(10)).'\n" if candidate else " + ' (\u00a73.1.1(12)).'\n")
        + "    return note\n"
        + precheck
    ).encode()
    return files


def _bundle(files, *, candidate):
    return delta.SourceBundle.create(
        "b" * 40 if candidate else "a" * 40,
        files,
        {path: hashlib.sha256(body).hexdigest() for path, body in files.items()},
    )


def _isolated_sources(*, message=False, gate=False, clause=False):
    old_files = _source_files(candidate=False)
    new_files = _source_files(candidate=True)
    document = json.loads(new_files[RULES])
    if not message:
        document["rules"][0]["action"]["message_tr"] = OLD_MESSAGE
    if not gate:
        document["rules"][0]["gate_b_sources"] = ["3.1.1.(12)"]
    new_files[RULES] = _json(document)
    if not clause:
        new_files[MANIFEST] = old_files[MANIFEST]
    return (
        _bundle(old_files, candidate=False),
        _bundle(new_files, candidate=True),
    )


@pytest.fixture
def sources():
    return _bundle(_source_files(candidate=False), candidate=False), _bundle(
        _source_files(candidate=True), candidate=True
    )


@pytest.fixture
def policy(sources):
    return delta.derive_policy(*sources)


def _ref(*, candidate):
    return {
        "clause_key": "synthetic-new-key" if candidate else "synthetic-old-key",
        "clause_coordinate": "3.1.2" if candidate else "3.1.1",
        "source_type": "sut_clause",
        "rule_type": "",
        "annex": "",
        "statutory_law": "",
    }


def _witnesses(sources):
    return {
        "clause_references": {
            "baseline": {RULE: _ref(candidate=False)},
            "candidate": {RULE: _ref(candidate=True)},
        },
        "clause_source_identities": {
            "baseline": sources[0].identity,
            "candidate": sources[1].identity,
        },
    }


def _report():
    return {
        "patient_id": PATIENT,
        "claim_id": CLAIM,
        "lab": {
            "normative_cost_try": 0.0,
            "exactness_status": "exact",
            "required_inputs_missing": [],
            "computed_total_try": 0.0,
        },
        "materials": {
            "rule_source": OLD_SOURCE,
            "prose_bundling_violations": [
                {
                    "rule_id": RULE,
                    "claim_id": CLAIM,
                    "material_code": "SYNTHETIC-CODE",
                    "message": OLD_MESSAGE,
                    "gate_b_sources": ["3.1.1.(12)"],
                    "clause_ref": _ref(candidate=False),
                    "source_type": "sut_clause",
                    "is_violation": True,
                    "amount_try": 0.0,
                }
            ],
            "pre_auth_required": [
                {
                    "claim_id": CLAIM,
                    "material_code": "SYNTHETIC-CODE",
                    "note": "Catalog citation",
                    "price_try": 0.0,
                }
            ],
            "kdv_price_reviews": [
                {"material_code": "SYNTHETIC-CODE", "note": OLD_KDV, "price_try": 0.0}
            ],
        },
        "recommended_actions": [
            {
                "action_id": f"materials:material_prose_bundling:{CLAIM}:0",
                "claim_id": CLAIM,
                "material_code": "SYNTHETIC-CODE",
                "surface": "materials",
                "kind": "material_prose_bundling",
                "detail": OLD_MESSAGE,
                "billed_try": 0.0,
            }
        ],
        "clinical_result": "not_evaluated",
        "known_zero_try": 0.0,
        "known_nonzero_try": 12.5,
    }


def _tables():
    tables = {table: {} for table in delta.TABLES}
    tables[REPORT] = {PATIENT: _report()}
    tables[BILL_REPORT] = {BILL_KEY: _report()}
    tables[COHORT] = {
        "rows": [
            {
                **copy.deepcopy(_report()["recommended_actions"][0]),
                "patient_id": PATIENT,
                "source_surface": "materials",
            }
        ]
    }
    return tables


def _measure(left, right, policy, sources, **overrides):
    witnesses = _witnesses(sources)
    witnesses.update(overrides)
    return delta.measure_delta(left, right, policy, **witnesses)


def _reject(left, right, policy, sources, **overrides):
    with pytest.raises(delta.MeasurementRejected) as caught:
        _measure(left, right, policy, sources, **overrides)
    message = str(caught.value)
    assert message
    assert PATIENT not in message
    assert CLAIM not in message
    assert OLD_MESSAGE not in message
    assert "12.5" not in message


def test_equal_complete_projection_is_non_authorizing(policy, sources, capsys):
    left = _tables()
    result = _measure(left, copy.deepcopy(left), policy, sources)
    summary = result.safe_summary()
    assert summary["status"] == "source_bound_delta_measured_non_authorizing"
    assert summary["changed_cell_count"] == 0
    assert summary["change_counts"] == {}
    for key in (
        "deployment_admitted",
        "semantic_release_admitted",
        "external_witness_generation_attested",
        "own_source_cache_equivalence_attested",
    ):
        assert summary[key] is False
    assert len(summary["source_policy_sha256"]) == 64
    assert len(summary["delta_sha256"]) == 64
    rendered = json.dumps(summary) + repr(result)
    for forbidden in (PATIENT, CLAIM, OLD_MESSAGE, "normative_cost_try", "12.5"):
        assert forbidden not in rendered
    assert capsys.readouterr() == ("", "")
    assert left == _tables()
    summary["deployment_admitted"] = True
    summary["change_counts"]["forged"] = 1
    assert result.safe_summary()["deployment_admitted"] is False
    assert result.safe_summary()["change_counts"] == {}


@pytest.mark.parametrize("table", [REPORT, BILL_REPORT])
@pytest.mark.parametrize(
    ("path", "value", "classification"),
    [
        (
            ("materials", "prose_bundling_violations", 0, "message"),
            NEW_MESSAGE,
            "material_rule_message_citation",
        ),
        (
            ("materials", "prose_bundling_violations", 0, "gate_b_sources", 0),
            "3.1.1.(10)",
            "material_rule_gate_source",
        ),
        (("materials", "rule_source"), NEW_SOURCE, "material_rule_source_citation"),
        (
            ("materials", "pre_auth_required", 0, "note"),
            "Flag only",
            "material_flag_only_preauth_note",
        ),
        (("materials", "kdv_price_reviews", 0, "note"), NEW_KDV, "material_kdv_note_citation"),
        (("recommended_actions", 0, "detail"), NEW_MESSAGE, "material_action_detail_source_pair"),
        (("lab", "normative_cost_try"), None, "lab_normative_never_computed_default"),
    ],
)
def test_each_source_proved_class_has_exact_scope(
    policy, sources, table, path, value, classification
):
    overrides = {}
    if classification in (
        "material_rule_message_citation",
        "material_rule_gate_source",
        "material_action_detail_source_pair",
    ):
        sources = _isolated_sources(
            message=classification != "material_rule_gate_source",
            gate=classification == "material_rule_gate_source",
        )
        policy = delta.derive_policy(*sources)
        overrides["clause_references"] = {"baseline": {}, "candidate": {}}
    left = _tables()
    right = copy.deepcopy(left)
    row_key = PATIENT if table == REPORT else BILL_KEY
    target = right[table][row_key]
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    expected_counts = {classification: 1}
    if path == ("recommended_actions", 0, "detail"):
        right[table][row_key]["materials"]["prose_bundling_violations"][0]["message"] = NEW_MESSAGE
        expected_counts["material_rule_message_citation"] = 1
    summary = _measure(left, right, policy, sources, **overrides).safe_summary()
    assert summary["changed_cell_count"] == sum(expected_counts.values())
    assert summary["change_counts"] == expected_counts


def test_cohort_action_detail_is_source_owned(policy, sources):
    sources = _isolated_sources(message=True)
    policy = delta.derive_policy(*sources)
    left = _tables()
    right = copy.deepcopy(left)
    right[COHORT]["rows"][0]["detail"] = NEW_MESSAGE
    right[REPORT][PATIENT]["recommended_actions"][0]["detail"] = NEW_MESSAGE
    right[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]["message"] = NEW_MESSAGE
    summary = _measure(
        left,
        right,
        policy,
        sources,
        clause_references={"baseline": {}, "candidate": {}},
    ).safe_summary()
    assert summary["change_counts"] == {
        "material_rule_message_citation": 1,
        "material_action_detail_source_pair": 2,
    }


def test_clause_reference_is_exact_independent_witness(policy, sources):
    sources = _isolated_sources(clause=True)
    policy = delta.derive_policy(*sources)
    left = _tables()
    right = copy.deepcopy(left)
    row = right[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]
    row["clause_ref"] = _ref(candidate=True)
    summary = _measure(left, right, policy, sources).safe_summary()
    assert summary["change_counts"] == {"material_manifest_clause_reference": 1}


def test_gate_source_addition_is_complete_source_owned_value():
    old_files = _source_files(candidate=False)
    parsed = json.loads(old_files[RULES])
    parsed["rules"][0].pop("gate_b_sources")
    old_files[RULES] = _json(parsed)
    new_files = _source_files(candidate=True)
    document = json.loads(new_files[RULES])
    document["rules"][0]["action"]["message_tr"] = OLD_MESSAGE
    new_files[RULES] = _json(document)
    new_files[MANIFEST] = old_files[MANIFEST]
    sources = (_bundle(old_files, candidate=False), _bundle(new_files, candidate=True))
    policy = delta.derive_policy(*sources)
    left = _tables()
    left[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0].pop("gate_b_sources")
    right = copy.deepcopy(left)
    right[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]["gate_b_sources"] = [
        "3.1.1.(10)"
    ]
    references = {"baseline": {}, "candidate": {}}
    summary = _measure(left, right, policy, sources, clause_references=references).safe_summary()
    assert summary["change_counts"] == {"material_rule_gate_source": 1}
    forged = copy.deepcopy(right)
    forged[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]["gate_b_sources"] = [
        "3.1.1.(10)",
        "3.1.1.(99)",
    ]
    _reject(left, forged, policy, sources, clause_references=references)


def test_clause_addition_requires_absent_old_fields_and_none_witness():
    old_files = _source_files(candidate=False)
    parsed = json.loads(old_files[MANIFEST])
    parsed["clause_traces"][0]["linked_rule_ids"] = []
    old_files[MANIFEST] = _json(parsed)
    new_files = _source_files(candidate=True)
    document = json.loads(new_files[RULES])
    document["rules"][0]["action"]["message_tr"] = OLD_MESSAGE
    document["rules"][0]["gate_b_sources"] = ["3.1.1.(12)"]
    new_files[RULES] = _json(document)
    sources = (_bundle(old_files, candidate=False), _bundle(new_files, candidate=True))
    policy = delta.derive_policy(*sources)
    left = _tables()
    row = left[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]
    row.pop("clause_ref")
    row.pop("source_type")
    right = copy.deepcopy(left)
    row = right[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]
    row["clause_ref"] = _ref(candidate=True)
    row["source_type"] = "sut_clause"
    references = {
        "baseline": {RULE: None},
        "candidate": {RULE: _ref(candidate=True)},
    }
    summary = _measure(left, right, policy, sources, clause_references=references).safe_summary()
    assert summary["change_counts"] == {"material_manifest_clause_reference": 2}
    left[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]["clause_ref"] = None
    _reject(left, right, policy, sources, clause_references=references)


def test_preauth_action_is_bound_to_its_raw_material_row(policy, sources):
    left = _tables()
    row = left[REPORT][PATIENT]["recommended_actions"][0]
    row["action_id"] = f"materials:material_pre_auth:{CLAIM}:0"
    row["kind"] = "material_pre_auth"
    row["detail"] = "Catalog citation"
    right = copy.deepcopy(left)
    right[REPORT][PATIENT]["materials"]["pre_auth_required"][0]["note"] = "Flag only"
    right[REPORT][PATIENT]["recommended_actions"][0]["detail"] = "Flag only"
    summary = _measure(left, right, policy, sources).safe_summary()
    assert summary["change_counts"] == {
        "material_flag_only_preauth_note": 1,
        "material_action_detail_source_pair": 1,
    }


@pytest.mark.parametrize("field", ["message", "message_tr", "note"])
def test_owned_material_message_field_variants(policy, sources, field):
    sources = _isolated_sources(message=True)
    policy = delta.derive_policy(*sources)
    left = _tables()
    row = left[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]
    row[field] = row.pop("message")
    right = copy.deepcopy(left)
    right[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0][field] = NEW_MESSAGE
    assert _measure(
        left,
        right,
        policy,
        sources,
        clause_references={"baseline": {}, "candidate": {}},
    ).safe_summary()["change_counts"] == {"material_rule_message_citation": 1}


@pytest.mark.parametrize(
    "mutation",
    ["wrong_table", "wrong_path", "wrong_owner", "wrong_field", "same_counts_wrong_locations"],
)
def test_reused_documentary_text_cannot_authorize_another_location(policy, sources, mutation):
    left = _tables()
    right = copy.deepcopy(left)
    if mutation == "wrong_table":
        table = next(table for table in delta.TABLES if table not in (REPORT, BILL_REPORT, COHORT))
        left[table] = {"synthetic": _report()}
        right[table] = copy.deepcopy(left[table])
        right[table]["synthetic"]["materials"]["prose_bundling_violations"][0]["message"] = (
            NEW_MESSAGE
        )
    elif mutation == "wrong_path":
        left[REPORT][PATIENT]["unowned"] = {"message": OLD_MESSAGE, "rule_id": RULE}
        right[REPORT][PATIENT]["unowned"] = {"message": NEW_MESSAGE, "rule_id": RULE}
    elif mutation == "wrong_owner":
        for tables in (left, right):
            tables[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]["rule_id"] = (
                OTHER_RULE
            )
        right[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]["message"] = NEW_MESSAGE
    elif mutation == "wrong_field":
        left[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]["description"] = (
            OLD_MESSAGE
        )
        right[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]["description"] = (
            NEW_MESSAGE
        )
    else:
        sources = _isolated_sources(message=True)
        policy = delta.derive_policy(*sources)
        accepted = copy.deepcopy(left)
        accepted[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]["message"] = (
            NEW_MESSAGE
        )
        assert (
            _measure(
                left,
                accepted,
                policy,
                sources,
                clause_references={"baseline": {}, "candidate": {}},
            ).safe_summary()["changed_cell_count"]
            == 1
        )
        left[REPORT][PATIENT]["clinical_note"] = OLD_MESSAGE
        right[REPORT][PATIENT]["clinical_note"] = NEW_MESSAGE
    if mutation == "same_counts_wrong_locations":
        _reject(
            left,
            right,
            policy,
            sources,
            clause_references={"baseline": {}, "candidate": {}},
        )
    else:
        _reject(left, right, policy, sources)


@pytest.mark.parametrize(
    "mutation", ["surface", "kind", "action_id", "claim_id", "billed_try", "patient_id"]
)
def test_action_detail_preserves_owner_and_siblings(policy, sources, mutation):
    left = _tables()
    right = copy.deepcopy(left)
    target = right[COHORT]["rows"][0]
    target["detail"] = NEW_MESSAGE
    target[mutation] = 1.0 if mutation == "billed_try" else "wrong-synthetic-owner"
    _reject(left, right, policy, sources)


@pytest.mark.parametrize(
    "mutation",
    [
        "integer_zero",
        "true_zero",
        "nonzero",
        "null_to_zero",
        "wrong_nullable_field",
        "wrong_lab_path",
        "lab_sibling",
        "clinical_result",
        "lab_inventory",
    ],
)
def test_default_nullable_boundary_preserves_computed_money(policy, sources, mutation):
    left = _tables()
    right = copy.deepcopy(left)
    before = left[REPORT][PATIENT]
    after = right[REPORT][PATIENT]
    after["lab"]["normative_cost_try"] = None
    if mutation == "integer_zero":
        before["lab"]["normative_cost_try"] = 0
    elif mutation == "true_zero":
        after["lab"]["normative_cost_try"] = 0.0
        after["known_zero_try"] = None
    elif mutation == "nonzero":
        before["lab"]["normative_cost_try"] = 12.5
    elif mutation == "null_to_zero":
        before["lab"]["normative_cost_try"] = None
        after["lab"]["normative_cost_try"] = 0.0
    elif mutation == "wrong_nullable_field":
        after["lab"]["normative_cost_try"] = 0.0
        after["lab"]["computed_total_try"] = None
    elif mutation == "wrong_lab_path":
        after["lab"]["normative_cost_try"] = 0.0
        before["other_lab"] = copy.deepcopy(before["lab"])
        after["other_lab"] = copy.deepcopy(after["lab"])
        after["other_lab"]["normative_cost_try"] = None
    elif mutation == "lab_sibling":
        after["lab"]["computed_total_try"] = 1.0
    elif mutation == "clinical_result":
        after["clinical_result"] = "eligible"
    else:
        after["lab"]["extra_computed_field"] = 0.0
    _reject(left, right, policy, sources)


def test_documentary_change_cannot_hide_boolean_clinical_change(policy, sources):
    left = _tables()
    right = copy.deepcopy(left)
    row = right[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]
    row["message"] = NEW_MESSAGE
    row["is_violation"] = False
    _reject(left, right, policy, sources)


@pytest.mark.parametrize("value", [0, True, "0.0", 1.0, None])
def test_known_zero_is_type_exact_and_never_normalized(policy, sources, value):
    left = _tables()
    right = copy.deepcopy(left)
    right[REPORT][PATIENT]["known_zero_try"] = value
    _reject(left, right, policy, sources)


@pytest.mark.parametrize("value", [12, 12.0, 0.0, None])
def test_known_nonzero_is_preserved(policy, sources, value):
    left = _tables()
    right = copy.deepcopy(left)
    right[REPORT][PATIENT]["known_nonzero_try"] = value
    _reject(left, right, policy, sources)


@pytest.mark.parametrize(
    "mutation",
    [
        "table_missing",
        "table_added",
        "row_added",
        "row_removed",
        "row_key",
        "patient_id",
        "claim_id",
        "sequence_order",
        "sequence_length",
    ],
)
def test_inventories_identity_and_sequence_order_are_immutable(policy, sources, mutation):
    left = _tables()
    right = copy.deepcopy(left)
    if mutation == "table_missing":
        right.pop(next(iter(delta.TABLES)))
    elif mutation == "table_added":
        right["unowned_table"] = {}
    elif mutation == "row_added":
        right[REPORT]["synthetic-extra"] = _report()
    elif mutation == "row_removed":
        right[REPORT].pop(PATIENT)
    elif mutation == "row_key":
        right[REPORT]["synthetic-renamed"] = right[REPORT].pop(PATIENT)
    elif mutation == "patient_id":
        right[REPORT][PATIENT]["patient_id"] = "synthetic-changed"
    elif mutation == "claim_id":
        right[BILL_REPORT][BILL_KEY]["claim_id"] = "synthetic-changed"
    elif mutation == "sequence_order":
        second = {
            **copy.deepcopy(left[REPORT][PATIENT]["recommended_actions"][0]),
            "action_id": "synthetic-second",
        }
        left[REPORT][PATIENT]["recommended_actions"].append(second)
        right = copy.deepcopy(left)
        right[REPORT][PATIENT]["recommended_actions"].reverse()
    else:
        right[REPORT][PATIENT]["recommended_actions"].append(
            copy.deepcopy(right[REPORT][PATIENT]["recommended_actions"][0])
        )
    _reject(left, right, policy, sources)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_side",
        "missing_rule",
        "extra_rule",
        "forged_ref",
        "wrong_shape",
        "wrong_identity",
        "observed_forgery",
    ],
)
def test_clause_witnesses_are_required_and_source_bound(policy, sources, mutation):
    sources = _isolated_sources(clause=True)
    policy = delta.derive_policy(*sources)
    left = _tables()
    right = copy.deepcopy(left)
    right[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]["clause_ref"] = _ref(
        candidate=True
    )
    witnesses = _witnesses(sources)
    if mutation == "missing_side":
        witnesses["clause_references"].pop("baseline")
    elif mutation == "missing_rule":
        witnesses["clause_references"]["candidate"].pop(RULE)
    elif mutation == "extra_rule":
        witnesses["clause_references"]["candidate"][OTHER_RULE] = _ref(candidate=True)
    elif mutation == "forged_ref":
        witnesses["clause_references"]["candidate"][RULE]["clause_key"] = "synthetic-forged"
    elif mutation == "wrong_shape":
        witnesses["clause_references"]["candidate"][RULE]["amount_try"] = 12.5
    elif mutation == "wrong_identity":
        witnesses["clause_source_identities"]["candidate"] = sources[0].identity
    else:
        right[REPORT][PATIENT]["materials"]["prose_bundling_violations"][0]["clause_ref"][
            "clause_coordinate"
        ] = "synthetic-forged"
    _reject(left, right, policy, sources, **witnesses)


@pytest.mark.parametrize("field", ["rule_type", "annex", "statutory_law"])
def test_clause_generator_default_fields_cannot_add_authority(policy, sources, field):
    witnesses = _witnesses(sources)
    witnesses["clause_references"]["candidate"][RULE][field] = "unverified-authority"
    _reject(_tables(), _tables(), policy, sources, **witnesses)


def test_full_source_derived_delta_remains_non_authorizing(policy, sources, capsys):
    left = _tables()
    right = copy.deepcopy(left)
    for table in (REPORT, BILL_REPORT):
        row = next(iter(right[table].values()))
        row["lab"]["normative_cost_try"] = None
        row["materials"]["rule_source"] = NEW_SOURCE
        row["materials"]["pre_auth_required"][0]["note"] = "Flag only"
        row["materials"]["kdv_price_reviews"][0]["note"] = NEW_KDV
        material = row["materials"]["prose_bundling_violations"][0]
        material["message"] = NEW_MESSAGE
        material["gate_b_sources"] = ["3.1.1.(10)"]
        material["clause_ref"] = _ref(candidate=True)
        row["recommended_actions"][0]["detail"] = NEW_MESSAGE
    right[COHORT]["rows"][0]["detail"] = NEW_MESSAGE
    result = _measure(left, right, policy, sources)
    summary = result.safe_summary()
    assert summary["changed_cell_count"] == 17
    assert len(summary["change_counts"]) == 8
    assert summary["change_counts"]["material_action_detail_source_pair"] == 3
    assert summary["deployment_admitted"] is summary["semantic_release_admitted"] is False
    for forbidden in (
        PATIENT,
        CLAIM,
        OLD_MESSAGE,
        NEW_MESSAGE,
        "12.5",
        "prose_bundling_violations",
    ):
        assert forbidden not in json.dumps(summary) + repr(result)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    "constructor", ["LabOptimization(0.0)", "LabOptimization(normative_cost_try=0.0)"]
)
def test_explicit_constructor_money_is_not_a_never_computed_default(constructor):
    old, new = _source_files(candidate=False), _source_files(candidate=True)
    for files in (old, new):
        files[BILLING + "claim_lab.py"] = (
            "def _optimize_lab_billing_from_claims(claims):\n    return " + constructor + "\n"
        ).encode()
    with pytest.raises(delta.MeasurementRejected):
        delta.derive_policy(_bundle(old, candidate=False), _bundle(new, candidate=True))


def test_omitted_clause_arguments_cannot_measure(policy):
    with pytest.raises((delta.MeasurementRejected, TypeError)):
        delta.measure_delta(_tables(), _tables(), policy)


@pytest.mark.parametrize(
    "mutation",
    [
        "predicate",
        "action",
        "rule_inventory",
        "manifest_unknown_rule",
        "lab_computed",
        "lab_sibling",
        "merge_other_change",
        "actions",
        "cohort",
        "clause_generator",
        "preauth_catalog",
        "source_unknown_edit",
    ],
)
def test_changed_source_semantics_cannot_derive_policy(mutation):
    before = _source_files(candidate=False)
    after = _source_files(candidate=True)
    if mutation in ("predicate", "action", "rule_inventory"):
        value = json.loads(after[RULES])
        if mutation == "predicate":
            value["rules"][0]["predicate"]["mode"] = "pay"
        elif mutation == "action":
            value["rules"][0]["action"]["kind"] = "pay"
        else:
            value["rules"].reverse()
        after[RULES] = _json(value)
    elif mutation == "manifest_unknown_rule":
        value = json.loads(after[MANIFEST])
        value["clause_traces"][0]["linked_rule_ids"] = ["UNKNOWN-SYNTHETIC-RULE"]
        after[MANIFEST] = _json(value)
    elif mutation == "lab_computed":
        for files in (before, after):
            files[BILLING + "claim_lab.py"] = (
                b"def _optimize_lab_billing_from_claims(claims):\n    result = LabOptimization()\n    result.normative_cost_try = 0.0\n    return result\n"
            )
    elif mutation == "lab_sibling":
        after[BILLING + "types.py"] = after[BILLING + "types.py"].replace(
            b"computed_total_try: float = 0.0", b"computed_total_try: float = 1.0"
        )
    elif mutation == "merge_other_change":
        after[BILLING + "lab_bill_merge.py"] += b"extra_behavior = True\n"
    elif mutation == "actions":
        after[BILLING + "billing_actions.py"] += b"extra_behavior = True\n"
    elif mutation == "cohort":
        after[BILLING + "cohort_compliance.py"] = after[BILLING + "cohort_compliance.py"].replace(
            b"action.get('detail')", b"action.get('amount_try')"
        )
    elif mutation == "clause_generator":
        after["src/bilun/domain/prose_rules/clause_linking.py"] += b"extra_behavior = True\n"
    elif mutation == "preauth_catalog":
        after[BILLING + "claim_materials.py"] = after[BILLING + "claim_materials.py"].replace(
            b"Catalog citation", b"Changed catalog authority"
        )
    else:
        after[BILLING + "patient_report.py"] += b"extra_behavior = True\n"
    with pytest.raises(delta.MeasurementRejected):
        delta.derive_policy(_bundle(before, candidate=False), _bundle(after, candidate=True))


@pytest.mark.parametrize("path", [RULES, MANIFEST])
@pytest.mark.parametrize(
    "malformed",
    [
        b'{"rules": [], "rules": []}',
        b'{"value": NaN}',
        b'{"value": Infinity}',
        b'{"value": -Infinity}',
    ],
)
def test_source_json_rejects_duplicates_and_nonfinite(path, malformed):
    before = _source_files(candidate=False)
    after = _source_files(candidate=True)
    after[path] = malformed
    with pytest.raises(delta.MeasurementRejected):
        delta.derive_policy(_bundle(before, candidate=False), _bundle(after, candidate=True))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_projection_nonfinite_is_rejected_even_if_unchanged(policy, sources, value):
    left = _tables()
    left[REPORT][PATIENT]["known_nonzero_try"] = value
    _reject(left, copy.deepcopy(left), policy, sources)


@pytest.mark.parametrize(
    "mutation",
    ["digest", "missing_file", "extra_file", "missing_digest", "extra_digest", "mutable_bytes"],
)
def test_source_bundle_validates_exact_bytes_roster_and_pins(mutation):
    files = _source_files(candidate=False)
    digests = {path: hashlib.sha256(body).hexdigest() for path, body in files.items()}
    if mutation == "digest":
        digests[RULES] = "0" * 64
    elif mutation == "missing_file":
        files.pop(RULES)
    elif mutation == "extra_file":
        files["unowned.py"] = b"unsafe = True\n"
        digests["unowned.py"] = hashlib.sha256(files["unowned.py"]).hexdigest()
    elif mutation == "missing_digest":
        digests.pop(RULES)
    elif mutation == "extra_digest":
        digests["unowned.py"] = "0" * 64
    else:
        files[RULES] = bytearray(files[RULES])
    with pytest.raises(delta.MeasurementRejected):
        delta.SourceBundle.create("a" * 40, files, digests)


def test_bundle_copies_caller_mapping_without_importing_source():
    files = _source_files(candidate=False)
    bundle = _bundle(files, candidate=False)
    files[RULES] = b"changed after creation"
    candidate = _bundle(_source_files(candidate=True), candidate=True)
    policy = delta.derive_policy(bundle, candidate)
    result = _measure(_tables(), _tables(), policy, (bundle, candidate))
    assert result.safe_summary()["changed_cell_count"] == 0


def test_measurement_changes_digest_by_location_without_exporting_values(policy, sources):
    left = _tables()
    a = copy.deepcopy(left)
    b = copy.deepcopy(left)
    a[REPORT][PATIENT]["lab"]["normative_cost_try"] = None
    b[BILL_REPORT][BILL_KEY]["lab"]["normative_cost_try"] = None
    saved_left = copy.deepcopy(left)
    saved_a = copy.deepcopy(a)
    saved_b = copy.deepcopy(b)
    first = _measure(left, a, policy, sources).safe_summary()
    second = _measure(left, b, policy, sources).safe_summary()
    assert (left, a, b) == (saved_left, saved_a, saved_b)
    assert first["change_counts"] == second["change_counts"]
    assert first["delta_sha256"] != second["delta_sha256"]
    assert json.dumps(first).find(PATIENT) == -1
    assert json.dumps(second).find(CLAIM) == -1


def _missing_context_source(*, candidate):
    return (
        "from synthetic import finalize_report_totals\n"
        "def compute_patient_billing_report(pid, *, claim_context=None):\n"
        "    report = BillingActionReport(patient_id=pid)\n"
        "    if claim_context is None:\n"
        "        if SUT_REQUIRE_CLAIM_LINES:\n"
        "            set_missing_inputs_report(report)\n"
        + ("" if candidate else "            finalize_report_totals(report, claim_context=None)\n")
        + "            finalize_report_exactness(report)\n"
        "            return report\n"
        "    assert claim_context is not None\n"
        "    report.lab, capture = compute_lab_and_capture_gap_from_claims(claim_context)\n"
        "    finalize_report_totals(report, claim_context=claim_context)\n"
        "    finalize_report_exactness(report)\n"
        "    return report\n"
    ).encode()


def _missing_context_sources():
    old, new = _source_files(candidate=False), _source_files(candidate=True)
    for files, candidate in ((old, False), (new, True)):
        files[BILLING + "patient_report.py"] = _missing_context_source(candidate=candidate)
    return old, new


@pytest.mark.parametrize("changed", [False, True])
def test_exact_missing_context_removal_is_in_policy_digest_without_data_allowance(changed):
    old, new = _missing_context_sources()
    if not changed:
        new[BILLING + "patient_report.py"] = old[BILLING + "patient_report.py"]
    sources = _bundle(old, candidate=False), _bundle(new, candidate=True)
    policy = delta.derive_policy(*sources)
    document = json.loads(policy._json)
    expected = "remove_missing_context_totals_finalization" if changed else "unchanged"
    assert document["patient_report_transform"] == expected
    assert hashlib.sha256(policy._json.encode()).hexdigest() == policy.sha256
    summary = _measure(_tables(), _tables(), policy, sources).safe_summary()
    assert summary["changed_cell_count"] == 0
    assert summary["change_counts"] == {}
    assert summary["deployment_admitted"] is False
    assert summary["semantic_release_admitted"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "outer_condition",
        "inner_condition",
        "wrong_owner",
        "wrong_report_argument",
        "wrong_call",
        "wrong_keyword",
        "positional_context",
        "extra_keyword",
        "wrong_return",
        "old_sequence_order",
        "new_sequence_order",
        "duplicate_call",
        "duplicate_branch",
        "duplicate_owner",
        "extra_branch_statement",
        "inner_else",
        "outer_else",
        "populated_finalization",
        "wrong_branch_removal",
        "import",
        "signature",
        "medula_counter",
        "other_statement",
        "lab_producer",
    ],
)
def test_missing_context_source_proof_rejects_every_other_transformation(mutation):
    old, new = _missing_context_sources()
    path = BILLING + "patient_report.py"
    missing = b"            set_missing_inputs_report(report)\n"
    totals = b"            finalize_report_totals(report, claim_context=None)\n"
    exactness = b"            finalize_report_exactness(report)\n"
    populated = b"    finalize_report_totals(report, claim_context=claim_context)\n"
    if mutation in ("outer_condition", "inner_condition", "wrong_owner", "wrong_return"):
        before, after = {
            "outer_condition": (b"if claim_context is None:", b"if claim_context is not None:"),
            "inner_condition": (b"if SUT_REQUIRE_CLAIM_LINES:", b"if not SUT_REQUIRE_CLAIM_LINES:"),
            "wrong_owner": (b"def compute_patient_billing_report(", b"def another_report("),
            "wrong_return": (b"            return report", b"            return None"),
        }[mutation]
        for files in (old, new):
            files[path] = files[path].replace(before, after)
    elif mutation in (
        "wrong_report_argument",
        "wrong_call",
        "wrong_keyword",
        "positional_context",
        "extra_keyword",
    ):
        replacement = {
            "wrong_report_argument": b"finalize_report_totals(other_report, claim_context=None)",
            "wrong_call": b"finalize_other_totals(report, claim_context=None)",
            "wrong_keyword": b"finalize_report_totals(report, context=None)",
            "positional_context": b"finalize_report_totals(report, None)",
            "extra_keyword": b"finalize_report_totals(report, claim_context=None, extra=True)",
        }[mutation]
        old[path] = old[path].replace(totals, b"            " + replacement + b"\n")
    elif mutation == "old_sequence_order":
        old[path] = old[path].replace(missing + totals, totals + missing)
    elif mutation == "new_sequence_order":
        new[path] = new[path].replace(missing + exactness, exactness + missing)
    elif mutation == "duplicate_call":
        old[path] = old[path].replace(totals, totals + totals)
    elif mutation == "duplicate_branch":
        for files, candidate in ((old, False), (new, True)):
            branch = (
                b"    if claim_context is None:\n"
                b"        if SUT_REQUIRE_CLAIM_LINES:\n"
                + missing
                + (b"" if candidate else totals)
                + exactness
                + b"            return report\n"
            )
            files[path] = files[path].replace(branch, branch + branch)
    elif mutation == "duplicate_owner":
        for files in (old, new):
            files[path] += files[path]
    elif mutation == "extra_branch_statement":
        for files in (old, new):
            files[path] = files[path].replace(
                missing, missing + b"            extra_guard(report)\n"
            )
    elif mutation in ("inner_else", "outer_else"):
        statement = (
            b"        else:\n            return None\n"
            if mutation == "inner_else"
            else b"    else:\n        return None\n"
        )
        for files in (old, new):
            files[path] = files[path].replace(
                b"    assert claim_context is not None\n",
                statement + b"    assert claim_context is not None\n",
            )
    elif mutation == "populated_finalization":
        new[path] = new[path].replace(
            populated, b"    finalize_report_totals(report, claim_context=None)\n"
        )
    elif mutation == "wrong_branch_removal":
        new[path] = old[path].replace(populated, b"")
    elif mutation == "import":
        new[path] = new[path].replace(b"from synthetic import", b"from other_source import")
    elif mutation == "signature":
        new[path] = new[path].replace(
            b"pid, *, claim_context", b"pid, extra=None, *, claim_context"
        )
    elif mutation == "medula_counter":
        new[path] = new[path].replace(populated, b"    report.medula_counter = 1\n" + populated)
    elif mutation == "other_statement":
        new[path] += b"other_behavior = True\n"
    elif mutation == "lab_producer":
        new[path] = new[path].replace(
            b"compute_lab_and_capture_gap_from_claims(claim_context)",
            b"other_lab_producer(claim_context)",
        )
    sources = _bundle(old, candidate=False), _bundle(new, candidate=True)
    with pytest.raises(delta.MeasurementRejected):
        delta.derive_policy(*sources)


@pytest.mark.parametrize(
    "field,before,after",
    [
        ("known_zero_try", 0.0, None),
        ("known_nonzero_try", 12.5, None),
        ("known_nonzero_try", 12.5, 12.6),
        ("known_zero_try", 0.0, 0),
        ("clinical_result", "not_evaluated", "evaluated"),
        ("result_count", 0, 1),
        ("build_id", "synthetic-old-build", "synthetic-new-build"),
        ("data_source", "synthetic-old-source", "synthetic-new-source"),
        ("normative_cost_try", 0.0, None),
    ],
)
def test_missing_context_source_proof_adds_no_financial_clinical_metadata_allowance(
    field, before, after
):
    old, new = _missing_context_sources()
    sources = _bundle(old, candidate=False), _bundle(new, candidate=True)
    policy = delta.derive_policy(*sources)
    left, right = _tables(), _tables()
    left[REPORT][PATIENT][field] = before
    right[REPORT][PATIENT][field] = after
    _reject(left, right, policy, sources)


def _historical_link_sources():
    old, new = _source_files(candidate=False), _source_files(candidate=True)
    for files in (old, new):
        document = json.loads(files[RULES])
        document["rules"][0]["gate_b_sources"] = ["3.1.2.c#01234567", "3.2.1.A.(2)"]
        document["rules"][1]["gate_b_sources"] = ["3.1.4.x#89abcdef"]
        files[RULES] = _json(document)
    return old, new


@pytest.mark.parametrize(
    "refs",
    [
        ["3.1.2.c#01234567"],
        ["3.2.1.A.(2)"],
        ["3.1.4.\u00e7"],
        ["3.1.2.c#01234567", "3.2.1.A.(2)"],
    ],
)
def test_identical_owner_bound_historical_links_are_preserved_without_delta(refs):
    old, new = _historical_link_sources()
    for files in (old, new):
        document = json.loads(files[RULES])
        document["rules"][0]["gate_b_sources"] = refs
        files[RULES] = _json(document)
    sources = _bundle(old, candidate=False), _bundle(new, candidate=True)
    policy = delta.derive_policy(*sources)
    assert json.loads(policy._json)["rules"][RULE]["gate_sources"] == [refs, refs]
    tables = _tables()
    for table, row in ((REPORT, PATIENT), (BILL_REPORT, BILL_KEY)):
        tables[table][row]["materials"]["prose_bundling_violations"][0]["gate_b_sources"] = refs
    summary = _measure(tables, copy.deepcopy(tables), policy, sources).safe_summary()
    assert summary["changed_cell_count"] == 0
    assert summary["change_counts"] == {}
    assert summary["deployment_admitted"] is False
    assert summary["semantic_release_admitted"] is False


@pytest.mark.parametrize(
    "mutation", ["changed", "reordered", "appended", "deleted", "key_removed", "owner_swapped"]
)
def test_changed_historical_links_never_receive_the_unchanged_exception(mutation):
    old, new = _historical_link_sources()
    document = json.loads(new[RULES])
    rule, other = document["rules"]
    refs = rule["gate_b_sources"]
    if mutation == "changed":
        refs[0] = "3.1.2.c#76543210"
    elif mutation == "reordered":
        refs.reverse()
    elif mutation == "appended":
        refs.append("3.1.1.(10)")
    elif mutation == "deleted":
        refs.pop()
    elif mutation == "key_removed":
        rule.pop("gate_b_sources")
    elif mutation == "owner_swapped":
        rule["gate_b_sources"], other["gate_b_sources"] = other["gate_b_sources"], refs
    new[RULES] = _json(document)
    with pytest.raises(delta.MeasurementRejected):
        delta.derive_policy(_bundle(old, candidate=False), _bundle(new, candidate=True))


@pytest.mark.parametrize(
    "value",
    [None, "3.1.2.c#01234567", {}, [""], [1], [None], [[]], ["same", "same"]],
)
def test_equal_historical_links_still_reject_null_bad_shape_entries_and_duplicates(value):
    old, new = _historical_link_sources()
    for files in (old, new):
        document = json.loads(files[RULES])
        document["rules"][0]["gate_b_sources"] = value
        files[RULES] = _json(document)
    with pytest.raises(delta.MeasurementRejected):
        delta.derive_policy(_bundle(old, candidate=False), _bundle(new, candidate=True))


@pytest.mark.parametrize("missing_side", ["baseline", "candidate"])
def test_historical_link_presence_change_cannot_use_the_unchanged_exception(missing_side):
    old, new = _historical_link_sources()
    files = old if missing_side == "baseline" else new
    document = json.loads(files[RULES])
    document["rules"][0].pop("gate_b_sources")
    files[RULES] = _json(document)
    with pytest.raises(delta.MeasurementRejected):
        delta.derive_policy(_bundle(old, candidate=False), _bundle(new, candidate=True))


@pytest.mark.parametrize(
    "left,right",
    [
        (None, None),
        (None, ["3.1.1.(10)"]),
        (["3.1.1.(12)"], ["3.1.1.(10)"]),
        (["3.1.1.(10)"], ["3.1.1.(10)"]),
        ([], []),
    ],
)
def test_original_absent_and_numeric_material_link_paths_remain_valid(left, right):
    old, new = _source_files(candidate=False), _source_files(candidate=True)
    for files, value in ((old, left), (new, right)):
        document = json.loads(files[RULES])
        if value is None:
            document["rules"][0].pop("gate_b_sources")
        else:
            document["rules"][0]["gate_b_sources"] = value
        files[RULES] = _json(document)
    delta.derive_policy(_bundle(old, candidate=False), _bundle(new, candidate=True))


def test_original_numeric_material_link_removal_guard_is_preserved():
    old, new = _source_files(candidate=False), _source_files(candidate=True)
    document = json.loads(new[RULES])
    document["rules"][0].pop("gate_b_sources")
    new[RULES] = _json(document)
    with pytest.raises(delta.MeasurementRejected, match="material_gate_removed"):
        delta.derive_policy(_bundle(old, candidate=False), _bundle(new, candidate=True))


@pytest.mark.parametrize("field", ["known_zero_try", "clinical_result", "result_count", "build_id"])
def test_unchanged_historical_source_links_add_no_observed_data_allowance(field):
    old, new = _historical_link_sources()
    sources = _bundle(old, candidate=False), _bundle(new, candidate=True)
    policy = delta.derive_policy(*sources)
    left, right = _tables(), _tables()
    if field == "known_zero_try":
        right[REPORT][PATIENT][field] = None
    elif field == "clinical_result":
        right[REPORT][PATIENT][field] = "evaluated"
    elif field == "result_count":
        left[REPORT][PATIENT][field] = 0
        right[REPORT][PATIENT][field] = 1
    elif field == "build_id":
        left[REPORT][PATIENT][field] = "synthetic-old-build"
        right[REPORT][PATIENT][field] = "synthetic-new-build"
    _reject(left, right, policy, sources)


@pytest.mark.parametrize("mutation", ["executable_rule", "rule_document", "module", "rule_owner"])
def test_unchanged_historical_links_cannot_hide_other_source_changes(mutation):
    old, new = _historical_link_sources()
    if mutation == "module":
        new[BILLING + "billing_actions.py"] += b"extra_behavior = True\n"
    else:
        document = json.loads(new[RULES])
        if mutation == "executable_rule":
            document["rules"][0]["predicate"]["mode"] = "pay"
        elif mutation == "rule_document":
            document["extra_behavior"] = True
        elif mutation == "rule_owner":
            document["rules"][0]["rule_id"] = "OTHER-SYNTHETIC-OWNER"
        new[RULES] = _json(document)
    with pytest.raises(delta.MeasurementRejected):
        delta.derive_policy(_bundle(old, candidate=False), _bundle(new, candidate=True))


def _build_tables():
    left = _tables()
    row = {
        "patient_id": PATIENT,
        "build_id": OLD_BUILD,
        "known_zero_try": 0.0,
        "known_nonzero_try": 12.5,
        "count": 2,
        "status": "not_evaluated",
        "timestamp": "synthetic-stable-timestamp",
        "data_source": {"claim_source": "synthetic-stable-input"},
        "nested": {"build_id": "private-stable-nested-build"},
    }
    left[OWN_TABLES[0]] = {PATIENT: copy.deepcopy(row)}
    left[OWN_TABLES[1]] = {BILL_KEY: copy.deepcopy(row)}
    left[OWN_TABLES[2]] = copy.deepcopy(row)
    right = copy.deepcopy(left)
    for table in OWN_TABLES:
        _build_owner(right, table)["build_id"] = NEW_BUILD
    return left, right


def _build_owner(tables, table):
    key = PATIENT if table == OWN_TABLES[0] else BILL_KEY
    return tables[table] if table == OWN_TABLES[2] else tables[table][key]


def _build_context(left, right, sources):
    return {
        side: {
            "source_identity": sources[index].identity,
            "build_id": OLD_BUILD if index == 0 else NEW_BUILD,
            "cache_sha256": ("c" if index == 0 else "d") * 64,
            "raw_projection_sha256": delta._digest(tables),
            "builder_source": {
                "path": BUILD_PATH,
                "bytes": BUILDER,
                "sha256": hashlib.sha256(BUILDER).hexdigest(),
            },
        }
        for index, (side, tables) in enumerate((("baseline", left), ("candidate", right)))
    }


def test_three_source_owned_build_deltas_are_private_and_non_authorizing(policy, sources, capsys):
    left, right = _build_tables()
    context = _build_context(left, right, sources)
    snapshot = copy.deepcopy((left, right, context))
    result = _measure(left, right, policy, sources, own_build_context=context)
    summary = result.safe_summary()
    assert summary["change_counts"] == {"own_build_bookkeeping": 3}
    assert summary["changed_cell_count"] == 3
    assert {(item._table, item._path) for item in result._differences} == {
        (table, ("build_id",)) for table in OWN_TABLES
    }
    assert {item._row for item in result._differences} == {PATIENT, BILL_KEY, "index"}
    assert all(
        item._before == json.dumps(OLD_BUILD) and item._after == json.dumps(NEW_BUILD)
        for item in result._differences
    )
    for key in (
        "deployment_admitted",
        "semantic_release_admitted",
        "external_witness_generation_attested",
        "own_source_cache_equivalence_attested",
    ):
        assert summary[key] is False
    for forbidden in (PATIENT, CLAIM, OLD_BUILD, NEW_BUILD, "synthetic-stable-input", "12.5"):
        assert forbidden not in repr(result) + json.dumps(summary)
    assert (left, right, context) == snapshot
    assert capsys.readouterr() == ("", "")


def test_old_context_free_contract_and_digest_are_unchanged(policy, sources):
    left = _tables()
    implicit = _measure(left, copy.deepcopy(left), policy, sources).safe_summary()
    explicit = _measure(
        left, copy.deepcopy(left), policy, sources, own_build_context=None
    ).safe_summary()
    assert implicit == explicit
    assert implicit["delta_sha256"] == delta._digest([])
    left, right = _build_tables()
    _reject(left, right, policy, sources)


def test_unchanged_correct_owners_are_validated_and_context_pins_bind_digest(policy, sources):
    left, right = _build_tables()
    for table in OWN_TABLES:
        _build_owner(right, table)["build_id"] = OLD_BUILD
    context = _build_context(left, right, sources)
    context["candidate"]["build_id"] = OLD_BUILD
    before = _measure(left, right, policy, sources, own_build_context=context).safe_summary()
    assert before["change_counts"] == {}
    # A valid-format cache hash remains a declaration, not independently attested.
    context["candidate"]["cache_sha256"] = "e" * 64
    after = _measure(left, right, policy, sources, own_build_context=context).safe_summary()
    assert before["delta_sha256"] != after["delta_sha256"]
    assert after["own_source_cache_equivalence_attested"] is False
    builder = context["baseline"]["builder_source"]["bytes"] + b"\n# same source-owned routes\n"
    for side in context.values():
        side["builder_source"].update(bytes=builder, sha256=hashlib.sha256(builder).hexdigest())
    rebound = _measure(left, right, policy, sources, own_build_context=context).safe_summary()
    assert rebound["delta_sha256"] != after["delta_sha256"]


@pytest.mark.parametrize("table", OWN_TABLES)
@pytest.mark.parametrize("unchanged", [False, True])
def test_wrong_direct_build_owner_is_never_skipped(policy, sources, table, unchanged):
    left, right = _build_tables()
    _build_owner(left, table)["build_id"] = "private-foreign-owner"
    if unchanged:
        _build_owner(right, table)["build_id"] = "private-foreign-owner"
    _reject(left, right, policy, sources, own_build_context=_build_context(left, right, sources))


@pytest.mark.parametrize("table", OWN_TABLES)
@pytest.mark.parametrize(
    "field,value",
    [
        ("known_zero_try", None),
        ("known_nonzero_try", 13.5),
        ("count", 3),
        ("status", "evaluated"),
        ("timestamp", "changed-timestamp"),
        ("data_source", {"claim_source": "changed-input"}),
        ("nested", {"build_id": NEW_BUILD}),
    ],
)
def test_build_context_does_not_permit_sibling_or_nested_drift(
    policy, sources, table, field, value
):
    left, right = _build_tables()
    _build_owner(right, table)[field] = value
    _reject(left, right, policy, sources, own_build_context=_build_context(left, right, sources))


@pytest.mark.parametrize("table", OWN_TABLES)
@pytest.mark.parametrize(
    "mutation", ["missing_owner", "extra_field", "missing_field", "wrong_row_type"]
)
def test_build_owner_field_sets_and_shapes_remain_exact(policy, sources, table, mutation):
    left, right = _build_tables()
    if mutation == "missing_owner":
        del _build_owner(left, table)["build_id"]
        del _build_owner(right, table)["build_id"]
    elif mutation == "extra_field":
        _build_owner(right, table)["extra"] = True
    elif mutation == "missing_field":
        del _build_owner(right, table)["count"]
    elif table == OWN_TABLES[2]:
        right[table] = []
    else:
        right[table][PATIENT if table == OWN_TABLES[0] else BILL_KEY] = []
    _reject(left, right, policy, sources, own_build_context=_build_context(left, right, sources))


@pytest.mark.parametrize("table", OWN_TABLES[:2])
@pytest.mark.parametrize("mutation", ["missing", "extra", "empty_key", "wrong_map_type"])
def test_build_owner_map_inventory_is_exact(policy, sources, table, mutation):
    left, right = _build_tables()
    key = PATIENT if table == OWN_TABLES[0] else BILL_KEY
    if mutation == "missing":
        del right[table][key]
    elif mutation == "extra":
        right[table]["private-extra-row"] = copy.deepcopy(right[table][key])
    elif mutation == "empty_key":
        for side in (left, right):
            side[table][""] = side[table].pop(key)
    else:
        right[table] = []
    _reject(left, right, policy, sources, own_build_context=_build_context(left, right, sources))


@pytest.mark.parametrize("table", sorted(delta.TABLES - set(OWN_TABLES)))
def test_build_context_does_not_allow_other_table_bookkeeping(policy, sources, table):
    left, right = _build_tables()
    if table in (REPORT, BILL_REPORT):
        row = PATIENT if table == REPORT else BILL_KEY
        right[table][row]["build_id"] = NEW_BUILD
    else:
        right[table]["build_id"] = NEW_BUILD
    _reject(left, right, policy, sources, own_build_context=_build_context(left, right, sources))


@pytest.mark.parametrize(
    "mutation",
    [
        "side_missing",
        "side_extra",
        "side_type",
        "field_missing",
        "field_extra",
        "context_type",
        "source_identity",
        "source_type",
        "build_empty",
        "build_type",
        "cache_digest",
        "cache_type",
        "projection_digest",
        "projection_type",
        "builder_missing",
        "builder_extra",
        "builder_type",
        "builder_path",
        "builder_bytes",
        "builder_digest",
        "builder_hash_mismatch",
        "builder_changed",
    ],
)
def test_build_context_exact_schema_and_pins(policy, sources, mutation):
    left, right = _build_tables()
    context = _build_context(left, right, sources)
    row = context["candidate"]
    witness = row["builder_source"]
    if mutation == "side_missing":
        del context["baseline"]
    elif mutation == "side_extra":
        context["extra"] = copy.deepcopy(row)
    elif mutation == "side_type":
        context["candidate"] = []
    elif mutation == "context_type":
        context = []
    elif mutation == "field_missing":
        del row["cache_sha256"]
    elif mutation == "field_extra":
        row["attested"] = True
    elif mutation == "source_identity":
        row["source_identity"] = sources[0].identity
    elif mutation == "source_type":
        row["source_identity"] = None
    elif mutation == "build_empty":
        row["build_id"] = ""
    elif mutation == "build_type":
        row["build_id"] = 1
    elif mutation == "cache_digest":
        row["cache_sha256"] = "not-a-digest"
    elif mutation == "cache_type":
        row["cache_sha256"] = None
    elif mutation == "projection_digest":
        row["raw_projection_sha256"] = "f" * 64
    elif mutation == "projection_type":
        row["raw_projection_sha256"] = False
    elif mutation == "builder_missing":
        del witness["bytes"]
    elif mutation == "builder_extra":
        witness["attested"] = True
    elif mutation == "builder_type":
        row["builder_source"] = []
    elif mutation == "builder_path":
        witness["path"] = "src/bilun/cache/other.py"
    elif mutation == "builder_bytes":
        witness["bytes"] = BUILDER.decode()
    elif mutation == "builder_digest":
        witness["sha256"] = "invalid"
    elif mutation == "builder_hash_mismatch":
        witness["sha256"] = "f" * 64
    elif mutation == "builder_changed":
        raw = BUILDER + b"\n# changed candidate source\n"
        witness.update(bytes=raw, sha256=hashlib.sha256(raw).hexdigest())
    _reject(left, right, policy, sources, own_build_context=context)


@pytest.mark.parametrize(
    "before,after",
    [
        (b"normalized['build_id'] = build_id", b"normalized['build_id'] = other_id"),
        (
            b"normalized['build_id'] = build_id",
            b"normalized['build_id'] = build_id\n    normalized['build_id'] = build_id",
        ),
        (b"normalized = json_ready(detail)", b"normalized = json_ready(other_detail)"),
        (b"return normalized", b"return detail"),
        (
            b"_normalize_wavea_bill_detail(bill_key, report, build_id)",
            b"_normalize_wavea_bill_detail(bill_key, report, other_id)",
        ),
        (b"'wavea_bill_evidence_detail', build_id, rows", b"'other_table', build_id, rows"),
        (
            b"'wavea_bill_evidence_detail', build_id, rows",
            b"'wavea_bill_evidence_detail', other_id, rows",
        ),
        (
            b"dump_json_compact(attach_bilun_data_source_metadata(detail, data_source))",
            b"dump_json_compact(other_detail)",
        ),
        (b"for detail in wavea_details.values():", b"for detail in other_details.values():"),
        (b"detail['build_id'] = build.build_id", b"detail['build_id'] = other_id"),
        (b"'wavea_evidence_detail', build.build_id", b"'other_table', build.build_id"),
        (b"'wavea_evidence_detail', build.build_id", b"'wavea_evidence_detail', other_id"),
        (
            b"for patient_id, detail in wavea_details.items()",
            b"for patient_id, detail in other_details.items()",
        ),
        (
            b"con, raw_bill_reports, build.build_id, sut_data_source_metadata",
            b"con, raw_bill_reports, other_id, sut_data_source_metadata",
        ),
        (
            b"wavea_index = build_full_wavea_evidence_index(wavea_details)",
            b"wavea_index = build_full_wavea_evidence_index(other_details)",
        ),
        (b"wavea_index['build_id'] = build.build_id", b"wavea_index['build_id'] = other_id"),
        (b"'wavea_evidence_index', build.build_id", b"'other_table', build.build_id"),
        (
            b"attach_bilun_data_source_metadata(wavea_index, sut_data_source_metadata)",
            b"attach_bilun_data_source_metadata(other_index, sut_data_source_metadata)",
        ),
        (b"def run_build(args):", b"def run_build(other_args):"),
        (b"def run_build(args):", b"def run_build(args):\n    pass\ndef run_build(args):"),
    ],
)
def test_each_builder_owner_assignment_and_writer_route_is_source_bound(
    policy, sources, before, after
):
    left, right = _build_tables()
    context = _build_context(left, right, sources)
    raw = BUILDER.replace(before, after, 1)
    assert raw != BUILDER
    for row in context.values():
        row["builder_source"].update(bytes=raw, sha256=hashlib.sha256(raw).hexdigest())
    _reject(left, right, policy, sources, own_build_context=context)


# Parse-only source fixtures; no builder or domain function is executed.
RAW_BUILDER = (
    b'''def _without_wavea_detail(report: object) -> object:
    """Avoid serializing the exhaustive drill-down into default report rows."""
    if dataclasses.is_dataclass(report):
        return {
            field.name: getattr(report, field.name)
            for field in dataclasses.fields(report)
            if field.name != "wavea_evidence_detail"
        }
    if isinstance(report, dict):
        return {key: value for key, value in report.items() if key != "wavea_evidence_detail"}
    return report

def _normalize_wavea_bill_detail(bill_key: str, report: object, build_id: str) -> dict[str, Any]:
    """Validate a bill's own predicate context before storing its evidence."""
    if not isinstance(bill_key, str) or "::" not in bill_key:
        raise ValueError("Bill Wave A evidence lacks a composite claim key")
    patient_id, claim_id = bill_key.split("::", 1)
    if not patient_id or not claim_id:
        raise ValueError("Bill Wave A evidence has an empty patient or claim ID")
    detail = (
        report.get("wavea_evidence_detail")
        if isinstance(report, dict)
        else getattr(report, "wavea_evidence_detail", None)
    )
    if detail is None:
        raise ValueError(f"Bill {bill_key} lacks complete Wave A evidence")
    normalized = json_ready(detail)
    validate_full_wavea_evidence_detail(normalized, patient_id)
    inventory = normalized["claim_scope_inventory"]
    if inventory["context_state"] != "available" or [
        row["claim_id"] for row in inventory["claims"]
    ] != [claim_id]:
        raise ValueError(f"Bill {bill_key} Wave A scope differs from its claim")
    normalized["build_id"] = build_id
    return normalized

'''
    + b"def _write_wavea_bill_details"
    + BUILDER.split(b"def _write_wavea_bill_details", 1)[1]
)
RAW_ROUTE = b"""        raw_bill_reports = ctx.get("bill_billing_reports", {})
        bill_billing_reports = json_ready(
            {bill_key: _without_wavea_detail(report) for bill_key, report in raw_bill_reports.items()}
        )
        for report in bill_billing_reports.values():
            report.pop("wavea_evidence_detail", None)
        write_json_payload_rows(con, "patient_bill_billing_report_rows", build.build_id,
            {bill_key: attach_bilun_data_source_metadata(report, sut_data_source_metadata)
             for bill_key, report in bill_billing_reports.items()})
"""
RAW_BUILDER = RAW_BUILDER.replace(b"    try:\n", b"    try:\n" + RAW_ROUTE, 1)


@pytest.fixture
def raw_sources():
    files = _missing_context_sources()
    for side in files:
        side[BILLING + "types.py"] += (
            b'\n@dataclass\nclass BillingActionReport:\n    patient_id: str = ""\n'
        )
    return _bundle(files[0], candidate=False), _bundle(files[1], candidate=True)


@pytest.fixture
def raw_policy(raw_sources):
    return delta.derive_policy(*raw_sources)


def _raw_bill_tables():
    left, right = _build_tables()
    for tables in (left, right):
        del tables[BILL_REPORT][BILL_KEY]["claim_id"]
        tables[OWN_TABLES[1]][BILL_KEY]["claim_scope_inventory"] = {
            "context_state": "available",
            "claims": [
                {"claim_id": CLAIM, "material_line_ids": ["synthetic-line-a", "synthetic-line-b"]}
            ],
        }
    return left, right


def _raw_context(left, right, sources, builder=RAW_BUILDER):
    context = _build_context(left, right, sources)
    for side in context.values():
        side["builder_source"].update(bytes=builder, sha256=hashlib.sha256(builder).hexdigest())
    return context


def _raw_measure(left, right, policy, sources, **overrides):
    options = {
        "own_build_context": _raw_context(left, right, sources),
        "raw_bill_cache_identity": True,
    }
    options.update(overrides)
    return _measure(left, right, policy, sources, **options)


def _raw_reject(left, right, policy, sources, **overrides):
    options = {
        "own_build_context": _raw_context(left, right, sources),
        "raw_bill_cache_identity": True,
    }
    options.update(overrides)
    _reject(left, right, policy, sources, **options)


def test_actual_source_shaped_raw_bill_identity_is_private_and_input_preserving(
    raw_policy, raw_sources, capsys
):
    left, right = _raw_bill_tables()
    context = _raw_context(left, right, raw_sources)
    snapshot = copy.deepcopy((left, right, context))
    result = _raw_measure(left, right, raw_policy, raw_sources, own_build_context=context)
    summary = result.safe_summary()
    assert summary["change_counts"] == {"own_build_bookkeeping": 3}
    assert set(summary) == {
        "status",
        "changed_cell_count",
        "change_counts",
        "source_policy_sha256",
        "delta_sha256",
        "deployment_admitted",
        "semantic_release_admitted",
        "external_witness_generation_attested",
        "own_source_cache_equivalence_attested",
    }
    assert all(
        summary[name] is False for name in summary if name.endswith(("admitted", "attested"))
    )
    pins, routes = delta._own_build_context(
        context,
        {"baseline": left, "candidate": right},
        {"baseline": raw_sources[0].identity, "candidate": raw_sources[1].identity},
    )
    assert summary["delta_sha256"] == delta._digest(
        {
            "differences": [
                [item._table, item._row, list(item._path), item._before, item._after, item._kind]
                for item in result._differences
            ],
            "own_build_context": pins,
            "build_owner_routes": routes,
            "raw_bill_cache_identity": {
                "enabled": True,
                "source_proof_sha256": delta._raw_bill_identity_source_proof(
                    dict(raw_sources[0]._files),
                    dict(raw_sources[1]._files),
                    RAW_BUILDER,
                ),
            },
        }
    )
    for value in (PATIENT, CLAIM, OLD_BUILD, NEW_BUILD, "claim_scope_inventory", "12.5"):
        assert value not in json.dumps(summary) + repr(result)
    assert (left, right, context) == snapshot
    assert capsys.readouterr() == ("", "")
    assert "claim_id" not in left[BILL_REPORT][BILL_KEY]
    assert "claim_id" not in right[BILL_REPORT][BILL_KEY]


def test_false_raw_mode_preserves_845_context_and_context_free_digests(policy, sources):
    left, right = _build_tables()
    context = _build_context(left, right, sources)
    implicit = _measure(left, right, policy, sources, own_build_context=context)
    explicit = _measure(
        left, right, policy, sources, own_build_context=context, raw_bill_cache_identity=False
    )
    assert implicit.safe_summary() == explicit.safe_summary()
    pins, routes = delta._own_build_context(
        context,
        {"baseline": left, "candidate": right},
        {"baseline": sources[0].identity, "candidate": sources[1].identity},
    )
    assert implicit.safe_summary()["delta_sha256"] == delta._digest(
        {
            "differences": [
                [item._table, item._row, list(item._path), item._before, item._after, item._kind]
                for item in implicit._differences
            ],
            "own_build_context": pins,
            "build_owner_routes": routes,
        }
    )
    tables = _tables()
    assert _measure(tables, tables, policy, sources, raw_bill_cache_identity=False).safe_summary()[
        "delta_sha256"
    ] == delta._digest([])


@pytest.mark.parametrize("mode", [None, 0, 1, "true", [], {}])
def test_raw_identity_mode_requires_exact_bool(policy, sources, mode):
    _reject(_tables(), _tables(), policy, sources, raw_bill_cache_identity=mode)


def test_raw_mode_requires_context_and_does_not_weaken_normal_mode(raw_policy, raw_sources):
    left, right = _raw_bill_tables()
    _raw_reject(left, right, raw_policy, raw_sources, own_build_context=None)
    _raw_reject(left, right, raw_policy, raw_sources, raw_bill_cache_identity=False)


@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize(
    "mutation",
    [
        "claim_null",
        "claim_string",
        "claim_number",
        "patient_missing",
        "patient_wrong",
        "patient_type",
        "key_separator",
        "key_patient_empty",
        "key_claim_empty",
        "key_patient_wrong",
        "key_claim_wrong",
        "report_row_missing",
        "report_row_extra",
        "evidence_missing",
        "evidence_type",
        "evidence_row_missing",
        "evidence_row_extra",
        "evidence_patient_missing",
        "evidence_patient_wrong",
        "evidence_patient_type",
        "inventory_missing",
        "inventory_type",
        "state_missing",
        "state_wrong",
        "claims_missing",
        "claims_type",
        "claims_empty",
        "claims_extra",
        "claim_row_type",
        "scope_claim_missing",
        "scope_claim_null",
        "scope_claim_empty",
        "scope_claim_wrong",
        "scope_claim_type",
    ],
)
def test_raw_bill_identity_is_strict_on_both_sides(raw_policy, raw_sources, side, mutation):
    left, right = _raw_bill_tables()
    tables = (left, right)[side]
    report = tables[BILL_REPORT][BILL_KEY]
    evidence = tables[OWN_TABLES[1]]
    detail = evidence[BILL_KEY]
    inventory = detail["claim_scope_inventory"]
    if mutation in ("claim_null", "claim_string", "claim_number"):
        report["claim_id"] = {"claim_null": None, "claim_string": CLAIM, "claim_number": 2}[
            mutation
        ]
    elif mutation.startswith("patient_"):
        if mutation == "patient_missing":
            del report["patient_id"]
        else:
            report["patient_id"] = "foreign-patient" if mutation == "patient_wrong" else 2
    elif mutation.startswith("key_"):
        key = {
            "key_separator": PATIENT + CLAIM,
            "key_patient_empty": "::" + CLAIM,
            "key_claim_empty": PATIENT + "::",
            "key_patient_wrong": "foreign-patient::" + CLAIM,
            "key_claim_wrong": PATIENT + "::foreign-claim",
        }[mutation]
        # Change both row inventories together so the identity guard, not a
        # simple baseline/candidate inventory difference, must reject the key.
        for value in (left, right):
            value[BILL_REPORT][key] = value[BILL_REPORT].pop(BILL_KEY)
            value[OWN_TABLES[1]][key] = value[OWN_TABLES[1]].pop(BILL_KEY)
    elif mutation.startswith("report_row_"):
        if mutation == "report_row_missing":
            del tables[BILL_REPORT][BILL_KEY]
        else:
            tables[BILL_REPORT]["foreign-row"] = copy.deepcopy(report)
    elif mutation == "evidence_missing":
        tables[OWN_TABLES[1]] = {}
    elif mutation == "evidence_type":
        tables[OWN_TABLES[1]] = []
    elif mutation == "evidence_row_missing":
        del evidence[BILL_KEY]
    elif mutation == "evidence_row_extra":
        evidence["foreign-row"] = copy.deepcopy(detail)
    elif mutation.startswith("evidence_patient_"):
        if mutation == "evidence_patient_missing":
            del detail["patient_id"]
        else:
            detail["patient_id"] = "foreign-patient" if mutation == "evidence_patient_wrong" else 2
    elif mutation == "inventory_missing":
        del detail["claim_scope_inventory"]
    elif mutation == "inventory_type":
        detail["claim_scope_inventory"] = []
    elif mutation == "state_missing":
        del inventory["context_state"]
    elif mutation == "state_wrong":
        inventory["context_state"] = "missing"
    elif mutation == "claims_missing":
        del inventory["claims"]
    elif mutation == "claims_type":
        inventory["claims"] = {}
    elif mutation == "claims_empty":
        inventory["claims"] = []
    elif mutation == "claims_extra":
        inventory["claims"].append(copy.deepcopy(inventory["claims"][0]))
    elif mutation == "claim_row_type":
        inventory["claims"] = [CLAIM]
    elif mutation == "scope_claim_missing":
        del inventory["claims"][0]["claim_id"]
    else:
        inventory["claims"][0]["claim_id"] = {
            "scope_claim_null": None,
            "scope_claim_empty": "",
            "scope_claim_wrong": "foreign-claim",
            "scope_claim_type": 2,
        }[mutation]
    _raw_reject(left, right, raw_policy, raw_sources)


@pytest.mark.parametrize(
    "mutation", ["money", "count", "type", "order", "nested", "status", "field_extra"]
)
@pytest.mark.parametrize("table", [BILL_REPORT, OWN_TABLES[1]])
def test_raw_identity_does_not_allow_unknown_sibling_deltas(
    raw_policy, raw_sources, mutation, table
):
    left, right = _raw_bill_tables()
    for tables in (left, right):
        tables[table][BILL_KEY]["ordered_sibling"] = ["first", "second"]
        tables[table][BILL_KEY]["nested_identity"] = {"claim_id": CLAIM}
    row = right[table][BILL_KEY]
    if mutation == "money":
        row["known_nonzero_try"] = 13.5
    elif mutation == "count":
        row["unowned_count"] = 2
        left[table][BILL_KEY]["unowned_count"] = 1
    elif mutation == "type":
        row["known_zero_try"] = 0
    elif mutation == "order":
        row["ordered_sibling"].reverse()
    elif mutation == "nested":
        row["nested_identity"]["claim_id"] = "foreign-claim"
    elif mutation == "status":
        row["unowned_status"] = "evaluated"
        left[table][BILL_KEY]["unowned_status"] = "not_evaluated"
    else:
        row["new_sibling"] = True
    _raw_reject(left, right, raw_policy, raw_sources)


@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize(
    "before,after",
    [
        (b'patient_id: str = ""', b"patient_id: int = 0"),
        (b'patient_id: str = ""', b'other_id: str = ""'),
        (b'patient_id: str = ""', b'patient_id: str = ""\n    claim_id: str = ""'),
        (b'patient_id: str = ""', b'patient_id: str = ""\n    patient_id: str = ""'),
        (b'patient_id: str = ""', b'patient_id: str = ""\n    patient_id = "foreign"'),
        (b"@dataclass\nclass BillingActionReport:", b"class BillingActionReport:"),
        (b"BillingActionReport(patient_id=pid)", b"BillingActionReport(patient_id=other_pid)"),
        (b"BillingActionReport(patient_id=pid)", b"BillingActionReport(pid)"),
        (
            b"BillingActionReport(patient_id=pid)",
            b"BillingActionReport(patient_id=pid, claim_id=other_id)",
        ),
        (
            b"    report = BillingActionReport(patient_id=pid)",
            b"    report = BillingActionReport(patient_id=pid)\n    report = BillingActionReport(patient_id=pid)",
        ),
        (
            b"    report = BillingActionReport(patient_id=pid)",
            b"    if injected:\n        report = BillingActionReport(patient_id=pid)",
        ),
    ],
)
def test_raw_source_schema_and_constructor_proof_checks_both_bound_sides(
    raw_sources, side, before, after
):
    files = [dict(source._files) for source in raw_sources]
    path = BILLING + (
        "types.py" if before.startswith((b"patient_id:", b"@dataclass")) else "patient_report.py"
    )
    changed = files[side][path].replace(before, after, 1)
    assert changed != files[side][path]
    files[side][path] = changed
    with pytest.raises(delta.MeasurementRejected):
        delta._raw_bill_identity_source_proof(*files, RAW_BUILDER)


@pytest.mark.parametrize(
    "before,after",
    [
        (b'bill_key.split("::", 1)', b'bill_key.split("::")'),
        (b"if not patient_id or not claim_id:", b"if not patient_id:"),
        (b'report.get("wavea_evidence_detail")', b'report.get("other_detail")'),
        (
            b"validate_full_wavea_evidence_detail(normalized, patient_id)",
            b"validate_full_wavea_evidence_detail(normalized, other_patient)",
        ),
        (b"    validate_full_wavea_evidence_detail(normalized, patient_id)\n", b""),
        (b'inventory["context_state"] != "available"', b'inventory["context_state"] != "missing"'),
        (b"] != [claim_id]:", b"] != []:"),
        (b"    normalized = json_ready(detail)", b"    normalized = json_ready(detail)\n    pass"),
        (b"    return normalized", b"    return normalized\n    pass"),
        (
            b'if field.name != "wavea_evidence_detail"',
            b'if field.name not in ("wavea_evidence_detail", "patient_id")',
        ),
        (b"    return report\n", b'    return {**report, "claim_id": "injected"}\n'),
        (b'ctx.get("bill_billing_reports", {})', b'ctx.get("billing_reports", {})'),
        (b"{bill_key: _without_wavea_detail(report)", b"{other_key: _without_wavea_detail(report)"),
        (
            b"_without_wavea_detail(report) for bill_key, report",
            b"_without_wavea_detail(other_report) for bill_key, report",
        ),
        (b'report.pop("wavea_evidence_detail", None)', b'report.pop("patient_id", None)'),
        (b'"patient_bill_billing_report_rows", build.build_id', b'"other_table", build.build_id'),
        (
            b'"patient_bill_billing_report_rows", build.build_id',
            b'"patient_bill_billing_report_rows", other_build',
        ),
        (
            b"attach_bilun_data_source_metadata(report, sut_data_source_metadata)",
            b"attach_bilun_data_source_metadata(other_report, sut_data_source_metadata)",
        ),
        (
            b"for bill_key, report in bill_billing_reports.items()",
            b"for bill_key, report in other_reports.items()",
        ),
        (
            b"        for report in bill_billing_reports.values():",
            b"        bill_billing_reports = foreign_reports\n        for report in bill_billing_reports.values():",
        ),
        (
            b"        bill_billing_reports = json_ready(",
            b'        raw_bill_reports["foreign"] = injected\n        bill_billing_reports = json_ready(',
        ),
        (
            b'        write_json_payload_rows(con, "patient_bill_billing_report_rows"',
            b'        report["claim_id"] = injected\n        write_json_payload_rows(con, "patient_bill_billing_report_rows"',
        ),
        (
            b"def _without_wavea_detail(report: object) -> object:",
            b"def _without_wavea_detail(report: object) -> object:\n    pass\ndef _without_wavea_detail(report: object) -> object:",
        ),
        (
            b"def _normalize_wavea_bill_detail(bill_key:",
            b"def _normalize_wavea_bill_detail():\n    pass\ndef _normalize_wavea_bill_detail(bill_key:",
        ),
    ],
)
def test_raw_builder_complete_functions_and_mapping_routes_are_frozen(
    raw_policy, raw_sources, before, after
):
    left, right = _raw_bill_tables()
    builder = RAW_BUILDER.replace(before, after, 1)
    assert builder != RAW_BUILDER
    _raw_reject(
        left,
        right,
        raw_policy,
        raw_sources,
        own_build_context=_raw_context(left, right, raw_sources, builder),
    )


def test_raw_builder_duplicate_write_and_bypass_order_are_rejected(raw_policy, raw_sources):
    left, right = _raw_bill_tables()
    prefix, suffix = RAW_BUILDER.split(RAW_ROUTE)
    raw_assignment = RAW_ROUTE.splitlines(keepends=True)[0]
    raw_write = (
        b"        write_json_payload_rows"
        + RAW_ROUTE.split(b"        write_json_payload_rows", 1)[1]
    )
    for builder in (
        prefix + RAW_ROUTE + RAW_ROUTE + suffix,
        prefix + RAW_ROUTE + raw_write + suffix,
        prefix + RAW_ROUTE[len(raw_assignment) :] + raw_assignment + suffix,
    ):
        _raw_reject(
            left,
            right,
            raw_policy,
            raw_sources,
            own_build_context=_raw_context(left, right, raw_sources, builder),
        )
