"""Python sources for the deterministic rule-surfacing audit."""

from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any
from .model import AuditContext, RuntimeCall
from .metadata import (
    EXPECTED_ANALYZE_CALLS,
    EXPECTED_REPORT_CALLS,
    NON_RUNTIME_IMPORTED_CALLS,
    BROAD_WRAPPED_CALLS,
)


_UNRESOLVED_STATIC_VALUE = object()


def _resolve_imports(ctx: AuditContext, path: Path, tree: ast.Module) -> dict[str, str]:
    current: list[str] | None = None
    imports: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                binding = alias.asname or alias.name.split(".", 1)[0]
                imports[binding] = alias.name if alias.asname else binding
            continue
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.level:
            if current is None:
                current = ctx.module_for_path(path).split(".")
            base = current[: -node.level]
            module = ".".join([*base, *node.module.split(".")])
        else:
            module = node.module
        for alias in node.names:
            imports[alias.asname or alias.name] = module
    return imports


def _resolve_qualified_imports(tree: ast.Module) -> dict[str, str]:
    imports: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            binding = alias.asname or alias.name.split(".", 1)[0]
            imports[binding] = alias.name if alias.asname else binding
    return imports


def _attribute_parts(node: ast.AST) -> list[str] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    return [current.id, *reversed(parts)]


def _call_target(
    node: ast.AST,
    imports: dict[str, str],
    qualified_imports: dict[str, str],
) -> tuple[str, str] | None:
    if isinstance(node, ast.Name):
        module = imports.get(node.id)
        return (node.id, module) if module is not None else None
    parts = _attribute_parts(node)
    if parts is None or len(parts) < 2:
        return None
    module = qualified_imports.get(parts[0])
    if module is None:
        return None
    suffix = parts[1:-1]
    qualified_module = ".".join((module, *suffix)) if suffix else module
    return parts[-1], qualified_module


