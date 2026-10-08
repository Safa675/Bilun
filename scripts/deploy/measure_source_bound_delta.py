"""Pure, non-authorizing measurement of narrowly source-owned cache deltas.

Inputs are supplied in memory. This module neither attests their external
generation nor grants source, semantic, clinical or deployment admission.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import wraps
from typing import Any

_BILLING = "src/bilun/domain/billing/"
_RULES = "data/gazette/prose_rules/material_bundling_prose.json"
_MANIFEST = "data/gazette/prose_manifests/L1.4_material_bundling_encoded_manifest.json"
SOURCE_PATHS = frozenset(
    {
        *(
            _BILLING + name + ".py"
            for name in (
                "types",
                "claim_materials",
                "billing_actions",
                "cohort_compliance",
                "claim_lab",
                "lab_bill_merge",
                "patient_report",
            )
        ),
        "src/bilun/domain/prose_rules/clause_linking.py",
        "src/bilun/domain/sut/rules_catalog.py",
        "src/bilun/domain/sut/clause_reference.py",
        _RULES,
        _MANIFEST,
    }
)
_REPORT_TABLES = frozenset({"patient_billing_report_rows", "patient_bill_billing_report_rows"})
TABLES = frozenset(
    {
        *_REPORT_TABLES,
        "wavea_evidence_detail",
        "wavea_bill_evidence_detail",
        "wavea_evidence_index",
        "cohort_compliance_index",
        "patient_detail_cache",
        "patient_outcome_base",
        "cohort_optimization_summary",
        "patient_alerts_summary",
        "cohort_recovery_summary",
        "cohort_sut_summary",
        "validation_payload",
        "patient_meta",
        "cohort_sut_exposure",
        "patient_alerts_payload",
        "patient_diagnoses",
        "patient_alert_rows",
        "patient_billing_reports",
    }
)
_SHA = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CITATION = re.compile(r"\u00a7[0-9.()/]+")
_COORDINATE = re.compile(r"[0-9]+(?:\.[0-9]+)*\.\([0-9]+\)")
_NULLABLE_FIELDS = {
    "LabOptimization": {"normative_cost_try"},
    "CopayOptimization": {
        "visit_copay_savings_try",
        "rx_copay_savings_try",
        "total_copay_savings_try",
        "patient_copay_waived_total_try",
        "patient_copay_try",
        "ilave_ucret_total_try",
    },
    "BillingActionReport": {
        "sgk_uplift_try",
        "compliance_adjustment_try",
        "audit_exposure_try",
        "capture_gap_try",
        "package_adequacy_review_try",
        "total_recoverable_try",
    },
}
_IDENTITY_FIELDS = frozenset(
    {
        "patient_id",
        "claim_id",
        "rule_id",
        "action_id",
        "finding_id",
        "evidence_id",
        "source_evidence_id",
        "drug_claim_line_id",
        "material_line_id",
        "procedure_line_id",
        "line_id",
        "evaluation_id",
    }
)
_MISSING = object()


class MeasurementRejected(ValueError):
    """A payload-free measurement guard failure, never an admission decision."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise MeasurementRejected(code)


