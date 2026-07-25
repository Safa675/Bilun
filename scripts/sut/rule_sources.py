"""YAML rule sources and JSON Schema validation for the rule compiler."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, RefResolver
from jsonschema.validators import validator_for

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_RULES_DIR = _PROJECT_ROOT / "data/gazette/prose_rules"
_SCHEMA_DIR = _RULES_DIR / "schemas"
_SOURCES_DIR = _PROJECT_ROOT / "data/gazette/prose_rule_sources"

RULE_FAMILY_YAML_DIRS: dict[str, str] = {
    "anti_vegf_prose": "anti_vegf",
    "copay_general_1_8": "copay_general_1_8",
    "definitions_2_6": "definitions_2_6",
    "dental_2_4_1": "dental_2_4_1",
    "drg_package_adequacy_prose": "drg_package_adequacy",
    "drug_combination_4_2": "drug_combination_4_2",
    "drug_indication_prose": "drug_indication",
    "gap_closing_misc": "gap_closing_misc",
    "gap_closing_treatment_2": "gap_closing_treatment_2",
    "gazette_repricing_prose": "gazette_repricing",
    "material_bundling_prose": "material_bundling",
    "material_pairing_uplift": "material_pairing_uplift",
    "payment_method_2_2": "payment_method_2_2",
    "procedure_pairing_prose": "procedure_pairing",
    "session_pricing_2_2_2_B": "session_pricing_2_2_2_B",
    "specialty_materials_prose": "specialty_materials",
    "treatment_pricing_2_4": "treatment_pricing_2_4",
}

# First 20 SUT sections migrated from Python batches → YAML (wave 1).
DRUG_INDICATION_YAML_WAVE1_SECTIONS: frozenset[str] = frozenset({
    "4.1",
    "4.1.1",
    "4.1.2",
    "4.1.3",
    "4.1.4",
    "4.1.5",
    "4.1.6",
    "4.1.7",
    "4.1.8",
    "4.1.9",
    "4.2.1.A",
    "4.2.1.B",
    "4.2.1.C",
    "4.2.1.C-1",
    "4.2.1.C-10",
    "4.2.1.C-11",
    "4.2.1.C-12",
    "4.2.1.C-13",
    "4.2.1.C-14",
    "4.2.1.C-2",
})

# Sections 21–40 (alphabetical) migrated in YAML wave 2.
DRUG_INDICATION_YAML_WAVE2_SECTIONS: frozenset[str] = frozenset({
    "4.2.1.C-3",
    "4.2.1.C-4",
    "4.2.1.C-5",
    "4.2.1.C-6",
    "4.2.1.C-7",
    "4.2.1.C-8",
    "4.2.1.C-9",
    "4.2.10.A",
    "4.2.10.A-3",
    "4.2.10.A-4",
    "4.2.10.B-2",
    "4.2.10.B-3",
    "4.2.10.C-1",
    "4.2.10.C-2",
    "4.2.10.C-3",
    "4.2.10.D-2",
    "4.2.10.Ç-2",
    "4.2.12.A",
    "4.2.12.B-1",
    "4.2.12.B-2",
})

# Sections 41–80 (alphabetical) migrated in YAML wave 3.
DRUG_INDICATION_YAML_WAVE3_SECTIONS: frozenset[str] = frozenset({
    "4.2.13",
    "4.2.13.1",
    "4.2.13.1.2",
    "4.2.13.1.3",
    "4.2.13.2",
    "4.2.13.3.1",
    "4.2.13.3.2",
    "4.2.13.3.2.A",
    "4.2.13.3.2.B",
    "4.2.13.E-1",
    "4.2.13.E-2",
    "4.2.14",
    "4.2.14.B",
    "4.2.14.C",
    "4.2.15.A",
    "4.2.15.B",
    "4.2.15.C",
    "4.2.15.D",
    "4.2.15.D-1",
    "4.2.15.D-2",
    "4.2.15.F",
    "4.2.16",
    "4.2.17.A",
    "4.2.17.B",
    "4.2.17.D",
    "4.2.18",
    "4.2.19",
    "4.2.2",
    "4.2.20",
    "4.2.22",
    "4.2.23",
    "4.2.24.A",
    "4.2.24.B",
    "4.2.24.C",
    "4.2.24.Ç",
    "4.2.25",
    "4.2.27.A",
    "4.2.27.B",
    "4.2.27.C",
    "4.2.27.D",
})

# Sections 81–166 (alphabetical) — final YAML wave 4 (completes drug_indication migration).
DRUG_INDICATION_YAML_WAVE4_SECTIONS: frozenset[str] = frozenset({
    "4.2.27.Ç",
    "4.2.28.A-1",
    "4.2.28.A-2",
    "4.2.28.C",
    "4.2.28.E",
    "4.2.28.Ç",
    "4.2.29",
    "4.2.3",
    "4.2.30.A",
    "4.2.32",
    "4.2.33",
    "4.2.33.D",
    "4.2.34",
    "4.2.35.A",
    "4.2.35.B",
    "4.2.36",
    "4.2.37.A",
    "4.2.38",
    "4.2.39",
    "4.2.42.A",
    "4.2.42.B",
    "4.2.43",
    "4.2.46.A",
    "4.2.46.B",
    "4.2.46.C",
    "4.2.48",
    "4.2.49",
    "4.2.49.A",
    "4.2.49.B",
    "4.2.49.C",
    "4.2.5",
    "4.2.50",
    "4.2.51",
    "4.2.52",
    "4.2.53",
    "4.2.54",
    "4.2.55",
    "4.2.56",
    "4.2.57",
    "4.2.58",
    "4.2.59",
    "4.2.6.A",
    "4.2.6.A-1",
    "4.2.6.A-2",
    "4.2.6.A-3",
    "4.2.6.A-4",
    "4.2.6.A-5",
    "4.2.6.B",
    "4.2.6.B-2",
    "4.2.60",
    "4.2.61",
    "4.2.62",
    "4.2.63",
    "4.2.64",
    "4.2.65",
    "4.2.66",
    "4.2.67",
    "4.2.68",
    "4.2.69",
    "4.2.7",
    "4.2.70.A",
    "4.2.70.B",
    "4.2.71",
    "4.2.72",
    "4.2.73",
    "4.2.74",
    "4.2.75",
    "4.2.8.A",
    "4.2.8.B",
    "4.2.9.A",
    "4.2.9.A-1",
    "4.2.9.A-2",
    "4.2.9.B",
    "4.2.9.C",
    "4.2.9.C-2",
    "4.2.9.E",
    "4.2.9.F",
    "4.2.9.Ç",
    "4.3",
    "4.4.1",
    "4.4.2",
    "4.5.1",
    "4.5.2",
    "4.5.3",
    "4.6",
    "4.7",
})

DRUG_INDICATION_YAML_MIGRATED_SECTIONS: frozenset[str] = (
    DRUG_INDICATION_YAML_WAVE1_SECTIONS
    | DRUG_INDICATION_YAML_WAVE2_SECTIONS
    | DRUG_INDICATION_YAML_WAVE3_SECTIONS
    | DRUG_INDICATION_YAML_WAVE4_SECTIONS
)

_RULE_SETS_REQUIRING_SOURCES = frozenset({"definitions_2_6", "drug_indication_prose"})

_RULE_SET_SCHEMAS: dict[str, Path] = {
    "definitions_2_6": _SCHEMA_DIR / "definitions_2_6.schema.json",
    "drug_indication_prose": _RULES_DIR / "drug_indication_prose.schema.json",
    "material_bundling_prose": _RULES_DIR / "material_bundling_prose.schema.json",
    "specialty_materials_prose": _RULES_DIR / "specialty_materials_prose.schema.json",
}

_REF_RESOLVER: RefResolver | None = None


def _ref_resolver() -> RefResolver:
    global _REF_RESOLVER
    if _REF_RESOLVER is None:
        _REF_RESOLVER = RefResolver(
            base_uri=_SCHEMA_DIR.as_uri() + "/",
            referrer={},
            store=_load_schema_store(),
        )
    return _REF_RESOLVER


def _load_schema_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for path in sorted(_SCHEMA_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        schema_id = str(payload.get("$id") or path.name)
        store[schema_id] = payload
        store[path.name] = payload
        store[path.as_uri()] = payload
    for path in sorted(_RULES_DIR.glob("*.schema.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        schema_id = str(payload.get("$id") or path.name)
        store[schema_id] = payload
        store[path.name] = payload
        store[path.as_uri()] = payload
    return store


def schema_path_for_rule_set(rule_set_id: str) -> Path | None:
    return _RULE_SET_SCHEMAS.get(rule_set_id)


def _validator_for_schema(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    cls = validator_for(schema)
    cls.check_schema(schema)
    return cls(schema, resolver=_ref_resolver())


def validate_rule_set_payload(payload: dict[str, Any], rule_set_id: str) -> None:
    """Raise ValueError with human-readable paths when a rule set fails schema validation."""
    schema_path = schema_path_for_rule_set(rule_set_id)
    if schema_path is None or not schema_path.is_file():
        _validate_compile_invariants(payload, rule_set_id, require_gate_b_sources=False)
        return

    validator = _validator_for_schema(schema_path)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    if errors:
        lines = [f"{rule_set_id}: schema validation failed ({schema_path.name})"]
        for err in errors[:20]:
            path = ".".join(str(part) for part in err.path) or "<root>"
            lines.append(f"  - {path}: {err.message}")
        if len(errors) > 20:
            lines.append(f"  ... {len(errors) - 20} more")
        raise ValueError("\n".join(lines))

    _validate_compile_invariants(
        payload,
        rule_set_id,
        require_gate_b_sources=rule_set_id in _RULE_SETS_REQUIRING_SOURCES,
    )


def _validate_compile_invariants(
    payload: dict[str, Any],
    rule_set_id: str,
    *,
    require_gate_b_sources: bool,
) -> None:
    """Extra compile-time checks beyond JSON Schema."""
    rules = payload.get("rules") or []
    if not isinstance(rules, list):
        raise ValueError(f"{rule_set_id}: rules must be a list")

    for index, rule in enumerate(rules):
        prefix = f"{rule_set_id}.rules[{index}]"
        if not isinstance(rule, dict):
            raise ValueError(f"{prefix}: rule must be an object")
        rule_id = rule.get("rule_id")
        if not rule_id:
            raise ValueError(f"{prefix}: missing rule_id")

        sources = rule.get("gate_b_sources")
        if require_gate_b_sources and not sources:
            raise ValueError(f"{prefix} ({rule_id}): gate_b_sources is required and must be non-empty")
        if sources is not None and not isinstance(sources, list):
            raise ValueError(f"{prefix} ({rule_id}): gate_b_sources must be a list")
        if isinstance(sources, list):
            from scripts.sut.prose.clause_identity import is_gate_b_source_ref

            for src in sources:
                if src is None or not str(src).strip():
                    raise ValueError(f"{prefix} ({rule_id}): gate_b_sources entries must be non-empty strings")
                if not is_gate_b_source_ref(str(src)):
                    raise ValueError(
                        f"{prefix} ({rule_id}): invalid gate_b_sources cite {src!r} "
                        "(expected C/F###### or clause_coordinate)"
                    )

        icd_codes = rule.get("icd10_codes") or []
        icd_ranges = rule.get("icd10_ranges") or []
        if icd_codes and icd_ranges:
            raise ValueError(
                f"{prefix} ({rule_id}): use icd10_codes OR icd10_ranges, not both"
            )


def _section_yaml_name(section_id: str) -> str:
    return section_id.replace("/", "_") + ".yaml"


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: object) -> bool:
        return True


def _dump_yaml(payload: dict[str, Any]) -> str:
    return yaml.dump(
        payload,
        Dumper=_NoAliasDumper,
        sort_keys=False,
        allow_unicode=True,
        width=120,
        default_flow_style=False,
    )


def section_yaml_path(section_id: str, *, family: str = "drug_indication") -> Path:
    return _SOURCES_DIR / family / _section_yaml_name(section_id)


def drug_indication_yaml_wave1_paths() -> list[Path]:
    return [section_yaml_path(section) for section in sorted(DRUG_INDICATION_YAML_WAVE1_SECTIONS)]


def drug_indication_yaml_wave2_paths() -> list[Path]:
    return [section_yaml_path(section) for section in sorted(DRUG_INDICATION_YAML_WAVE2_SECTIONS)]


def drug_indication_yaml_wave3_paths() -> list[Path]:
    return [section_yaml_path(section) for section in sorted(DRUG_INDICATION_YAML_WAVE3_SECTIONS)]


def drug_indication_yaml_wave4_paths() -> list[Path]:
    return [section_yaml_path(section) for section in sorted(DRUG_INDICATION_YAML_WAVE4_SECTIONS)]


def drug_indication_yaml_all_paths() -> list[Path]:
    return [section_yaml_path(section) for section in sorted(DRUG_INDICATION_YAML_MIGRATED_SECTIONS)]


def load_drug_section_rules(section_id: str) -> list[dict[str, Any]]:
    return load_yaml_rules(section_yaml_path(section_id))


def load_drug_sections_rules(section_ids: list[str]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for section_id in section_ids:
        rules.extend(load_drug_section_rules(section_id))
    return rules


# Short-key aliases for wave-3 tests → qualified keys in legacy_batch_rule_ids.json.
_LEGACY_BATCH_SHORT_ALIASES: dict[str, str] = {
    "BATCH_A2_RULES": "drug_indication_4213_4216_batch_rules.py:BATCH_A2_RULES",
    "BATCH_A2A_RULES": "drug_indication_4213_a2a_batch_rules.py:BATCH_A2A_RULES",
    "BATCH_4213_TIER_B_RULES": "drug_indication_4213_tier_b_batch_rules.py:BATCH_4213_TIER_B_RULES",
    "BATCH_A2B_4216_RULES": "drug_indication_4216_a2b_batch_rules.py:BATCH_A2B_4216_RULES",
    "BATCH_4216_TIER_B_RULES": "drug_indication_4216_tier_b_batch_rules.py:BATCH_4216_TIER_B_RULES",
    "BATCH_A15_RULES": "drug_indication_4215_pilot_batch_rules.py:BATCH_A15_RULES",
    "BATCH_A3_RULES": "drug_indication_4217_batch_rules.py:BATCH_A3_RULES",
    "BATCH_A4_RULES": "drug_indication_4219_batch_rules.py:BATCH_A4_RULES",
    "BATCH_A24_RULES": "drug_indication_4224_pilot_batch_rules.py:BATCH_A24_RULES",
}

_LEGACY_BATCH_JSON = _SOURCES_DIR / "drug_indication" / "legacy_batch_rule_ids.json"


@lru_cache(maxsize=1)
def _legacy_batch_rule_ids() -> dict[str, tuple[str, ...]]:
    if not _LEGACY_BATCH_JSON.is_file():
        raise FileNotFoundError(_LEGACY_BATCH_JSON)
    raw = json.loads(_LEGACY_BATCH_JSON.read_text(encoding="utf-8"))
    out: dict[str, tuple[str, ...]] = {
        key: tuple(rule_ids) for key, rule_ids in raw.items()
    }
    for short, qualified in _LEGACY_BATCH_SHORT_ALIASES.items():
        if qualified in out:
            out[short] = out[qualified]
    return out


def load_drug_rules_by_ids(rule_ids: tuple[str, ...] | list[str]) -> list[dict[str, Any]]:
    """Load drug-indication rules from section YAML by rule_id (preserves order)."""
    wanted = frozenset(rule_ids)
    by_id: dict[str, dict[str, Any]] = {}
    for section in DRUG_INDICATION_YAML_MIGRATED_SECTIONS:
        for rule in load_drug_section_rules(section):
            rule_id = str(rule.get("rule_id") or "")
            if rule_id in wanted:
                by_id[rule_id] = rule
    missing = wanted - by_id.keys()
    if missing:
        raise KeyError(f"rule_ids not found in YAML sources: {sorted(missing)}")
    return [by_id[rule_id] for rule_id in rule_ids]


def load_legacy_drug_batch(batch_name: str) -> list[dict[str, Any]]:
    """Load a retired Python batch rule list from YAML section sources.

    ``batch_name`` is either a qualified key ``module.py:ATTR`` from
    ``legacy_batch_rule_ids.json`` or a short alias (e.g. ``BATCH_A15_RULES``).
    """
    rule_ids_map = _legacy_batch_rule_ids()
    try:
        rule_ids = rule_ids_map[batch_name]
    except KeyError as exc:
        raise KeyError(f"unknown legacy drug batch: {batch_name}") from exc
    return load_drug_rules_by_ids(rule_ids)


def load_yaml_rules(path: Path) -> list[dict[str, Any]]:
    """Load rules from a section YAML file."""
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: YAML root must be a mapping")
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise ValueError(f"{path}: missing rules list")
    out: list[dict[str, Any]] = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"{path}: rules[{index}] must be a mapping")
        out.append(dict(rule))
    return out


def load_yaml_sources(paths: list[Path]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda p: p.as_posix()):
        rules.extend(load_yaml_rules(path))
    return rules


def rule_family_yaml_dir(rule_set_id: str) -> Path:
    try:
        dirname = RULE_FAMILY_YAML_DIRS[rule_set_id]
    except KeyError as exc:
        raise KeyError(f"unknown rule family YAML directory: {rule_set_id}") from exc
    return _SOURCES_DIR / dirname


def rule_family_yaml_paths(rule_set_id: str) -> list[Path]:
    return sorted(rule_family_yaml_dir(rule_set_id).glob("*.yaml"))


def load_rule_family_yaml_rules(rule_set_id: str) -> list[dict[str, Any]]:
    return load_yaml_sources(rule_family_yaml_paths(rule_set_id))


def export_rules_to_section_yaml(
    rules: list[dict[str, Any]],
    *,
    out_dir: Path,
    source_note: str | None = None,
) -> list[Path]:
    """Group rules by sut_section and write one YAML file per section."""
    by_section: dict[str, list[dict[str, Any]]] = {}
    for rule in rules:
        section = str(rule.get("sut_section") or "").strip()
        if not section:
            raise ValueError(f"rule {rule.get('rule_id')!r} missing sut_section")
        by_section.setdefault(section, []).append(dict(rule))

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for section in sorted(by_section):
        path = out_dir / _section_yaml_name(section)
        payload: dict[str, Any] = {
            "section_id": section,
            "rules": by_section[section],
        }
        if source_note:
            payload["source_note"] = source_note
        path.write_text(_dump_yaml(payload), encoding="utf-8")
        written.append(path)
    return written


def sources_dir() -> Path:
    return _SOURCES_DIR