def _report_targets(node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "report":
        return [node.attr]
    if isinstance(node, (ast.Tuple, ast.List)):
        result: list[str] = []
        for child in node.elts:
            result.extend(_report_targets(child))
        return result
    return []


def _ancestor_if_gates(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> tuple[str, ...]:
    gates: list[str] = []
    current = node
    while current in parents:
        parent = parents[current]
        if isinstance(parent, (ast.If, ast.IfExp)):
            text = ast.unparse(parent.test)
            if text not in gates:
                gates.append(text)
        current = parent
    return tuple(reversed(gates))


def _assignment_report_fields(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> tuple[str, ...]:
    current = node
    while current in parents:
        parent = parents[current]
        if isinstance(parent, ast.Assign):
            fields: list[str] = []
            for target in parent.targets:
                fields.extend(_report_targets(target))
            return tuple(fields)
        if isinstance(parent, ast.AnnAssign):
            return tuple(_report_targets(parent.target))
        if isinstance(parent, ast.stmt):
            return ()
        current = parent
    return ()


def _focused_specs(ctx: AuditContext) -> tuple[dict[str, tuple[tuple[str, str], ...]], frozenset[str]]:
    """Read the reviewed 18-group/32-ID projection contract without imports."""
    return _parse_focused_specs(
        ctx.focused_projection_path.read_text(encoding="utf-8"),
        str(ctx.focused_projection_path),
    )


@lru_cache(maxsize=8)
def _parse_focused_specs(
    source: str, filename: str
) -> tuple[dict[str, tuple[tuple[str, str], ...]], frozenset[str]]:
    tree = ast.parse(source, filename=filename)
    assignment = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "FOCUSED_RULE_SPECS"
        ),
        None,
    )
    if assignment is None or not isinstance(assignment.value, ast.Tuple):
        raise ValueError("focused projection spec inventory is missing")
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    rule_ids: set[str] = set()
    def spec_argument(arg: ast.AST, bindings: dict[str, Any]) -> str:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
        if isinstance(arg, ast.JoinedStr):
            pieces: list[str] = []
            for part in arg.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    pieces.append(part.value)
                elif (
                    isinstance(part, ast.FormattedValue)
                    and isinstance(part.value, ast.Name)
                    and part.value.id in bindings
                    and isinstance(bindings[part.value.id], str)
                    and part.format_spec is None
                    and part.conversion == -1
                ):
                    pieces.append(bindings[part.value.id])
                else:
                    raise ValueError("focused projection rule ID has dynamic interpolation")
            return "".join(pieces)
        raise ValueError("focused projection spec argument is not static")

    def expand(node: ast.AST, bindings: dict[str, Any]) -> list[tuple[str, str, str, str]]:
        if isinstance(node, ast.Starred) and isinstance(node.value, ast.GeneratorExp):
            generator = node.value
            if any(item.ifs or item.is_async for item in generator.generators):
                raise ValueError("focused projection spec generator is conditional")

            def walk_generators(index: int, values: dict[str, Any]) -> list[tuple[str, str, str, str]]:
                if index == len(generator.generators):
                    return expand(generator.elt, values)
                item = generator.generators[index]
                iterable = _resolve_static_value(item.iter, values)
                if not isinstance(iterable, (tuple, list)):
                    raise ValueError("focused projection spec generator source is dynamic")
                result: list[tuple[str, str, str, str]] = []
                for value in iterable:
                    next_values = dict(values)
                    if isinstance(item.target, ast.Name):
                        next_values[item.target.id] = value
                    elif (
                        isinstance(item.target, ast.Tuple)
                        and isinstance(value, (tuple, list))
                        and len(item.target.elts) == len(value)
                        and all(isinstance(target, ast.Name) for target in item.target.elts)
                    ):
                        next_values.update(
                            (target.id, member)
                            for target, member in zip(item.target.elts, value)
                        )
                    else:
                        raise ValueError("focused projection spec generator binding is dynamic")
                    result.extend(walk_generators(index + 1, next_values))
                return result

            return walk_generators(0, bindings)
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.func.id != "_spec"
            or len(node.args) < 4
        ):
            raise ValueError("focused projection spec is not statically auditable")
        return [tuple(spec_argument(arg, bindings) for arg in node.args[:4])]

    for node in assignment.value.elts:
        for group, rule_id, _line_kind, disposition in expand(node, {}):
            if rule_id in rule_ids:
                raise ValueError(f"duplicate focused projection rule ID: {rule_id}")
            rule_ids.add(rule_id)
            grouped[group].append((rule_id, disposition))
    bindings: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = _resolve_static_value(node.value, bindings)
        if value is _UNRESOLVED_STATIC_VALUE:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                bindings[target.id] = value
    non_emitting = bindings.get("NON_EMITTING_FOCUSED_RULE_IDS")
    if (
        len(grouped) != 18
        or len(rule_ids) != 32
        or not isinstance(non_emitting, frozenset)
        or len(non_emitting) != 3
        or not non_emitting <= rule_ids
    ):
        raise ValueError("focused projection group, identity, or non-emitting inventory drift")
    return {group: tuple(specs) for group, specs in grouped.items()}, non_emitting


def _focused_materializer_calls(ctx: AuditContext) -> dict[str, str]:
    """Prove each materializer group invokes its same-named detector."""
    tree = ast.parse(
        ctx.focused_materializer_path.read_text(encoding="utf-8"),
        filename=str(ctx.focused_materializer_path),
    )
    order = _static_module_binding(ctx.focused_materializer_path, "FOCUSED_GROUP_ORDER")
    specs, _ = _focused_specs(ctx)
    if (
        not isinstance(order, tuple)
        or len(order) != 18
        or len(set(order)) != len(order)
        or set(order) != set(specs)
    ):
        raise ValueError("focused materializer group order differs from the projection specs")
    imports = _resolve_imports(ctx, ctx.focused_materializer_path, tree)
    qualified_imports = _resolve_qualified_imports(tree)
    run_group = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_run_group"),
        None,
    )
    materializer = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "FocusedLegacyMaterializer"),
        None,
    )
    if run_group is None or materializer is None:
        raise ValueError("focused materializer call path is missing")
    methods = {
        node.name: node for node in materializer.body if isinstance(node, ast.FunctionDef)
    }
    if not (
        any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_run_group"
            for node in ast.walk(methods.get("rows", ast.Pass()))
        )
        and any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr == "rows"
            for node in ast.walk(methods.get("all_rows", ast.Pass()))
        )
    ):
        raise ValueError("focused materializer rows/all_rows no longer reach _run_group")
    mapping: dict[str, str] = {}
    for branch in ast.walk(run_group):
        if (
            not isinstance(branch, ast.If)
            or not isinstance(branch.test, ast.Compare)
            or not isinstance(branch.test.left, ast.Name)
            or branch.test.left.id != "group"
            or len(branch.test.ops) != 1
            or not isinstance(branch.test.ops[0], ast.Eq)
            or len(branch.test.comparators) != 1
            or not isinstance(branch.test.comparators[0], ast.Constant)
            or not isinstance(branch.test.comparators[0].value, str)
        ):
            continue
        group = branch.test.comparators[0].value
        direct = {
            name: module
            for body_node in branch.body
            for node in ast.walk(body_node)
            if isinstance(node, ast.Call)
            if (target := _call_target(node.func, imports, qualified_imports)) is not None
            for name, module in (target,)
            if name.startswith("detect_")
        }
        if group not in order or direct != {group: imports.get(group)}:
            raise ValueError(f"focused materializer detector call drift: {group} -> {direct}")
        if group in mapping:
            raise ValueError(f"duplicate focused materializer branch: {group}")
        mapping[group] = direct[group]
    if set(mapping) != set(order) or set(_direct_imported_calls(ctx, ctx.focused_materializer_path, "_run_group")) != set(order):
        raise ValueError("focused materializer detector inventory drift")
    return mapping