def _payload_free(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except MeasurementRejected:
            raise
        except (
            ValueError,
            TypeError,
            KeyError,
            IndexError,
            AttributeError,
            RecursionError,
            OverflowError,
        ):
            raise MeasurementRejected("invalid_measurement_inputs") from None

    return guarded


def _typed(value: Any, depth: int = 0) -> None:
    _require(depth <= 128, "value_depth")
    if type(value) is dict:
        _require(all(type(key) is str for key in value), "mapping_key_type")
        for item in value.values():
            _typed(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _typed(item, depth + 1)
    else:
        _require(value is None or type(value) in (str, int, float, bool), "value_type")
        _require(type(value) is not float or math.isfinite(value), "nonfinite_number")


def _canonical(value: Any) -> str:
    _typed(value)
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _same(left: Any, right: Any) -> bool:
    return _canonical(left) == _canonical(right)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _document(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except MeasurementRejected:
        raise
    except (ValueError, UnicodeError):
        raise MeasurementRejected("source_json") from None
    _typed(value)
    _require(type(value) is dict, "source_document_shape")
    return value


def _tree(raw: bytes) -> ast.Module:
    try:
        return ast.parse(raw.decode("utf-8"))
    except (ValueError, SyntaxError, UnicodeError):
        raise MeasurementRejected("source_ast") from None


def _ast(value: ast.AST) -> str:
    return ast.dump(value, include_attributes=False)


def _node(tree: ast.Module, kind: type, name: str) -> Any:
    values = [node for node in tree.body if isinstance(node, kind) and node.name == name]
    _require(len(values) == 1, "source_definition")
    return values[0]


def _constant(tree: ast.Module, name: str) -> str:
    values = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
    ]
    _require(
        len(values) == 1
        and isinstance(values[0], ast.Constant)
        and type(values[0].value) is str
        and bool(values[0].value),
        "source_constant",
    )
    return values[0].value


def _citation_pair(old: Any, new: Any) -> bool:
    return (
        type(old) is str
        and type(new) is str
        and old != new
        and bool(_CITATION.search(old))
        and bool(_CITATION.search(new))
        and _CITATION.sub("", old) == _CITATION.sub("", new)
    )


@dataclass(frozen=True)
class SourceBundle:
    identity: str
    _files: tuple[tuple[str, bytes], ...] = field(repr=False)
    _digests: tuple[tuple[str, str], ...] = field(repr=False)

    @classmethod
    @_payload_free
    def create(
        cls, identity: str, files: Mapping[str, bytes], digests: Mapping[str, str]
    ) -> SourceBundle:
        _require(isinstance(files, Mapping) and isinstance(digests, Mapping), "source_bundle")
        value = cls(identity, tuple(sorted(files.items())), tuple(sorted(digests.items())))
        _sources(value)
        return value


def _sources(bundle: SourceBundle) -> dict[str, bytes]:
    _require(
        type(bundle) is SourceBundle
        and type(bundle.identity) is str
        and bool(_SHA.fullmatch(bundle.identity)),
        "source_identity",
    )
    files, digests = dict(bundle._files), dict(bundle._digests)
    _require(
        len(files) == len(bundle._files)
        and len(digests) == len(bundle._digests)
        and set(files) == set(digests) == SOURCE_PATHS,
        "source_roster",
    )
    for path, raw in files.items():
        expected = digests[path]
        _require(
            type(raw) is bytes
            and len(raw) <= 2_000_000
            and type(expected) is str
            and bool(_SHA256.fullmatch(expected))
            and hashlib.sha256(raw).hexdigest() == expected,
            "source_digest",
        )
    return files


def _rules_policy(old: dict, new: dict) -> dict:
    _require(type(old.get("rules")) is list and type(new.get("rules")) is list, "rule_roster")
    output, identities = {}, []
    for left, right in zip(old["rules"], new["rules"], strict=False):
        _require(
            type(left) is dict
            and type(right) is dict
            and type(left.get("rule_id")) is str
            and bool(left["rule_id"])
            and left["rule_id"] == right.get("rule_id")
            and left["rule_id"] not in output
            and type(left.get("action")) is dict
            and type(right.get("action")) is dict,
            "rule_identity",
        )
        rule = left["rule_id"]
        identities.append(rule)
        cleaned = []
        for row in (left, right):
            item = {key: value for key, value in row.items() if key != "gate_b_sources"}
            item["action"] = {
                key: value for key, value in row["action"].items() if key != "message_tr"
            }
            cleaned.append(item)
        _require(_same(*cleaned), "executable_material_rule_changed")
        a, b = left["action"].get("message_tr"), right["action"].get("message_tr")
        _require(
            type(a) is str and type(b) is str and (a == b or _citation_pair(a, b)),
            "material_message_source",
        )
        gates = [row.get("gate_b_sources") for row in (left, right)]
        for row, value in zip((left, right), gates, strict=True):
            _require(
                value is None
                and "gate_b_sources" not in row
                or type(value) is list
                and all(type(ref) is str and _COORDINATE.fullmatch(ref) for ref in value)
                and len(value) == len(set(value)),
                "material_gate_source",
            )
        _require(gates[1] is not None or gates[0] is None, "material_gate_removed")
        output[rule] = {
            "message": [a, b],
            "gate_sources": gates,
            "gate_present": ["gate_b_sources" in left, "gate_b_sources" in right],
        }
    _require(len(old["rules"]) == len(new["rules"]) == len(output), "rule_roster")
    _require(
        _same(
            {key: value for key, value in old.items() if key != "rules"},
            {key: value for key, value in new.items() if key != "rules"},
        ),
        "rule_document_changed",
    )
    return {"rules": output, "rule_order": identities}


def _manifest_policy(old: dict, new: dict, rules: dict) -> list[str]:
    left, right = old.get("clause_traces"), new.get("clause_traces")
    _require(
        type(left) is list and type(right) is list and len(left) == len(right), "manifest_shape"
    )
    indexes = []
    for rows in (left, right):
        index = {}
        for row in rows:
            _require(type(row) is dict and type(row.get("clause_id")) is str, "manifest_trace")
            linked = row.get("linked_rule_ids", [])
            _require(
                type(linked) is list
                and all(type(rule) is str and rule in rules for rule in linked)
                and len(linked) == len(set(linked)),
                "manifest_rule_owner",
            )
            for rule in linked:
                index.setdefault(rule, row["clause_id"])
        indexes.append(index)
    for a, b in zip(left, right, strict=True):
        _require(
            _same(
                {key: value for key, value in a.items() if key != "linked_rule_ids"},
                {key: value for key, value in b.items() if key != "linked_rule_ids"},
            ),
            "manifest_nonlink_changed",
        )
    _require(
        _same(
            {key: value for key, value in old.items() if key != "clause_traces"},
            {key: value for key, value in new.items() if key != "clause_traces"},
        ),
        "manifest_document_changed",
    )
    return sorted(
        rule
        for rule in indexes[0].keys() | indexes[1].keys()
        if indexes[0].get(rule) != indexes[1].get(rule)
    )


def _lab_policy(old: dict[str, bytes], new: dict[str, bytes]) -> list[str]:
    trees = [_tree(files[_BILLING + "types.py"]) for files in (old, new)]
    labs = [_node(tree, ast.ClassDef, "LabOptimization") for tree in trees]
    fields = [
        {
            node.target.id: node
            for node in lab.body
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        for lab in labs
    ]
    _require(
        set(fields[0]) == set(fields[1]) and "normative_cost_try" in fields[0], "lab_field_roster"
    )
    for index, (annotation, value) in enumerate((("float", "0.0"), ("float | None", "None"))):
        node = fields[index]["normative_cost_try"]
        _require(
            _ast(node.annotation) == _ast(ast.parse(annotation, mode="eval").body)
            and _ast(node.value) == _ast(ast.parse(value, mode="eval").body),
            "lab_default_transform",
        )
    converted = copy.deepcopy(trees[0])
    after_classes = {node.name: node for node in trees[1].body if isinstance(node, ast.ClassDef)}
    for cls in converted.body:
        if not isinstance(cls, ast.ClassDef) or cls.name not in _NULLABLE_FIELDS:
            continue
        target = after_classes.get(cls.name)
        _require(target is not None, "schema_class_roster")
        after = {
            node.target.id: node
            for node in target.body
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        for index, node in enumerate(cls.body):
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id in _NULLABLE_FIELDS[cls.name]
                and node.target.id in after
            ):
                other = after[node.target.id]
                if _ast(node) == _ast(other):
                    continue
                _require(
                    _ast(node.annotation) == _ast(ast.parse("float", mode="eval").body)
                    and _ast(node.value) == _ast(ast.parse("0.0", mode="eval").body)
                    and _ast(other.annotation) == _ast(ast.parse("float | None", mode="eval").body)
                    and _ast(other.value) == _ast(ast.parse("None", mode="eval").body),
                    "schema_default_transform",
                )
                cls.body[index] = copy.deepcopy(other)
    _require(_ast(converted) == _ast(trees[1]), "unknown_schema_change")
    claim = _tree(old[_BILLING + "claim_lab.py"])
    _require(
        old[_BILLING + "claim_lab.py"] == new[_BILLING + "claim_lab.py"]
        and not any(
            isinstance(node, ast.Attribute)
            and node.attr == "normative_cost_try"
            or isinstance(node, ast.Name)
            and node.id == "normative_cost_try"
            or isinstance(node, ast.Constant)
            and node.value == "normative_cost_try"
            for node in ast.walk(claim)
        ),
        "lab_producer_computes_normative",
    )
    producer = _node(claim, ast.FunctionDef, "_optimize_lab_billing_from_claims")
    constructors = [
        node
        for node in ast.walk(producer)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "LabOptimization"
    ]
    _require(
        bool(constructors) and all(not node.args and not node.keywords for node in constructors),
        "lab_default_producer",
    )
    merge_trees = [_tree(files[_BILLING + "lab_bill_merge.py"]) for files in (old, new)]
    before = ast.parse(
        "merged_lab.normative_cost_try = round(merged_lab.normative_cost_try + lab_result.normative_cost_try, 2)"
    ).body[0]
    after = ast.parse(
        "if lab_result.normative_cost_try is not None:\n    merged_lab.normative_cost_try = round((merged_lab.normative_cost_try or 0.0) + lab_result.normative_cost_try, 2)"
    ).body[0]

    class MergeOnly(ast.NodeTransformer):
        count = 0

        def visit_Assign(self, node):
            if _ast(node) == _ast(before):
                self.count += 1
                return copy.deepcopy(after)
            return self.generic_visit(node)

    transform = MergeOnly()
    merged = transform.visit(copy.deepcopy(merge_trees[0]))
    _require(transform.count == 1 and _ast(merged) == _ast(merge_trees[1]), "lab_merge_transform")
    report = _tree(old[_BILLING + "patient_report.py"])
    _require(
        old[_BILLING + "patient_report.py"] == new[_BILLING + "patient_report.py"],
        "lab_report_source",
    )
    writes = [
        node
        for node in ast.walk(report)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Tuple)
            and any(isinstance(item, ast.Attribute) and item.attr == "lab" for item in target.elts)
            for target in node.targets
        )
    ]
    _require(
        len(writes) == 1
        and isinstance(writes[0].value, ast.Call)
        and isinstance(writes[0].value.func, ast.Name)
        and writes[0].value.func.id == "compute_lab_and_capture_gap_from_claims",
        "lab_report_producer",
    )
    return sorted(fields[1])


def _material_policy(old: bytes, new: bytes) -> dict:
    trees = [_tree(raw) for raw in (old, new)]
    catalog = [_constant(tree, "_PREAUTH_NOTE") for tree in trees]
    _require(catalog[0] == catalog[1], "catalog_note_changed")
    flag = _constant(trees[1], "_PREAUTH_FLAG_NOTE")
    _require(flag != catalog[0], "flag_note_source")
    functions = [_node(tree, ast.FunctionDef, "precheck_materials_from_claims") for tree in trees]
    source_target = _ast(ast.parse("result.rule_source = ''").body[0].targets[0])
    sources = []
    for function in functions:
        values = [
            node.value
            for node in ast.walk(function)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Attribute)
            and _ast(node.targets[0]) == source_target
        ]
        _require(
            len(values) == 1
            and isinstance(values[0], ast.Constant)
            and type(values[0].value) is str,
            "material_rule_source",
        )
        sources.append(values[0].value)
    _require(sources[0] == sources[1] or _citation_pair(*sources), "material_rule_source")
    kdvs = [_node(tree, ast.FunctionDef, "_append_kdv_price_reviews") for tree in trees]
    suffixes = []
    for function in kdvs:
        strings = [
            node.value
            for node in ast.walk(function)
            if isinstance(node, ast.Constant) and type(node.value) is str
        ]
        _require(
            {"Billed amount exceeds EK-3 list price", " + KDV", " (KDV exempt path)"}
            <= set(strings),
            "kdv_note_source",
        )
        found = [text for text in strings if text.startswith(" (") and text.endswith(").")]
        _require(len(found) == 1, "kdv_suffix_source")
        suffixes.append(found[0])
    _require(suffixes[0] == suffixes[1] or _citation_pair(*suffixes), "kdv_suffix_source")
    expected_condition = _ast(
        ast.parse("code in preauth_codes or line.requires_pre_auth", mode="eval").body
    )

    class MaterialOnly(ast.NodeTransformer):
        conditions = 0
        notes = 0
        source_assignments = 0

        def visit_If(self, node):
            if _ast(node.test) == expected_condition:
                self.conditions += 1
                node = self.generic_visit(node)
                node.test = ast.parse(
                    "in_preauth_catalog or line.requires_pre_auth", mode="eval"
                ).body
                return [ast.parse("in_preauth_catalog = code in preauth_codes").body[0], node]
            return self.generic_visit(node)

        def visit_Dict(self, node):
            for index, (key, value) in enumerate(zip(node.keys, node.values, strict=True)):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "note"
                    and isinstance(value, ast.Name)
                    and value.id == "_PREAUTH_NOTE"
                ):
                    self.notes += 1
                    node.values[index] = ast.parse(
                        "_PREAUTH_NOTE if in_preauth_catalog else _PREAUTH_FLAG_NOTE", mode="eval"
                    ).body
            return self.generic_visit(node)

        def visit_Assign(self, node):
            if len(node.targets) == 1 and _ast(node.targets[0]) == source_target:
                self.source_assignments += 1
                node.value = ast.Constant(sources[1])
            return self.generic_visit(node)

    converted = copy.deepcopy(trees[0])
    function = _node(converted, ast.FunctionDef, "precheck_materials_from_claims")
    transform = MaterialOnly()
    transform.visit(function)
    _require(
        transform.conditions == transform.notes == transform.source_assignments == 1,
        "material_producer_transform",
    )
    kdv = _node(converted, ast.FunctionDef, "_append_kdv_price_reviews")
    target_kdv = kdvs[1]
    for node in ast.walk(kdv):
        if isinstance(node, ast.Constant) and node.value == suffixes[0]:
            node.value = suffixes[1]
    old_doc, new_doc = ast.get_docstring(kdv), ast.get_docstring(target_kdv)
    if old_doc != new_doc:
        _require(_citation_pair(old_doc, new_doc), "kdv_documentary_change")
        kdv.body[0] = copy.deepcopy(target_kdv.body[0])
    target = copy.deepcopy(trees[1])
    target.body = [
        node
        for node in target.body
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "_PREAUTH_FLAG_NOTE"
        )
    ]
    _require(_ast(converted) == _ast(target), "unknown_material_source_change")
    return {
        "catalog_note": catalog[0],
        "flag_note": flag,
        "rule_source": sources,
        "kdv_notes": [
            ["Billed amount exceeds EK-3 list price" + extra + suffix for suffix in suffixes]
            for extra in (" + KDV", " (KDV exempt path)")
        ],
    }


