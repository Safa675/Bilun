from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from scripts.audits.rule_surfacing.surface_sources import read_section_id_map


ROOT = Path(__file__).resolve().parents[3]
MAP_NAME = "RECOMMENDED_ACTION_SECTION_IDS"


def _load_audit():
    spec = importlib.util.spec_from_file_location(
        "rule_surfacing_section_map_fixture",
        ROOT / "scripts/audits/build_rule_surfacing_inventory.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "declaration",
    [
        "const NAME = { copay: 'billing-copay', drug_indication: 'drug-indication' };",
        'const NAME: Record<string, string> = {"copay": "billing-copay", "drug_indication": "drug-indication",};',
        "export const NAME : Readonly < Record < string , string > > = { copay : 'billing-copay', 'drug_indication' : 'drug-indication' };",
        "const /* contract */ NAME /* type */ : Record<string, /* values */ string> = {\n"
        "// entry\n'copay' /* key */: /* value */ 'billing-copay',\n drug_indication: 'drug-indication',\n};",
        "const NAME = { copay: 'billing-copay', drug_indication: 'drug-indication' } as const;",
        "const NAME = { copay: 'billing-copay', drug_indication: 'drug-indication' }",
    ],
    ids=["untyped", "quoted", "readonly", "comments", "as-const", "end-of-file"],
)
def test_supported_map_syntax_preserves_entry_values(declaration):
    assert read_section_id_map(declaration.replace("NAME", MAP_NAME)) == {
        "copay": "billing-copay",
        "drug_indication": "drug-indication",
    }


@pytest.mark.parametrize(
    "entry",
    [
        "...other",
        "['copay']: 'billing-copay'",
        "copay: unknownSection",
        "copay: resolveSection()",
        "copay: `billing-copay`",
        "copay: `billing-${kind}`",
        "copay: 'billing-' + suffix",
        "copay: { section: 'billing-copay' }",
        "copay: ['billing-copay']",
        "copay",
        "copay() { return 'billing-copay'; }",
        "copay: ''",
        "copay: 'billing-\\u0063opay'",
        "'co\\u0070ay': 'billing-copay'",
        "copay: 'billing-copay', 'copay': 'another-section'",
        "copay: 'billing-copay',, drug_indication: 'drug-indication'",
    ],
)
def test_nonliteral_or_ambiguous_entries_fail_instead_of_being_skipped(entry):
    with pytest.raises(ValueError, match=MAP_NAME):
        read_section_id_map(f"const {MAP_NAME} = {{ {entry} }};")


@pytest.mark.parametrize(
    "declaration",
    [
        "let NAME = { copay: 'billing-copay' };",
        "const NAME: SectionMap = { copay: 'billing-copay' };",
        "const NAME: Record<string, number> = { copay: 'billing-copay' };",
        "const NAME = fromElsewhere;",
        "const NAME = Object.freeze({ copay: 'billing-copay' });",
        "const NAME = { copay: 'billing-copay' } || other;",
        "const NAME = { copay: 'billing-copay' }; const NAME = { copay: 'other' };",
    ],
)
def test_unsupported_or_duplicate_declarations_fail(declaration):
    with pytest.raises(ValueError, match=MAP_NAME):
        read_section_id_map(declaration.replace("NAME", MAP_NAME))


@pytest.mark.parametrize(
    "source",
    [
        "// const NAME = { copay: 'billing-copay' };",
        "/* const NAME = { copay: 'billing-copay' }; */",
        'const decoy = "const NAME = { copay: \'billing-copay\' };";',
        "const decoy = `const NAME = { copay: 'billing-copay' };`;",
        "function unused() { const NAME = { copay: 'billing-copay' }; }",
        "const unused = () => { const NAME = { copay: 'billing-copay' }; };",
    ],
)
def test_comments_strings_and_nested_maps_are_not_top_level_evidence(source):
    with pytest.raises(ValueError, match=f"{MAP_NAME} not found"):
        read_section_id_map(source.replace("NAME", MAP_NAME))


@pytest.mark.parametrize(
    "source",
    [
        "const NAME = { copay: 'billing-copay' ;",
        "const NAME = { copay: 'billing-copay };",
        "const NAME = { /* unterminated",
    ],
)
def test_malformed_source_does_not_produce_partial_map(source):
    with pytest.raises(ValueError):
        read_section_id_map(source.replace("NAME", MAP_NAME))


def test_unrelated_nested_map_does_not_override_real_declaration():
    source = (
        f"function unused() {{ const {MAP_NAME} = {{ copay: 'wrong' }}; }}\n"
        f"const {MAP_NAME} = {{ copay: 'billing-copay' }};"
    )
    assert read_section_id_map(source) == {"copay": "billing-copay"}


@pytest.mark.parametrize(
    "source",
    [
        "const decoy = /const NAME = {copay: 'billing-copay'};/;",
        "const decoy = /; const NAME = {copay: 'billing-copay'};/;",
        "const NAME = {copay: 'billing-copay'}; const decoy = /const NAME = {copay: 'wrong'};/;",
        "const decoy = /;const NAME = {copay: 'wrong'};/; const NAME = {copay: 'billing-copay'};",
    ],
    ids=["regex-only", "semicolon-inside-regex", "real-before-regex", "real-after-regex"],
)
def test_top_level_regex_text_cannot_supply_or_duplicate_map_evidence(source):
    # Reject the unsupported enclosing expression, rather than treating its
    # contents as a declaration or reporting a false duplicate map.
    with pytest.raises(ValueError, match="unsupported top-level slash expression"):
        read_section_id_map(source.replace("NAME", MAP_NAME))


def test_real_map_reformatting_preserves_full_audit_and_missing_surface_still_fails(tmp_path, monkeypatch):
    audit = _load_audit()
    before = audit.build_audit()
    expected_map = audit.discover_deep_link_sections()
    original = audit.RECOMMENDED_ACTIONS_PATH
    source = original.read_text(encoding="utf-8")
    start = source.index(f"const {MAP_NAME}:")
    end = source.index("\n};", start) + len("\n};")
    formatted_map = (
        f"const {MAP_NAME} /* map contract */ : Readonly < Record < string, string > > = {{\n"
        + "\n".join(f"  '{key}' /* entry */: '{value}'," for key, value in expected_map.items())
        + "\n} as const;"
    )
    copied = tmp_path / "recommendedActions.ts"
    copied.write_text(source[:start] + formatted_map + source[end:], encoding="utf-8")
    original_rel = audit._rel
    monkeypatch.setattr(audit, "RECOMMENDED_ACTIONS_PATH", copied)
    monkeypatch.setattr(audit, "_rel", lambda path: original_rel(original if path == copied else path))

    assert audit.discover_deep_link_sections() == expected_map
    assert audit.build_audit() == before

    copied.write_text(
        copied.read_text().replace("  'drug_indication' /* entry */: 'drug-indication',\n", ""),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="recommended-actions surface drift"):
        audit.build_audit()