def discover_runtime_calls(ctx: AuditContext, path: Path, entrypoint: str) -> list[RuntimeCall]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = _resolve_imports(ctx, path, tree)
    qualified_imports = _resolve_qualified_imports(tree)
    fn = next(
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entrypoint
    )
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(fn):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    materializer_bindings = {
        target.id
        for node in ast.walk(fn)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and _call_target(node.value.func, imports, qualified_imports)
        == ("FocusedLegacyMaterializer", "src.bilun.domain.billing.focused_legacy_materializer")
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    focused_modules = _focused_materializer_calls(ctx) if materializer_bindings else {}
    focused_discovered: set[str] = set()
    broad_discovered: set[str] = set()

    grouped: dict[str, dict[str, Any]] = {}
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        target = _call_target(node.func, imports, qualified_imports)
        if (
            target is None
            and entrypoint == "analyze_claim"
            and isinstance(node.func, ast.Name)
            and node.func.id == "_broad_rows"
        ):
            if (
                len(node.args) != 2
                or node.keywords
                or not isinstance(node.args[0], ast.Constant)
                or not isinstance(node.args[0].value, str)
                or not isinstance(node.args[1], ast.Name)
            ):
                raise ValueError("broad wrapper call is not statically auditable")
            family = node.args[0].value
            detector = node.args[1].id
            if BROAD_WRAPPED_CALLS.get(family) != detector or detector not in imports:
                raise ValueError(f"broad wrapper detector call drift: {family} -> {detector}")
            broad_discovered.add(family)
            target = (detector, imports[detector])
        if (
            target is None
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "rows"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in materializer_bindings
        ):
            if (
                len(node.args) != 1
                or node.keywords
                or not isinstance(node.args[0], ast.Constant)
                or not isinstance(node.args[0].value, str)
                or node.args[0].value not in focused_modules
            ):
                raise ValueError("focused materializer group call is not statically auditable")
            group = node.args[0].value
            target = (group, focused_modules[group])
            focused_discovered.add(group)
        if target is None:
            continue
        name, module = target
        if name in NON_RUNTIME_IMPORTED_CALLS:
            continue
        row = grouped.setdefault(
            name,
            {
                "module": module,
                "lines": set(),
                "gate_paths": set(),
                "report_fields": set(),
            },
        )
        row["lines"].add(node.lineno)
        site_gates = _ancestor_if_gates(node, parents)
        row["gate_paths"].add(" AND ".join(site_gates) if site_gates else "always")
        row["report_fields"].update(_assignment_report_fields(node, parents))

    if materializer_bindings and focused_discovered != set(focused_modules):
        raise ValueError(
            "focused materializer entrypoint coverage drift: "
            f"missing={sorted(set(focused_modules) - focused_discovered)}"
        )
    if (
        entrypoint == "analyze_claim"
        and path.resolve() == ctx.engine_path.resolve()
        and broad_discovered != set(BROAD_WRAPPED_CALLS)
    ):
        raise ValueError(
            "broad wrapper entrypoint coverage drift: "
            f"missing={sorted(set(BROAD_WRAPPED_CALLS) - broad_discovered)}"
        )

    return [
        RuntimeCall(
            entrypoint=entrypoint,
            callable=name,
            module=row["module"],
            lines=tuple(sorted(row["lines"])),
            gates=tuple(sorted(row["gate_paths"])),
            report_fields=tuple(sorted(row["report_fields"])),
        )
        for name, row in sorted(grouped.items())
    ]


def assert_known_runtime_calls(entrypoint: str, calls: Iterable[RuntimeCall]) -> None:
    discovered = {row.callable for row in calls}
    expected = EXPECTED_ANALYZE_CALLS if entrypoint == "analyze_claim" else EXPECTED_REPORT_CALLS
    missing = sorted(expected - discovered)
    unexpected = sorted(discovered - expected)
    if missing or unexpected:
        raise ValueError(
            f"{entrypoint} runtime inventory drift: missing={missing}, unexpected={unexpected}"
        )


def _validate_focused_report_dataflow(ctx: AuditContext) -> None:
    """Confirm focused findings actually reach the generic visible projection."""
    tree = ast.parse(ctx.patient_report_path.read_text(encoding="utf-8"), filename=str(ctx.patient_report_path))
    imports = _resolve_imports(ctx, ctx.patient_report_path, tree)
    qualified_imports = _resolve_qualified_imports(tree)
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "compute_patient_billing_report"
    )

    def imported_calls(name: str) -> list[ast.Call]:
        return [
            node
            for node in ast.walk(fn)
            if isinstance(node, ast.Call)
            and (target := _call_target(node.func, imports, qualified_imports)) is not None
            and target[0] == name
        ]

    projections = imported_calls("project_focused_legacy_rows")
    if len(projections) != 1 or len(projections[0].args) != 3:
        raise ValueError("focused report projection path drift")
    raw_arg = projections[0].args[2]
    materialized = [
        node
        for node in ast.walk(raw_arg)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "all_rows"
        and isinstance(node.func.value, ast.Call)
        and _call_target(node.func.value.func, imports, qualified_imports)
        == ("FocusedLegacyMaterializer", "src.bilun.domain.billing.focused_legacy_materializer")
    ]
    if len(materialized) != 1:
        raise ValueError("focused report no longer consumes materialized detector rows")
    focused_assignments = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "focused_batch"
        and node.value is projections[0]
    ]
    if len(focused_assignments) != 1:
        raise ValueError("focused report projection result is not bound")
    generic = imported_calls("project_claim_compliance")
    if len(generic) != 1:
        raise ValueError("focused report generic compliance projection drift")
    batches = [
        node
        for node in ast.walk(generic[0])
        if isinstance(node, ast.Call)
        and (target := _call_target(node.func, imports, qualified_imports)) is not None
        and target[0] == "RuleEvaluationBatch"
    ]
    if len(batches) != 1:
        raise ValueError("focused report evaluation-batch projection drift")
    def batch_attribute(field: str, owner: str, attribute: str) -> bool:
        value = next((kw.value for kw in batches[0].keywords if kw.arg == field), None)
        return value is not None and any(
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == owner
            and node.attr == attribute
            for node in ast.walk(value)
        )

    if not batch_attribute("findings", "focused_batch", "findings"):
        raise ValueError("focused report findings no longer reaches claim compliance")
    if not batch_attribute("findings", "evidence", "confirmed_broad_findings"):
        raise ValueError("broad report findings no longer reaches claim compliance")
    if not batch_attribute("evaluations", "compliance_batch", "evaluations"):
        raise ValueError("original-five evaluations no longer reach claim compliance")
    materialize = imported_calls("materialize_broad_rules")
    if len(materialize) != 1 or not any(
        isinstance(node, ast.Assign)
        and node.value is materialize[0]
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "broad_bundle"
        for node in ast.walk(fn)
    ):
        raise ValueError("broad report materializer path drift")
    evidence = imported_calls("project_full_wavea_evidence")
    if len(evidence) != 1 or [
        arg.id for arg in evidence[0].args if isinstance(arg, ast.Name)
    ] != ["pid", "claim_context", "focused_batch", "broad_bundle"]:
        raise ValueError("Wave A review evidence no longer consumes focused and broad batches")
    validated = imported_calls("validate_full_wavea_evidence_detail")
    if len(validated) != 1 or not any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "evidence"
        and node.attr == "detail"
        for node in ast.walk(validated[0])
    ):
        raise ValueError("Wave A evidence detail validation path drift")
    api = ctx.billing_api_path.read_text(encoding="utf-8")
    for token in (
        "def _gate_wavea_evidence(",
        "if not complete_build_evidence_available(reader, index, build_id):",
        "payload = original_five_report_payload(payload)",
        'payload["claim_reviews"]',
        'payload["financial_findings"]',
    ):
        if token not in api:
            raise ValueError("focused review/financial evidence draft API gate drift")
    if api.count("_gate_wavea_evidence(") != 4:
        raise ValueError("focused patient/bill report routes bypass the draft gate")
    cohort_api = ctx.compliance_api_path.read_text(encoding="utf-8")
    for token in (
        "if not complete_build_evidence_available(reader, wavea_index, active_build):",
        "read_cache_json_payload_rows(",
        "patient_id: original_five_report_payload(report)",
        "build_cohort_compliance_index(",
    ):
        if token not in cohort_api:
            raise ValueError("focused cohort compliance draft API gate drift")
    gate_api = ctx.wavea_gate_api_path.read_text(encoding="utf-8")
    for token in (
        "def complete_build_evidence_available(reader: Any, index: Any, build_id: str) -> bool:",
        'index.get("schema_version") == FULL_EVIDENCE_SCHEMA_VERSION',
        'index.get("capability") == "draft"',
        "validate_full_wavea_evidence_index(index)",
        "counts = declared_build_row_counts(reader, build_id)",
        'expected = counts.get("patient_billing_report_rows")',
        'counts.get("wavea_evidence_detail") == expected',
        'counts.get("wavea_evidence_index") == 1',
        'index["n_patients"] == expected',
    ):
        if token not in gate_api:
            raise ValueError("focused complete-build evidence gate drift")
    if _static_module_binding(ctx.wavea_evidence_path, "COMPLETE_EVIDENCE_CAPABILITY") != "complete-25-v1":
        raise ValueError("focused public activation marker drift")
    if '"capability": "draft"' not in ctx.wavea_evidence_path.read_text(encoding="utf-8"):
        raise ValueError("focused evidence builder no longer stamps draft capability")


