"""Resolve the audit's patient surfaces through explicit TSX source contracts.

Supported components are named function declarations, with literal JSX IDs,
named imports and named re-exports. Views may export their named function as
default. Only JSX in a component's return expressions provides evidence; text,
unused imports and uncalled local functions do not. No runtime reachability or
arbitrary TypeScript evaluation is claimed.
"""

from dataclasses import dataclass
from pathlib import Path
from .model import AuditContext

from collections.abc import Mapping
from dataclasses import field

from .tsx_tokens import Token, expression_end, fail, group_end, tokenize


@dataclass
class _Module:
    functions: dict[str, list[Token]] = field(default_factory=dict)
    parameters: dict[str, list[Token]] = field(default_factory=dict)
    imports: dict[str, tuple[str, str]] = field(default_factory=dict)
    exports: dict[str, list[tuple[str, str | None]]] = field(default_factory=dict)
    wildcard_export: bool = False


def _bindings(tokens: list[Token]) -> list[tuple[str, str]]:
    """Read a named import/export list: source-name [as local-name]."""
    result = []
    for start in range(0, len(tokens)):
        if start and tokens[start - 1].value != ",":
            continue
        part = tokens[start:]
        stop = next((i for i, token in enumerate(part) if token.value == ","), len(part))
        part = part[:stop]
        if not part or part[0].value == "type":
            continue
        if len(part) == 1 and part[0].kind == "word":
            result.append((part[0].value, part[0].value))
        elif len(part) == 3 and part[1].value == "as" and all(
            part[i].kind == "word" for i in (0, 2)
        ):
            result.append((part[0].value, part[2].value))
        else:
            raise fail("unsupported named import/re-export")
    return result


def _read_module(path: Path) -> _Module:
    tokens = tokenize(path.read_text(encoding="utf-8"))
    module = _Module()
    index = 0
    while index < len(tokens):
        start = index
        exported = tokens[index].value == "export" and tokens[index].kind == "word"
        if exported:
            index += 1
        default = exported and tokens[index].value == "default"
        if default:
            index += 1
        token = tokens[index]
        if token.value == "function" and token.kind == "word":
            name = tokens[index + 1].value
            params = index + 2
            if tokens[params].value != "(":
                raise fail(f"unsupported function declaration in {path}")
            body = group_end(tokens, params)
            # Named return types are permitted; object return-type literals are
            # intentionally unsupported for audited component declarations.
            if tokens[body].value == ":":
                body += 1
                while body < len(tokens) and tokens[body].value != "{":
                    body += 1
            if body >= len(tokens) or tokens[body].value != "{":
                raise fail(f"unsupported function body in {path}")
            end = group_end(tokens, body)
            if name in module.functions:
                raise fail(f"ambiguous function {name} in {path}")
            module.functions[name] = tokens[body + 1 : end - 1]
            module.parameters[name] = tokens[params + 1 : group_end(tokens, params) - 1]
            if exported:
                module.exports.setdefault("default" if default else name, []).append((name, None))
            index = end
        elif (token.value == "import" and token.kind == "word") or (
            exported and token.value in {"{", "*"}
        ):
            end = next((i for i in range(index, len(tokens)) if tokens[i].value == ";"), len(tokens))
            statement = tokens[index:end]
            if exported and token.value == "*":
                module.wildcard_export = True
            elif not (token.value == "import" and len(statement) > 1 and statement[1].value == "type"):
                opening = next((i for i, item in enumerate(statement) if item.value == "{"), None)
                if opening is not None:
                    closing = group_end(statement, opening)
                    source = None
                    if closing < len(statement):
                        if statement[closing].value != "from" or statement[-1].kind != "string":
                            raise fail(f"unsupported module source in {path}")
                        source = statement[-1].value
                    for original, local in _bindings(statement[opening + 1 : closing - 1]):
                        if exported:
                            module.exports.setdefault(local, []).append((original, source))
                        elif source is not None:
                            if local in module.imports:
                                raise fail(f"ambiguous import {local} in {path}")
                            module.imports[local] = (original, source)
            index = end + 1
        else:
            # Skip whole unrelated declarations. Their contents cannot declare
            # imports or exported components for this bounded source reader.
            index = expression_end(tokens, start)
            if index == start:
                index += 1
            elif index < len(tokens) and tokens[index].value == ";":
                index += 1
    return module