@dataclass(frozen=True)
class DeltaPolicy:
    sha256: str
    _baseline: SourceBundle = field(repr=False)
    _candidate: SourceBundle = field(repr=False)
    _json: str = field(repr=False)


@_payload_free
def derive_policy(baseline: SourceBundle, candidate: SourceBundle) -> DeltaPolicy:
    """Derive only the specified source transformations; never attest a release."""
    old, new = _sources(baseline), _sources(candidate)
    stable = SOURCE_PATHS - {
        _RULES,
        _MANIFEST,
        *(_BILLING + name + ".py" for name in ("types", "claim_materials", "lab_bill_merge")),
    }
    _require(all(old[path] == new[path] for path in stable), "stable_source_changed")
    actions = _tree(old[_BILLING + "billing_actions.py"])
    detail = _node(actions, ast.FunctionDef, "_material_row_detail")
    _require(
        any(isinstance(node, ast.Constant) and node.value == "note" for node in ast.walk(detail)),
        "action_note_projection",
    )
    collect = _node(actions, ast.FunctionDef, "collect_billing_actions")
    _require(
        all(
            any(isinstance(node, ast.Constant) and node.value == kind for node in ast.walk(collect))
            for kind in ("material_pre_auth", "material_prose_bundling")
        ),
        "action_kind_projection",
    )
    _require(
        sum(
            isinstance(node, ast.keyword)
            and node.arg == "detail"
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_material_row_detail"
            for node in ast.walk(collect)
        )
        == 1,
        "action_detail_projection",
    )
    row = _node(_tree(old[_BILLING + "cohort_compliance.py"]), ast.FunctionDef, "_row_from_action")
    _require(
        any(
            isinstance(node, ast.Dict)
            and any(
                isinstance(key, ast.Constant)
                and key.value == "detail"
                and _ast(value) == _ast(ast.parse("action.get('detail')", mode="eval").body)
                for key, value in zip(node.keys, node.values, strict=True)
            )
            for node in ast.walk(row)
        ),
        "cohort_detail_projection",
    )
    data = _rules_policy(_document(old[_RULES]), _document(new[_RULES]))
    data["clause_rules"] = _manifest_policy(
        _document(old[_MANIFEST]), _document(new[_MANIFEST]), data["rules"]
    )
    data["lab_fields"] = _lab_policy(old, new)
    data["materials"] = _material_policy(
        old[_BILLING + "claim_materials.py"], new[_BILLING + "claim_materials.py"]
    )
    data["source_identities"] = {"baseline": baseline.identity, "candidate": candidate.identity}
    data["source_digests"] = {
        "baseline": dict(baseline._digests),
        "candidate": dict(candidate._digests),
    }
    return DeltaPolicy(_digest(data), baseline, candidate, _canonical(data))