def _module_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value.value
    return constants


def _resolve_static_value(node: ast.AST, bindings: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return bindings.get(node.id, _UNRESOLVED_STATIC_VALUE)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        values = [_resolve_static_value(child, bindings) for child in node.elts]
        if any(value is _UNRESOLVED_STATIC_VALUE for value in values):
            return _UNRESOLVED_STATIC_VALUE
        if isinstance(node, ast.Tuple):
            return tuple(values)
        if isinstance(node, ast.List):
            return list(values)
        return set(values)
    if isinstance(node, ast.Dict):
        keys = [_resolve_static_value(child, bindings) for child in node.keys]
        values = [_resolve_static_value(child, bindings) for child in node.values]
        if any(value is _UNRESOLVED_STATIC_VALUE for value in (*keys, *values)):
            return _UNRESOLVED_STATIC_VALUE
        return dict(zip(keys, values))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"frozenset", "set"}
        and len(node.args) == 1
        and not node.keywords
    ):
        value = _resolve_static_value(node.args[0], bindings)
        if value is _UNRESOLVED_STATIC_VALUE:
            return _UNRESOLVED_STATIC_VALUE
        return frozenset(value) if node.func.id == "frozenset" else set(value)
    return _UNRESOLVED_STATIC_VALUE


def _static_module_binding(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bindings: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = _resolve_static_value(node.value, bindings)
        if value is _UNRESOLVED_STATIC_VALUE:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                bindings[target.id] = value
    return bindings.get(name, _UNRESOLVED_STATIC_VALUE)


def _direct_imported_calls(ctx: AuditContext, path: Path, callable_name: str) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = _resolve_imports(ctx, path, tree)
    qualified_imports = _resolve_qualified_imports(tree)
    fn = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == callable_name
        ),
        None,
    )
    if fn is None:
        raise ValueError(f"runtime callable missing for static contract: {callable_name}")
    calls: dict[str, str] = {}
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        target = _call_target(node.func, imports, qualified_imports)
        if target is None or target[0] in NON_RUNTIME_IMPORTED_CALLS:
            continue
        calls[target[0]] = target[1]
    return calls