def _return_expressions(body: list[Token]) -> list[list[Token]]:
    expressions = []
    index = 0
    while index < len(body):
        token = body[index]
        if token.kind == "word" and token.value in {"const", "let", "var"}:
            # Initializers (including object methods and uncalled callbacks)
            # are not component returns. Following arbitrary local bindings is
            # outside the supported contract.
            index = expression_end(body, index + 1)
        elif token.value == "=>" or (token.value in {"function", "class"} and token.kind == "word"):
            index += 1
            if token.value == "function":
                while index < len(body) and body[index].value != "(":
                    index += 1
                if index >= len(body):
                    raise fail("unsupported nested function")
                index = group_end(body, index)
            if token.value in {"function", "class"}:
                while index < len(body) and body[index].value != "{":
                    index += 1
            if index < len(body) and body[index].value == "{":
                index = group_end(body, index)
            else:
                index = expression_end(body, index)
        elif token.value == "return" and token.kind == "word":
            end = expression_end(body, index + 1)
            expressions.append(body[index + 1 : end])
            index = end
        else:
            index += 1
    return expressions


def _jsx_tags(expression: list[Token]) -> list[tuple[str, set[str]]]:
    """Read opening tags, excluding attribute expressions/callback props."""
    tags: list[tuple[str, set[str]]] = []
    index = 0
    while index < len(expression):
        token = expression[index]
        if token.value == "=>" or (token.kind == "word" and token.value == "function"):
            # A function value itself is not rendered. Inline map callbacks
            # are handled explicitly below when their call is encountered.
            return tags
        if token.value == "map" and token.kind == "word" and index > 0 and expression[index - 1].value == ".":
            if index + 1 < len(expression) and expression[index + 1].value == "(":
                end = group_end(expression, index + 1)
                callback = expression[index + 2 : end - 1]
                arrow = next((i for i, item in enumerate(callback) if item.value == "=>"), None)
                if arrow is not None:
                    result = callback[arrow + 1 :]
                    # A property or another call on the map result is no
                    # longer evidence that its JSX elements are rendered.
                    chained = end < len(expression) and expression[end].value in {".", "[", "("}
                    if chained:
                        result = []
                    if result and result[0].value == "{":
                        for returned in _return_expressions(result[1:-1]):
                            tags.extend(_jsx_tags(returned))
                    else:
                        tags.extend(_jsx_tags(result))
                index = end
                continue
        if token.kind == "symbol" and token.value in {"(", "{"}:
            end = group_end(expression, index)
            previous = expression[index - 1] if index else None
            is_call = token.value == "(" and previous is not None and (
                previous.kind == "word" or previous.value in {")", "]"}
            )
            if not is_call:
                tags.extend(_jsx_tags(expression[index + 1 : end - 1]))
            index = end
            continue
        if token.value == "<" and token.kind == "symbol" and index + 1 < len(expression) and expression[index + 1].kind == "word":
            name = expression[index + 1].value
            index += 2
            if index < len(expression) and expression[index].value in {".", ":"}:
                raise fail("unsupported member or namespace JSX component")
            ids: set[str] = set()
            has_id = False
            has_spread = False
            while index < len(expression) and expression[index].value != ">":
                if expression[index].value == "{" and expression[index].kind == "symbol":
                    has_spread = has_spread or expression[index + 1].value == "."
                    index = group_end(expression, index)
                    continue
                attr = expression[index].value
                index += 1
                while index + 1 < len(expression) and expression[index].value == "-":
                    attr += "-" + expression[index + 1].value
                    index += 2
                if index < len(expression) and expression[index].value == "=":
                    index += 1
                    if index >= len(expression):
                        raise fail("incomplete JSX attribute")
                    value = expression[index]
                    if attr == "id":
                        if has_id:
                            raise fail("ambiguous duplicate JSX id attribute")
                        has_id = True
                        if value.kind == "string":
                            ids.add(value.value)
                    if value.value == "{" and value.kind == "symbol":
                        index = group_end(expression, index)
                    else:
                        index += 1
            if index >= len(expression):
                raise fail("unterminated JSX opening tag")
            if expression[index - 1].value != "/" and not any(
                [item.value for item in expression[pos : pos + 4]] == ["<", "/", name, ">"]
                for pos in range(index + 1, len(expression) - 3)
            ):
                raise fail(f"unsupported or unclosed JSX element {name}")
            if ids and has_spread:
                raise fail("unsupported spread can replace the JSX id attribute")
            tags.append((name, ids))
        index += 1
    return tags


