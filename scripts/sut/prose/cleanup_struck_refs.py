#!/usr/bin/env python3
"""Systemic cleanup: re-link or remove struck (non-in-force) clause_ids across
prose rule YAML sources, runtime JSONs, and manifests.

A struck clause_id means the SUT amendment repealed that text. Rules referencing
struck clauses encode legacy/repealed law. This script finds, for each struck ref,
the best in-force replacement (same section, same provision) or removes the ref
if no replacement exists (fully repealed).

Run: python scripts/sut/prose/cleanup_struck_refs.py [--apply]
Without --apply it only reports (dry run).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import polars as pl

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_BATCH_DIR = _REPO / "scripts/sut/prose"
_RULES_DIR = _REPO / "data/gazette/prose_rules"
_MANIFEST_DIR = _REPO / "data/gazette/prose_manifests"

# Minimum similarity ratio to accept a replacement (conservative — false
# positive is worse than removal, since removal is auditable).
_MIN_SIMILARITY = 0.55


def _load_clauses() -> pl.DataFrame:
    return pl.read_parquet(_CLAUSES)


def _fikra_number(text: str) -> str | None:
    """Extract the leading fikra marker like '(7)', 'a)', '1)' from clause text."""
    m = re.match(r"^\s*(\([0-9]+\)|[a-zçğıöşü]\)|[0-9]+[-)])", text or "")
    return m.group(1) if m else None


def _key_phrases(text: str) -> set[str]:
    """Extract distinctive Turkish phrases (drug names, conditions) for matching."""
    text = text or ""
    # lowercase Turkish-aware
    text = text.casefold()
    # grab 4+ char word sequences, skip common stop-words
    stops = {"ve","ile","bir","bu","olan","için","göre","kadar","gibi","adar","halinde"}
    words = [w for w in re.findall(r"[a-zçğıöşü]{4,}", text) if w not in stops]
    return set(words[:15])


def build_replacement_map(df: pl.DataFrame, struck_ids: set[str]) -> dict[str, str]:
    """For each struck clause_id, find the best in-force replacement by section + content."""
    in_force = df.filter(pl.col("is_in_force"))
    by_section: dict[str, list[dict]] = {}
    for r in in_force.iter_rows(named=True):
        sec = r.get("section_id") or ""
        by_section.setdefault(sec, []).append(r)

    mapping: dict[str, str] = {}
    for sid in sorted(struck_ids):
        row = df.filter(pl.col("clause_id") == sid)
        if not len(row):
            continue
        r = row.row(0, named=True)
        sec = r.get("section_id") or ""
        struck_text = (r.get("text_tr") or "")[:300]
        struck_fikra = _fikra_number(struck_text)
        struck_keys = _key_phrases(struck_text)

        cands = by_section.get(sec, [])
        # also try prefix match if exact section empty
        if not cands and sec:
            prefix = ".".join(sec.split(".")[:3])
            cands = [c for s, cs in by_section.items() if (s or "").startswith(prefix) for c in cs]

        best_id, best_score = None, 0.0
        for c in cands:
            ct = (c.get("in_force_text") or "")[:300]
            # base similarity
            score = SequenceMatcher(None, struck_text, ct).ratio()
            # bonus for same fikra number
            if struck_fikra and _fikra_number(ct) == struck_fikra:
                score += 0.15
            # bonus for key-phrase overlap
            c_keys = _key_phrases(ct)
            if struck_keys and c_keys:
                overlap = len(struck_keys & c_keys) / max(len(struck_keys), 1)
                score += 0.1 * overlap
            if score > best_score:
                best_id, best_score = c["clause_id"], score

        if best_id and best_score >= _MIN_SIMILARITY:
            mapping[sid] = best_id
    return mapping


def _find_rules_list_attr(tree: ast.Module) -> list[tuple[str, str]]:
    """Return [(assign_name, list_var_name)] for module-level list assigns of rule dicts."""
    out = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name) and isinstance(node.value, ast.List):
                if node.value.elts and isinstance(node.value.elts[0], ast.Dict):
                    out.append((tgt.id, tgt.id))
    return out


def clean_batch_file(path: Path, mapping: dict[str, str], struck_ids: set[str], apply: bool) -> tuple[int, int]:
    """Clean one batch_rules .py file by string-replacing struck ids. Returns (relinked, removed)."""
    src = path.read_text(encoding="utf-8")
    # First: relink struck ids that have replacements (global string replace)
    relinked = 0
    for struck_id, repl in mapping.items():
        literal = f'"{struck_id}"'
        if literal in src:
            src = src.replace(literal, f'"{repl}"')
            relinked += 1
    # Then: remove struck ids with no replacement using regex (handles all list positions).
    removed = 0
    for struck_id in struck_ids:
        literal = f'"{struck_id}"'
        if literal not in src:
            continue
        # Match the literal optionally followed by comma+space, OR preceded by comma+space.
        # Handles: [..., "CXXX", ...] / [..., "CXXX"] / ["CXXX", ...] / ["CXXX"]
        before = src
        # case: "CXXX", (with optional surrounding whitespace) -> remove the element + comma
        src = re.sub(r',\s*' + re.escape(literal) + r'(?=\s*[\]\)])', '', src)
        # case: "CXXX", at start/middle -> remove element + trailing comma
        src = re.sub(re.escape(literal) + r',\s*', '', src)
        # case: lone "CXXX" (last or only element) -> leave as-is (empty list handled below)
        if literal in src:
            src = re.sub(re.escape(literal), '', src)
        if src != before:
            removed += 1
    # clean up empty/double-comma artifacts
    src = re.sub(r',\s*,', ',', src)
    src = re.sub(r'\[\s*,', '[', src)
    src = re.sub(r',\s*\]', ']', src)
    if (relinked or removed) and apply:
        path.write_text(src, encoding="utf-8")
    return (relinked, removed)


def clean_json(path: Path, mapping: dict[str, str], struck_ids: set[str], apply: bool) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = data.get("rules") or []
    relinked = removed = 0
    for r in rules:
        src = r.get("gate_b_sources") or []
        new = []
        for cid in src:
            if cid in struck_ids:
                if cid in mapping:
                    new.append(mapping[cid]); relinked += 1
                else:
                    removed += 1
            else:
                new.append(cid)
        r["gate_b_sources"] = new
    if (relinked or removed) and apply:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return (relinked, removed)


def clean_manifest(path: Path, mapping: dict[str, str], struck_ids: set[str], apply: bool) -> int:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if isinstance(data, list):
        # array manifest — clean each element if list of clause_ids
        new = []
        changed = False
        for cid in data:
            if isinstance(cid, str) and cid in struck_ids:
                changed = True
                if cid in mapping:
                    new.append(mapping[cid])
            else:
                new.append(cid)
        if changed and apply:
            path.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1 if changed else 0
    if not isinstance(data, dict):
        return 0
    changed = False
    for key, val in list(data.items()):
        if not isinstance(val, list) or not val or not isinstance(val[0], str):
            continue
        if not any(c.startswith("C0") for c in val):
            continue
        new = []
        for cid in val:
            if cid in struck_ids:
                if cid in mapping:
                    new.append(mapping[cid]); changed = True
                else:
                    changed = True  # drop
            else:
                new.append(cid)
        seen = set(); data[key] = [c for c in new if not (c in seen or seen.add(c))]
        if key == "encoded_clause_ids":
            data["encoded_clause_count"] = len(data[key])
    if changed and apply:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if changed else 0


def main() -> None:
    apply = "--apply" in sys.argv
    print(f"mode: {'APPLY' if apply else 'DRY RUN'}")

    df = _load_clauses()
    struck_ids = set(df.filter(~pl.col("is_in_force"))["clause_id"].to_list())
    print(f"struck clause_ids in parquet: {len(struck_ids)}")

    # Scan YAML sources, rule JSONs, and manifests for struck references.
    referenced: set[str] = set()
    yaml_root = _REPO / "data/gazette/prose_rule_sources"
    for f in sorted(yaml_root.rglob("*.yaml")):
        src = f.read_text(encoding="utf-8")
        for sid in struck_ids:
            if f'"{sid}"' in src:
                referenced.add(sid)
    for f in sorted(_RULES_DIR.glob("*.json")):
        if f.name.endswith(".schema.json"):
            continue
        src = f.read_text(encoding="utf-8")
        for sid in struck_ids:
            if f'"{sid}"' in src:
                referenced.add(sid)
    print(f"struck ids referenced in YAML/JSON files: {len(referenced)}")

    mapping = build_replacement_map(df, referenced)
    print(f"found in-force replacements: {len(mapping)}")
    print(f"to remove (no replacement): {len(referenced - set(mapping))}")

    print("\n=== mapping (struck -> in-force) ===")
    for s, r in sorted(mapping.items()):
        print(f"  {s} -> {r}")
    no_rep = sorted(referenced - set(mapping))
    if no_rep:
        print(f"\nno replacement (will remove): {no_rep}")

    if not apply:
        print("\n(dry run — re-run with --apply to make changes)")
        return

    # Apply: YAML sources
    print("\n=== applying to YAML sources ===")
    total_r = total_rm = 0
    for f in sorted(yaml_root.rglob("*.yaml")):
        r, rm = clean_batch_file(f, mapping, struck_ids, apply=True)
        if r or rm:
            print(f"  {f.relative_to(_REPO)}: +{r} relinked, -{rm} removed")
            total_r += r
            total_rm += rm
    print(f"YAML sources total: +{total_r} relinked, -{total_rm} removed")

    # Apply: rule JSONs
    print("\n=== applying to rule JSONs ===")
    for f in sorted(_RULES_DIR.glob("*.json")):
        if f.name.endswith(".schema.json"):
            continue
        r, rm = clean_json(f, mapping, struck_ids, apply=True)
        if r or rm:
            print(f"  {f.name}: +{r} relinked, -{rm} removed")

    # Apply: manifests
    print("\n=== applying to manifests ===")
    for f in sorted(_MANIFEST_DIR.glob("*.json")):
        n = clean_manifest(f, mapping, struck_ids, apply=True)
        if n:
            print(f"  {f.name}: updated")

    print("\n=== done ===")


if __name__ == "__main__":
    main()