@dataclass(frozen=True)
class _Difference:
    _table: str = field(repr=False)
    _row: str = field(repr=False)
    _path: tuple = field(repr=False)
    _before: str = field(repr=False)
    _after: str = field(repr=False)
    _kind: str = field(repr=False)


@dataclass(frozen=True)
class DeltaMeasurement:
    _counts: tuple[tuple[str, int], ...] = field(repr=False)
    _policy_sha256: str = field(repr=False)
    _delta_sha256: str = field(repr=False)
    _differences: tuple[_Difference, ...] = field(repr=False)

    def safe_summary(self) -> dict:
        """Export only aggregate counts/digests and explicit non-admission flags."""
        return {
            "status": "source_bound_delta_measured_non_authorizing",
            "changed_cell_count": sum(count for _, count in self._counts),
            "change_counts": dict(self._counts),
            "source_policy_sha256": self._policy_sha256,
            "delta_sha256": self._delta_sha256,
            "deployment_admitted": False,
            "semantic_release_admitted": False,
            "external_witness_generation_attested": False,
            "own_source_cache_equivalence_attested": False,
        }


def _clause_witnesses(value: Any, identities: Any, policy: dict) -> dict:
    _require(
        type(value) is dict
        and set(value) == {"baseline", "candidate"}
        and _same(identities, policy["source_identities"]),
        "clause_witness_identity",
    )
    for side in ("baseline", "candidate"):
        rows = value[side]
        _require(
            type(rows) is dict and set(rows) == set(policy["clause_rules"]), "clause_witness_roster"
        )
        for ref in rows.values():
            _require(
                ref is None
                or type(ref) is dict
                and set(ref)
                == {
                    "clause_key",
                    "clause_coordinate",
                    "source_type",
                    "rule_type",
                    "annex",
                    "statutory_law",
                }
                and all(type(item) is str for item in ref.values())
                and bool(ref["clause_key"])
                and bool(ref["clause_coordinate"])
                and ref["source_type"] == "sut_clause"
                and ref["rule_type"] == ref["annex"] == ref["statutory_law"] == "",
                "clause_witness_shape",
            )
    _typed(value)
    return value