def _rendered_tags(body: list[Token]) -> list[tuple[str, set[str]]]:
    return [tag for expression in _return_expressions(body) for tag in _jsx_tags(expression)]


class SurfaceSourceResolver:
    """Read only named component chains rooted in the supplied known views."""

    def __init__(self, source_root: Path, views: Mapping[str, Path]):
        self.source_root = source_root.resolve()
        self.views = {name: path.resolve() for name, path in views.items()}
        self._modules: dict[Path, _Module] = {}

    def _module(self, path: Path) -> _Module:
        if not path.is_relative_to(self.source_root) or not path.is_file():
            raise fail(f"missing or out-of-root module {path}")
        if path not in self._modules:
            self._modules[path] = _read_module(path)
        return self._modules[path]

    def _import_path(self, owner: Path, source: str) -> Path:
        if source.startswith("@/"):
            base = self.source_root / source[2:]
        elif source.startswith("."):
            base = owner.parent / source
        else:
            raise fail(f"unsupported component import {source!r}")
        candidates = [base] if base.suffix else [base.with_suffix(".tsx"), base.with_suffix(".ts"), base / "index.tsx", base / "index.ts"]
        matches = [path.resolve() for path in candidates if path.is_file()]
        if len(matches) != 1:
            raise fail(f"unresolved or ambiguous component module {source!r} from {owner}")
        return matches[0]

    def _definition(self, path: Path, name: str, seen: frozenset[tuple[Path, str]] = frozenset()) -> tuple[list[Token], set[Path]]:
        key = (path, name)
        if key in seen or len(seen) >= 32:
            raise fail(f"cyclic or excessive component re-exports for {name}")
        module = self._module(path)
        targets = module.exports.get(name, [])
        if module.wildcard_export or len(targets) != 1:
            raise fail(f"unresolved, ambiguous or unsupported export {name} in {path}")
        original, source = targets[0]
        if source is None and original in module.functions:
            return module.functions[original], {path}
        if source is None:
            binding = module.imports.get(original)
            if binding is None:
                raise fail(f"unsupported component definition {original} in {path}")
            original, source = binding
        body, paths = self._definition(self._import_path(path, source), original, seen | {key})
        return body, paths | {path}

    def _view(self, name: str) -> tuple[Path, list[Token]]:
        path = self.views.get(name)
        if path is None:
            raise fail(f"unknown patient view {name}")
        module = self._module(path)
        exported = module.exports.get(name, []) + module.exports.get("default", [])
        if name not in module.functions or exported != [(name, None)]:
            raise fail(f"unsupported or ambiguous view declaration {name}")
        return path, module.functions[name]

    def view_evidence(self, view_name: str, *, section_id: str) -> list[Path]:
        path, body = self._view(view_name)
        if not any(section_id in ids for _, ids in _rendered_tags(body)):
            raise fail(f"section ID {section_id!r} not rendered by {view_name}")
        return [path]

    def component_evidence(self, view_name: str, component_name: str, *, section_id: str | None = None) -> list[Path]:
        path, view_body = self._view(view_name)
        module = self._module(path)
        used = {name for name, _ in _rendered_tags(view_body)}
        bindings = [(local, original, source) for local, (original, source) in module.imports.items() if original == component_name]
        for local, _, _ in bindings:
            if any(token.value == local for token in module.parameters[view_name]) or any(
                token.kind == "word" and token.value in {"const", "let", "var", "function", "class"}
                and index + 1 < len(view_body) and view_body[index + 1].value == local
                for index, token in enumerate(view_body)
            ):
                raise fail(f"ambiguous shadowed component import {local}")
        matches = [(original, source) for local, original, source in bindings if local in used and local[0].isupper()]
        if len(matches) != 1:
            raise fail(f"component {component_name} not uniquely rendered by {view_name}")
        original, source = matches[0]
        body, paths = self._definition(self._import_path(path, source), original)
        tags = _rendered_tags(body)
        if not tags:
            raise fail(f"component {component_name} has no supported returned JSX")
        if section_id is not None and not any(section_id in ids for _, ids in tags):
            raise fail(f"section ID {section_id!r} not rendered by {component_name}")
        return sorted(paths | {path})


