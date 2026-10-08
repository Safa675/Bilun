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
        BILLING + "claim_lab.py": b"def _optimize_lab_billing_from_claims(claims):\n    return LabOptimization()\n",
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
        BILLING + "cohort_compliance.py": b"def _row_from_action(action):\n    return {'detail': action.get('detail')}\n",
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