@_payload_free
def measure_delta(
    baseline: dict,
    candidate: dict,
    policy: DeltaPolicy,
    *,
    clause_references: dict,
    clause_source_identities: dict,
) -> DeltaMeasurement:
    """Reject unknown deltas; a complete measurement still grants no authority."""
    _require(type(policy) is DeltaPolicy, "policy_type")
    derived = derive_policy(policy._baseline, policy._candidate)
    _require(derived._json == policy._json and derived.sha256 == policy.sha256, "policy_derivation")
    data = _document(policy._json.encode())
    refs = _clause_witnesses(clause_references, clause_source_identities, data)
    _typed(baseline)
    _typed(candidate)
    _require(
        type(baseline) is dict
        and type(candidate) is dict
        and set(baseline) == set(candidate) == TABLES,
        "table_inventory",
    )
    differences = []
    actions = {}

    def add(table, row, path, left, right, kind):
        differences.append(
            _Difference(
                table,
                row,
                tuple(path),
                "missing" if left is _MISSING else _canonical(left),
                "missing" if right is _MISSING else _canonical(right),
                kind,
            )
        )

    def raw_rule(left, right, removed):
        rule = left.get("rule_id")
        _require(
            type(rule) is str and rule == right.get("rule_id") and rule in data["rules"],
            "material_rule_owner",
        )
        _require(
            _same(
                {key: value for key, value in left.items() if key not in removed},
                {key: value for key, value in right.items() if key not in removed},
            ),
            "material_rule_siblings",
        )
        expected = data["rules"][rule]
        for index, value in enumerate((left, right)):
            for key in ("message", "message_tr", "note"):
                if key in value:
                    _require(value[key] == expected["message"][index], "material_message_owner")
            if "gate_b_sources" in value:
                _require(
                    _same(value["gate_b_sources"], expected["gate_sources"][index]),
                    "material_gate_owner",
                )
            _require(
                ("gate_b_sources" in value) is expected["gate_present"][index],
                "material_gate_presence",
            )
        if rule in data["clause_rules"]:
            for side, value in (("baseline", left), ("candidate", right)):
                ref = refs[side][rule]
                _require(
                    _same(value.get("clause_ref"), ref)
                    and (
                        ref is None
                        and "clause_ref" not in value
                        and "source_type" not in value
                        or ref is not None
                        and value.get("source_type") == ref["source_type"]
                    ),
                    "observed_clause_witness",
                )
        return rule, expected

    def material_row(table, row, path, left, right):
        removable = {"message", "message_tr", "note", "gate_b_sources", "clause_ref", "source_type"}
        rule, expected = raw_rule(left, right, removable)
        _require(set(left) - removable == set(right) - removable, "material_row_inventory")
        for key in left.keys() | right.keys():
            a, b = left.get(key, _MISSING), right.get(key, _MISSING)
            if a is not _MISSING and b is not _MISSING and _same(a, b):
                continue
            if key in ("message", "message_tr", "note"):
                _require(
                    a is not _MISSING and b is not _MISSING and [a, b] == expected["message"],
                    "material_message_owner",
                )
                kind = "material_rule_message_citation"
            elif key == "gate_b_sources":
                _require(
                    b is not _MISSING
                    and _same(None if a is _MISSING else a, expected["gate_sources"][0])
                    and _same(b, expected["gate_sources"][1]),
                    "material_gate_owner",
                )
                kind = "material_rule_gate_source"
            elif key in ("clause_ref", "source_type"):
                _require(rule in data["clause_rules"], "clause_rule_owner")
                kind = "material_manifest_clause_reference"
            else:
                raise MeasurementRejected("unknown_material_delta")
            add(table, row, (*path, key), a, b, kind)

    def action_detail(report_old, report_new, left, right):
        _require(
            _same(
                {key: value for key, value in left.items() if key != "detail"},
                {key: value for key, value in right.items() if key != "detail"},
            )
            and left.get("surface") == "materials",
            "action_siblings",
        )
        kind = left.get("kind")
        source_list = {
            "material_pre_auth": "pre_auth_required",
            "material_prose_bundling": "prose_bundling_violations",
        }.get(kind)
        _require(source_list is not None and type(left.get("action_id")) is str, "action_owner")
        matches = []
        for index, source in enumerate(report_old.get("materials", {}).get(source_list, [])):
            expected = f"materials:{kind}:{source.get('claim_id')}:{index}"
            if left["action_id"] == expected:
                matches.append(index)
        _require(len(matches) == 1, "action_source_identity")
        index = matches[0]
        old_source = report_old["materials"][source_list][index]
        new_source = report_new["materials"][source_list][index]
        for action, source in ((left, old_source), (right, new_source)):
            _require(
                action.get("claim_id") == source.get("claim_id")
                and action.get("material_code")
                == (source.get("material_code") or source.get("sut_code")),
                "action_source_owner",
            )
            text = next(
                (
                    str(source[key])
                    for key in ("note", "detail", "message", "rule_id")
                    if source.get(key)
                ),
                None,
            )
            _require(action.get("detail") == text, "action_detail_source")

    def visit(table, row, path, left, right, report_old=None, report_new=None):
        if _same(left, right):
            return
        _require(type(left) is type(right), "changed_value_type")
        if type(left) is dict:
            if table in _REPORT_TABLES and path == ("lab",):
                _require(set(left) == set(right) == set(data["lab_fields"]), "lab_row_shape")
                _require(
                    type(left.get("normative_cost_try")) is float
                    and _same(left["normative_cost_try"], 0.0)
                    and right.get("normative_cost_try") is None
                    and _same(
                        {key: value for key, value in left.items() if key != "normative_cost_try"},
                        {key: value for key, value in right.items() if key != "normative_cost_try"},
                    ),
                    "lab_default_delta",
                )
                add(
                    table,
                    row,
                    (*path, "normative_cost_try"),
                    0.0,
                    None,
                    "lab_normative_never_computed_default",
                )
                return
            if (
                table in _REPORT_TABLES
                and len(path) == 3
                and path[:2] == ("materials", "prose_bundling_violations")
                and type(path[2]) is int
            ):
                material_row(table, row, path, left, right)
                return
            if (
                table in _REPORT_TABLES
                and len(path) == 2
                and path[0] == "recommended_actions"
                and type(path[1]) is int
            ):
                action_detail(report_old, report_new, left, right)
                add(
                    table,
                    row,
                    (*path, "detail"),
                    left.get("detail"),
                    right.get("detail"),
                    "material_action_detail_source_pair",
                )
                return
            if (
                table == "cohort_compliance_index"
                and len(path) == 2
                and path[0] == "rows"
                and type(path[1]) is int
            ):
                _require(
                    _same(
                        {key: value for key, value in left.items() if key != "detail"},
                        {key: value for key, value in right.items() if key != "detail"},
                    ),
                    "cohort_action_siblings",
                )
                key = (left.get("patient_id"), left.get("action_id"))
                _require(
                    key in actions
                    and left.get("surface") == left.get("source_surface") == "materials",
                    "cohort_action_source",
                )
                for value, action in zip((left, right), actions[key], strict=True):
                    _require(
                        all(
                            _same(value.get(name), action.get(name))
                            for name in ("action_id", "claim_id", "kind", "material_code", "detail")
                        ),
                        "cohort_action_source",
                    )
                add(
                    table,
                    row,
                    (*path, "detail"),
                    left.get("detail"),
                    right.get("detail"),
                    "material_action_detail_source_pair",
                )
                return
            _require(set(left) == set(right), "mapping_inventory")
            for key in sorted(left):
                _require(
                    key not in _IDENTITY_FIELDS or _same(left[key], right[key]),
                    "row_identity_changed",
                )
                visit(table, row, (*path, key), left[key], right[key], report_old, report_new)
            return
        if type(left) is list:
            _require(len(left) == len(right), "sequence_inventory")
            for index, (a, b) in enumerate(zip(left, right, strict=True)):
                visit(table, row, (*path, index), a, b, report_old, report_new)
            return
        if table in _REPORT_TABLES and path == ("materials", "rule_source"):
            _require([left, right] == data["materials"]["rule_source"], "material_source_owner")
            add(table, row, path, left, right, "material_rule_source_citation")
            return
        if (
            table in _REPORT_TABLES
            and len(path) == 4
            and path[0] == "materials"
            and path[3] == "note"
            and type(path[2]) is int
        ):
            parent_left = report_old["materials"][path[1]][path[2]]
            parent_right = report_new["materials"][path[1]][path[2]]
            _require(
                _same(
                    {key: value for key, value in parent_left.items() if key != "note"},
                    {key: value for key, value in parent_right.items() if key != "note"},
                ),
                "material_note_siblings",
            )
            if path[1] == "pre_auth_required":
                _require(
                    [left, right]
                    == [data["materials"]["catalog_note"], data["materials"]["flag_note"]],
                    "flag_note_owner",
                )
                kind = "material_flag_only_preauth_note"
            elif path[1] == "kdv_price_reviews":
                _require([left, right] in data["materials"]["kdv_notes"], "kdv_note_owner")
                kind = "material_kdv_note_citation"
            else:
                raise MeasurementRejected("unknown_material_note")
            add(table, row, path, left, right, kind)
            return
        raise MeasurementRejected("unknown_delta")

    for table in sorted(_REPORT_TABLES):
        old, new = baseline[table], candidate[table]
        _require(
            type(old) is dict and type(new) is dict and set(old) == set(new), "report_inventory"
        )
        for key in sorted(old):
            a, b = old[key], new[key]
            _require(
                type(a) is dict
                and type(b) is dict
                and type(a.get("patient_id")) is str
                and bool(a["patient_id"])
                and a["patient_id"] == b.get("patient_id"),
                "report_identity",
            )
            if table == "patient_bill_billing_report_rows":
                _require(
                    type(a.get("claim_id")) is str
                    and bool(a["claim_id"])
                    and a["claim_id"] == b.get("claim_id")
                    and key == a["patient_id"] + "::" + a["claim_id"],
                    "bill_identity",
                )
            else:
                _require(key == a["patient_id"], "patient_row_identity")
            visit(table, key, (), a, b, a, b)
            if table == "patient_billing_report_rows":
                old_actions, new_actions = (
                    a.get("recommended_actions", []),
                    b.get("recommended_actions", []),
                )
                _require(
                    type(old_actions) is list and type(new_actions) is list, "action_inventory"
                )
                for left, right in zip(old_actions, new_actions, strict=True):
                    _require(type(left) is dict and type(right) is dict, "action_shape")
                    identity = (a["patient_id"], left.get("action_id"))
                    _require(
                        type(identity[1]) is str and bool(identity[1]) and identity not in actions,
                        "action_identity",
                    )
                    actions[identity] = [left, right]
    for table in sorted(TABLES - _REPORT_TABLES):
        if table == "cohort_compliance_index":
            visit(table, "cohort", (), baseline[table], candidate[table])
        else:
            _require(_same(baseline[table], candidate[table]), "protected_table_changed")
    counts = {}
    for difference in differences:
        counts[difference._kind] = counts.get(difference._kind, 0) + 1
    witness_digest = _digest(
        [
            [item._table, item._row, list(item._path), item._before, item._after, item._kind]
            for item in differences
        ]
    )
    return DeltaMeasurement(
        tuple(sorted(counts.items())), policy.sha256, witness_digest, tuple(differences)
    )