_SECTION_MAP_NAME = "RECOMMENDED_ACTION_SECTION_IDS"


def _section_map_error(detail: str) -> ValueError:
    return ValueError(f"{_SECTION_MAP_NAME}: {detail}")


def _section_map_entries(tokens: list[Token]) -> dict[str, str]:
    entries: dict[str, str] = {}
    index = 0
    while index < len(tokens):
        key = tokens[index]
        if key.kind not in {"word", "string"} or not key.value:
            raise _section_map_error("entry key must be an identifier or literal string")
        if index + 2 >= len(tokens) or tokens[index + 1] != Token(":"):
            raise _section_map_error("entry must have a literal string value")
        value = tokens[index + 2]
        if value.kind != "string" or not value.value:
            raise _section_map_error("entry must have a non-empty, unescaped literal string value")
        if key.value in entries:
            raise _section_map_error(f"duplicate key {key.value!r}")
        entries[key.value] = value.value
        index += 3
        if index < len(tokens):
            if tokens[index] != Token(","):
                raise _section_map_error("unsupported expression after map entry")
            index += 1
    return entries


def read_section_id_map(source: str) -> dict[str, str]:
    """Read this one top-level const map without executing TypeScript.

    Entries are identifier/quoted keys and unescaped quoted string values.
    The declaration may be untyped, Record<string, string>, or
    Readonly<Record<string, string>>, with an optional `as const` assertion.
    Comments, ordinary whitespace and trailing commas are insignificant.
    Expressions, spreads, computed keys and ambiguous declarations fail.
    Top-level slash expressions are unsupported: the shared lexer does not
    distinguish regex literals from division, so their text cannot prove a map.
    """
    tokens = tokenize(source)
    declarations: list[int] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == Token("/"):
            raise _section_map_error("unsupported top-level slash expression")
        if (
            token.kind == "word" and token.value in {"const", "let", "var"}
            and index + 1 < len(tokens) and tokens[index + 1] == Token(_SECTION_MAP_NAME, "word")
        ):
            declarations.append(index)
        if token.kind == "symbol" and token.value in {"(", "[", "{"}:
            index = group_end(tokens, index)
        else:
            index += 1

    if not declarations:
        raise ValueError(f"{_SECTION_MAP_NAME} not found")
    if len(declarations) != 1:
        raise _section_map_error("ambiguous declarations")
    index = declarations[0]
    if tokens[index] != Token("const", "word"):
        raise _section_map_error("declaration must be const")
    index += 2
    if index < len(tokens) and tokens[index] == Token(":"):
        index += 1
        supported_types = (
            tokenize("Readonly<Record<string, string>>"),
            tokenize("Record<string, string>"),
        )
        annotation = next((kind for kind in supported_types if tokens[index:index + len(kind)] == kind), None)
        if annotation is None:
            raise _section_map_error("unsupported type annotation")
        index += len(annotation)
    if tokens[index:index + 2] != [Token("="), Token("{")]:
        raise _section_map_error("initializer must be a literal object")
    end = group_end(tokens, index + 1)
    entries = _section_map_entries(tokens[index + 2:end - 1])
    index = end
    if tokens[index:index + 2] == [Token("as", "word"), Token("const", "word")]:
        index += 2
    if index < len(tokens) and tokens[index] != Token(";"):
        raise _section_map_error("unsupported expression after literal object")
    return entries