def _canonical_evaluator_emissions(ctx: AuditContext, module: str, callable_name: str) -> set[str]:
    if callable_name != "evaluate_rule_findings":
        return set()
    path = ctx.module_path(module)
    if path is None:
        raise ValueError(f"canonical evaluator module missing: {module}")
    rule_order = _static_module_binding(path, "_RULE_ORDER")
    if not isinstance(rule_order, tuple) or not rule_order or not all(
        isinstance(value, str) and value for value in rule_order
    ):
        raise ValueError(
            "canonical evaluator emission drift: _RULE_ORDER must be a non-empty string tuple"
        )
    if len(set(rule_order)) != len(rule_order):
        raise ValueError("canonical evaluator emission drift: _RULE_ORDER contains duplicates")

    metadata_maps: dict[str, dict[str, Any]] = {}
    for map_name in ("_REQUIRED_INPUTS", "_LINE_MAPPING", "_SOURCE_ENGINE"):
        value = _static_module_binding(path, map_name)
        if not isinstance(value, dict):
            raise ValueError(
                f"canonical evaluator metadata drift: required map {map_name} is missing"
            )
        if set(value) != set(rule_order):
            raise ValueError(
                f"canonical evaluator metadata drift: {map_name} keys do not match _RULE_ORDER"
            )
        metadata_maps[map_name] = value

    required_inputs = metadata_maps["_REQUIRED_INPUTS"]
    if any(
        not isinstance(inputs, (list, tuple))
        or not inputs
        or not all(isinstance(item, str) and item for item in inputs)
        for inputs in required_inputs.values()
    ):
        raise ValueError("canonical evaluator metadata drift: invalid _REQUIRED_INPUTS map")

    line_mapping = metadata_maps["_LINE_MAPPING"]
    if any(
        not isinstance(mapping, tuple)
        or len(mapping) != 2
        or mapping[0] not in {"procedure", "drug", "material", "claim"}
        or (mapping[1] is not None and (not isinstance(mapping[1], str) or not mapping[1]))
        for mapping in line_mapping.values()
    ):
        raise ValueError("canonical evaluator metadata drift: invalid _LINE_MAPPING map")

    source_engine = metadata_maps["_SOURCE_ENGINE"]
    if any(not isinstance(source, str) or not source for source in source_engine.values()):
        raise ValueError("canonical evaluator metadata drift: invalid _SOURCE_ENGINE map")
    if len(set(source_engine.values())) != len(source_engine):
        raise ValueError("canonical evaluator metadata drift: _SOURCE_ENGINE is ambiguous")

    direct_detectors = {
        name: source_module
        for name, source_module in _direct_imported_calls(ctx, path, callable_name).items()
        if name.startswith("detect_")
    }
    mapped_detectors = set(source_engine.values())
    if set(direct_detectors) != mapped_detectors:
        missing = sorted(mapped_detectors - set(direct_detectors))
        extra = sorted(set(direct_detectors) - mapped_detectors)
        raise ValueError(
            "canonical evaluator detector/source mapping drift: "
            f"missing={missing}, extra={extra}"
        )

    emitted_by_detector: dict[str, set[str]] = {}
    for detector_name, source_module in sorted(direct_detectors.items()):
        emitted = _static_emissions(ctx, source_module, detector_name)
        if not emitted:
            raise ValueError(
                "canonical evaluator detector emission drift: "
                f"{source_module}.{detector_name} has no statically resolved rule ID"
            )
        emitted_by_detector[detector_name] = emitted
        mapped_rule_ids = {
            rule_id for rule_id, source in source_engine.items() if source == detector_name
        }
        if emitted != mapped_rule_ids:
            raise ValueError(
                "canonical evaluator detector emission drift: "
                f"{detector_name} mapped={sorted(mapped_rule_ids)}, "
                f"emitted={sorted(emitted)}"
            )

    emitted_union = set().union(*emitted_by_detector.values())
    if emitted_union != set(rule_order):
        raise ValueError(
            "canonical evaluator emission drift: detector union does not match _RULE_ORDER; "
            f"missing={sorted(set(rule_order) - emitted_union)}, "
            f"extra={sorted(emitted_union - set(rule_order))}"
        )
    return emitted_union