def discover_deep_link_sections(ctx: AuditContext) -> dict[str, str]:
    return read_section_id_map(ctx.recommended_actions_path.read_text(encoding="utf-8"))

def _require_source_token(ctx: AuditContext, path: Path, token: str, *, label: str) -> None:
    if token not in path.read_text(encoding="utf-8"):
        raise ValueError(f"{label} source drift: {token!r} missing from {ctx.relative_path(path)}")


def _patient_ui_evidence_paths(ctx: AuditContext, patient_ui: str) -> list[Path]:
    views = {
        "ComplianceViewSection": ctx.compliance_view_path,
        "RevenueViewSection": ctx.revenue_view_path,
        "AuditViewSection": ctx.audit_view_path,
    }
    resolver = SurfaceSourceResolver(ctx.frontend_source_root, views)
    if patient_ui == "RecommendedActionsPanel":
        return sorted({
            path
            for view in ("RevenueViewSection", "AuditViewSection")
            for path in resolver.component_evidence(view, patient_ui)
        })
    if "#" in patient_ui:
        component, section_id = patient_ui.split("#", 1)
        return resolver.view_evidence(component, section_id=section_id)
    if ":" in patient_ui:
        component, child = patient_ui.split(":", 1)
        section_ids = {
            "CopayOptimizationSection": "billing-copay",
            "BillingStrategySection": "billing-strategy",
            "SessionUpliftSection": "billing-session-uplift",
            "DrgUpliftSection": "billing-drg-uplift",
            "BloodComponentUpliftSection": "billing-blood-uplift",
            "MaterialUpliftSection": "billing-material-uplift",
            "CareSettingReviewSection": "billing-care-setting-review",
            "DrgPackageAdequacyReviewSection": "billing-drg-package-adequacy",
            "ProcedureAddonUpliftSection": "billing-procedure-addon-uplift",
            "MedulaRejectionPlaybookSection": "medula-playbook",
            "ClaimSubmissionChecklistSection": "claim-submission-checklist",
            "DrugIndicationReviewSection": "drug-indication",
            "MaterialsPreCheckSection": "materials-pre-check",
        }
        if child not in section_ids:
            raise ValueError(f"patient UI source: unknown component contract {child}")
        return resolver.component_evidence(component, child, section_id=section_ids[child])

    section_ids = [value for value in patient_ui.split(",") if value]
    if not section_ids:
        raise ValueError("empty patient UI metadata")
    section_components = {
        "billing-lab": ("ComplianceViewSection", "LabOptimizationSection"),
        "billing-procedure-capture-gap": ("RevenueViewSection", "ProcedureCaptureGapSection"),
    }
    paths: set[Path] = set()
    for section_id in section_ids:
        if section_id not in section_components:
            raise ValueError(f"patient UI source: unknown section contract {section_id}")
        view, child = section_components[section_id]
        paths.update(resolver.component_evidence(view, child, section_id=section_id))
    return sorted(paths)


def _cohort_api_evidence_path(ctx: AuditContext, cohort_api: str) -> Path:
    route = cohort_api.split("?", 1)[0]
    path = {
        "/compliance-index": ctx.compliance_api_path,
        "/patient-alerts": ctx.alerts_api_path,
    }.get(route)
    if path is None:
        raise ValueError(f"unknown cohort API metadata route: {cohort_api}")
    _require_source_token(ctx, path, f'@router.get("{route}"', label="cohort API")
    return path


def _cohort_ui_evidence_path(ctx: AuditContext, cohort_ui: str) -> Path:
    prefix = "SUTComplianceDashboard:"
    if not cohort_ui.startswith(prefix):
        raise ValueError(f"unknown cohort UI metadata: {cohort_ui}")
    surface = cohort_ui[len(prefix) :]
    _require_source_token(ctx, ctx.cohort_dashboard_path, f'"{surface}"', label="cohort UI")
    return ctx.cohort_dashboard_path