def _static_emissions(ctx: AuditContext, module: str, callable_name: str) -> set[str]:
    path = ctx.module_path(module)
    if path is None:
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    constants = _module_constants(tree)
    fn = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == callable_name
        ),
        None,
    )
    if fn is None:
        return set()
    rule_ids: set[str] = set()
    kinds: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if not isinstance(key, ast.Constant) or key.value not in {"rule_id", "violation_kind"}:
                    continue
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    target = kinds if key.value == "violation_kind" else rule_ids
                    target.add(value.value)
                elif isinstance(value, ast.Name) and value.id in constants:
                    target = kinds if key.value == "violation_kind" else rule_ids
                    target.add(constants[value.id])
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg not in {"rule_id", "violation_kind"}:
                    continue
                value = keyword.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    target = kinds if keyword.arg == "violation_kind" else rule_ids
                    target.add(value.value)
                elif isinstance(value, ast.Name) and value.id in constants:
                    target = kinds if keyword.arg == "violation_kind" else rule_ids
                    target.add(constants[value.id])
    if rule_ids:
        return rule_ids
    return {f"kind:{value}" for value in kinds}


def discover_recommended_action_surfaces(ctx: AuditContext) -> set[str]:
    tree = ast.parse(
        ctx.billing_actions_path.read_text(encoding="utf-8"),
        filename=str(ctx.billing_actions_path),
    )
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    reachable: set[str] = set()
    pending = ["collect_billing_actions"]
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        fn = functions.get(name)
        if fn is None:
            raise ValueError(f"billing-actions helper missing: {name}")
        reachable.add(name)
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in functions
                and node.func.id not in reachable
            ):
                pending.append(node.func.id)

    surfaces: set[str] = set()
    for name in reachable:
        fn = functions[name]
        loop_values: dict[str, set[str]] = defaultdict(set)
        for node in ast.walk(fn):
            if not isinstance(node, ast.For):
                continue
            targets = (
                list(node.target.elts)
                if isinstance(node.target, (ast.Tuple, ast.List))
                else [node.target]
            )
            if not isinstance(node.iter, (ast.Tuple, ast.List)):
                continue
            for index, target in enumerate(targets):
                if not isinstance(target, ast.Name):
                    continue
                for item in node.iter.elts:
                    values = (
                        list(item.elts)
                        if isinstance(item, (ast.Tuple, ast.List))
                        else [item]
                    )
                    if index >= len(values):
                        continue
                    value = values[index]
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        loop_values[target.id].add(value.value)

        for node in ast.walk(fn):
            if (
                not isinstance(node, ast.Call)
                or not isinstance(node.func, ast.Name)
                or node.func.id != "_action_row"
            ):
                continue
            surface_kw = next((kw for kw in node.keywords if kw.arg == "surface"), None)
            if surface_kw is None:
                continue
            value = surface_kw.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                surfaces.add(value.value)
            elif isinstance(value, ast.Name):
                surfaces.update(loop_values.get(value.id, set()))
    return surfaces


def _load_registry(ctx: AuditContext) -> list[dict[str, Any]]:
    # Importing the module would pull package dependencies into the audit.  The
    # registry source is declarative, so parse constructor calls statically.
    tree = ast.parse(ctx.registry_path.read_text(encoding="utf-8"), filename=str(ctx.registry_path))
    rows: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "RuleRegistryEntry":
            continue
        values: dict[str, Any] = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            try:
                values[keyword.arg] = ast.literal_eval(keyword.value)
            except (ValueError, TypeError):
                continue
        if values.get("rule_id"):
            rows.append(values)
    rows.sort(key=lambda item: str(item["rule_id"]))
    return rows


def _direct_calls_in_callable(ctx: AuditContext, row: RuntimeCall) -> set[str]:
    path = ctx.module_path(row.module)
    if path is None:
        raise ValueError(f"runtime module missing for rerun evidence: {row.module}")
    return set(_direct_imported_calls(ctx, path, row.callable))
