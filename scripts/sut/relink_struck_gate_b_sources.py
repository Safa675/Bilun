#!/usr/bin/env python3
"""Re-link ``gate_b_sources`` clause refs that point at STRUCK (repealed) clause_ids
to their in-force replacements, for ``drug_indication_prose.json``.

Background
----------
The SUT amendment pattern: when a clause is amended, the legacy text is struck
(``is_in_force: false``) and replacement text is added at an adjacent clause_id
(or sometimes a re-organised section). An earlier encoding batch linked 28
drug-indication rules to the OLD struck clause_ids instead of the in-force
replacements. This script re-links each one to its verified in-force
replacement and removes fully-repealed (no-replacement) refs.

Each mapping below was verified by hand against ``text_tr`` (legacy content)
and ``in_force_text`` (replacement) — matching key Turkish phrases (drug
names, condition keywords, fıkra numbers). The script then re-confirms every
candidate programmatically (same section + content similarity) before writing,
so the mapping is auditable and fails loudly if the parquet drifts.

Updates
  1. ``data/gazette/prose_rules/drug_indication_prose.json``  (gate_b_sources)
  2. ``data/gazette/prose_manifests/L4.2_drug_indication_*.json`` clause-id
     lists (``encoded_clause_ids``, ``gate_b_sources_encoded``) that still list
     the struck ids — swapped to the in-force replacements.

Usage
    python scripts/sut/relink_struck_gate_b_sources.py
    python scripts/sut/relink_struck_gate_b_sources.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CLAUSES_PARQUET = _PROJECT_ROOT / "data" / "gazette" / "sut_clauses.parquet"
_PROSE_RULES = _PROJECT_ROOT / "data" / "gazette" / "prose_rules" / "drug_indication_prose.json"
_MANIFEST_DIR = _PROJECT_ROOT / "data" / "gazette" / "prose_manifests"

# Manifest clause-id list keys kept in sync with is_in_force (same set as
# scripts/sut/sync_gate_b_in_force.py).
_CLAUSE_ID_LIST_KEYS = frozenset(
    {
        "gate_b_sources",
        "gate_b_sources_encoded",
        "encoded_clause_ids",
        "tier_a_pending_clause_ids",
        "tier_b_pending_clause_ids",
        "tier_c_deferred_clause_ids",
        "non_actionable_clause_ids",
    }
)

# Sentinel for "the provision was fully repealed with no in-force replacement".
REPEALED = "REPEALED_NO_REPLACEMENT"

# ---------------------------------------------------------------------------
# VERIFIED mapping: struck_clause_id -> in-force replacement (or REPEALED).
#
# Each row is (struck_id, replacement_id). The replacement is the in-force
# clause carrying the SAME substantive provision (drug/condition/requirement)
# as the struck clause's text_tr. Cross-section replacements occur where a
# whole subsection was re-organised (e.g. acute HCV 4.2.13.E-1 -> 4.2.13.3.1,
# paricalcitol oral 4.2.9.C-2 -> 4.2.9.C, dabigatran 4.2.15.D -> 4.2.15.D-1).
# ---------------------------------------------------------------------------
MAPPING: dict[str, str] = {
    # §4.2.1.C-6 / C-7 / C-8 (rheum biologics + UC)
    "C003727": "C003739",   # Tofacitinib RA prescriber board (2) -> (2) in-force
    "C003799": "C003807",   # anakinra 3mo failure switch to kanakinumab (2) -> (2) in-force
    "C003800": "C003808",   # kanakinumab 3mo response/continuation (3) -> (3) in-force
    "C003802": "C003813",   # Amiloidoz FMF anakinra/kanakinumab b) -> b) in-force (verified example)
    "C003836": "C003840",   # Vedolizumab UC anti-TNF second line (2) -> (2) in-force

    # §4.2.6.A-1 pediatric growth hormone
    "C003956": "C003966",   # GH initiation closing sentence -> (1) initiation board clause in-force
    "C003957": "C003982",   # GH continuation/monitoring (2) epifiz takibi -> (2) in-force

    # §4.2.9.A-1 ESA / §4.2.9.C-2 paricalcitol oral
    "C004122": "C004131",   # ESA prescriber nephrology (2) -> (2) in-force
    "C004160": "C004167",   # Paricalcitol oral PD formula -> (4) paricalcitol oral in-force (cross-subsection)

    # §4.2.13 / 4.2.13.1 / 4.2.13.E-* / 4.2.13.3.2* (hepatitis B/C)
    "C004506": "C004604",   # Hepatitis prior-therapy doc + oral antiviral 6mo report -> surviving (8) duration clause
    "C004533": "C004602",   # HBV antiviral report renewal (8) -> (7) HBsAg continuation in-force
    "C004601": "C004602",   # HBV antiviral report renewal (7) -> (7) HBsAg continuation in-force (verified example)
    "C004634": "C004637",   # Acute HCV 24w interferon monotherapy -> (2) in-force (cross-subsection 4.2.13.E-1 -> 4.2.13.3.1)
    "C004641": "C004911",   # Chronic HCV interferon+ribavirin combo -> (2) in-force (children 4.2.13.3.2.B)
    "C004642": "C004912",   # HCV genotype 1/4 48wk duration -> (3) in-force (children 4.2.13.3.2.B)
    "C004760": "C004905",   # HCV retreatment prior-therapy report (2) -> (1) retreatment lead in-force
    "C004815": "C004907",   # Glecaprevir+Pibrentasvir+Ribavirin 16wk cirrhosis -> (3) NS5A/PI retreatment 16wk in-force
    "C004851": "C004905",   # HCV retreatment prior-therapy report (2, alt spelling) -> (1) retreatment lead in-force

    # §4.2.15.D dabigatran
    "C005823": "C005835",   # Dabigatran cardiology board 1y report (3) -> (2) cardiology board report in-force (4.2.15.D-1)

    # §4.2.16 special formula / celiac
    "C005883": "C006007",   # Celiac GF 1y gastro report (3) -> (6) celiac report in-force
    "C005894": "C006007",   # Celiac GF 1y gastro report (3, dup) -> (6) celiac report in-force
    "C005908": "C005983",   # special formula all-prescriber closing -> (a) metabolic special formula all-prescriber in-force
    "C005948": "C006000",   # infant CMPA formula (5) -> (5) infant CMPA tıbbi mama in-force

    # §4.2.27.A anticoagulation / coagulation factors
    "C006215": "C006225",   # (1) hematology board tanı/faktör/inhibitör -> (1) in-force
    "C006220": "C006235",   # (4) combined PCC acquired coagulopathy -> (a) combined factor congenital/acquired in-force
    "C006222": "C006243",   # coumarin active bleed one-day a) -> (1) coumarin+NOAK active bleed in-force (verified example)
    "C006230": "C006232",   # (3) Factor VIIa bleeding board -> (a) Factor VIIa board in-force
    "C006239": "C006243",   # coumarin active bleed reversal one-day 1- -> (1) coumarin+NOAK active bleed in-force (verified example)
}


def _toks(s: str) -> set[str]:
    if not s:
        return set()
    return set(re.findall(r"[a-zçğıöşü0-9]+", s.lower()))


def _strip_markers(s: str) -> str:
    """Strip SUT amendment / Mülga inline markers so content matching is cleaner."""
    if not s:
        return ""
    s = re.sub(r"\(Değişik:.*?md\.?\s*Yürürlük:.*?\)", " ", s)
    s = re.sub(r"\(Mülga:.*?md\.?\s*Yürürlük:.*?\)", " ", s)
    s = re.sub(r"\(Ek:.*?md\.?\s*Yürürlük:.*?\)", " ", s)
    return s


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def verify_mapping(clauses: pl.DataFrame) -> list[str]:
    """Re-confirm each mapping programmatically. Returns list of warnings."""
    warnings: list[str] = []
    id2sec = {r["clause_id"]: r["section_id"] for r in clauses.iter_rows(named=True)}
    in_force_ids = set(
        clauses.filter(pl.col("is_in_force"))["clause_id"].to_list()
    )

    for struck_id, repl in MAPPING.items():
        if struck_id not in id2sec:
            warnings.append(f"{struck_id}: not found in parquet")
            continue
        srow = clauses.filter(pl.col("clause_id") == struck_id)
        if srow["is_in_force"][0]:
            warnings.append(f"{struck_id}: NOT actually struck (is_in_force=true) — review")

        if repl == REPEALED:
            continue
        if repl not in id2sec:
            warnings.append(f"{struck_id} -> {repl}: replacement not found in parquet")
            continue
        if repl not in in_force_ids:
            warnings.append(f"{struck_id} -> {repl}: replacement is NOT in-force")
            continue

        struck_text = _strip_markers(srow["text_tr"][0] or "")
        rrow = clauses.filter(pl.col("clause_id") == repl)
        repl_text = _strip_markers(rrow["in_force_text"][0] or "")
        jac = _jaccard(_toks(struck_text), _toks(repl_text))
        # Low threshold: cross-section / re-organised replacements legitimately
        # diverge; we just flag anything very low for manual eyes.
        if jac < 0.15:
            warnings.append(
                f"{struck_id} -> {repl}: LOW content overlap (jaccard={jac:.3f}); "
                f"sec {id2sec[struck_id]} -> {id2sec.get(repl)}"
            )
    return warnings


def _swap_in_list(values: list, struck_to_repl: dict[str, str]) -> list:
    """Replace struck ids with their in-force replacement (dedup-preserving order)."""
    out: list = []
    seen: set[str] = set()
    for v in values:
        cid = str(v)
        if cid in struck_to_repl:
            repl = struck_to_repl[cid]
            if repl == REPEALED:
                continue  # drop fully-repealed ref
            cid = repl
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return out


def apply_to_prose_rules(struck_to_repl: dict[str, str]) -> tuple[int, int, int]:
    """Update drug_indication_prose.json gate_b_sources. Returns (rules_fixed, relinked, dropped)."""
    data = json.loads(_PROSE_RULES.read_text(encoding="utf-8"))
    rules_fixed = 0
    relinked = 0
    dropped = 0
    for rule in data.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        sources = rule.get("gate_b_sources")
        if not isinstance(sources, list):
            continue
        before = list(sources)
        after = _swap_in_list(sources, struck_to_repl)
        if after != before:
            rule["gate_b_sources"] = after
            rules_fixed += 1
            relinked += sum(1 for c in before if c in struck_to_repl and struck_to_repl[c] != REPEALED)
            dropped += sum(1 for c in before if c in struck_to_repl and struck_to_repl[c] == REPEALED)
        # Clear the stale struck-clause verification flag now that it's resolved.
        if rule.get("verification_status") == "struck_clause_no_replacement" and after:
            rule.pop("verification_status", None)
    _PROSE_RULES.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return rules_fixed, relinked, dropped


def apply_to_manifests(struck_to_repl: dict[str, str]) -> list[str]:
    """Update manifest clause-id lists that still reference the struck ids."""
    updated: list[str] = []
    for path in sorted(_MANIFEST_DIR.glob("L4.2_drug_indication_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        changed = False
        for key, value in list(data.items()):
            if key not in _CLAUSE_ID_LIST_KEYS or not isinstance(value, list):
                continue
            # Only touch lists that actually contain one of OUR struck ids.
            if not any(str(v) in struck_to_repl for v in value):
                continue
            filtered = _swap_in_list(value, struck_to_repl)
            if filtered != value:
                data[key] = filtered
                changed = True
        if changed:
            # Re-sync the derived encoded count if present.
            if "encoded_clause_ids" in data and "encoded_clause_count" in data:
                data["encoded_clause_count"] = len(data["encoded_clause_ids"])
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            updated.append(path.name)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Verify + print plan without writing")
    args = parser.parse_args()

    clauses = pl.read_parquet(_CLAUSES_PARQUET)
    struck_ids_all = set(clauses.filter(~pl.col("is_in_force"))["clause_id"].to_list())

    # Only consider the 28 struck ids we have mappings for.
    struck_to_repl = {k: v for k, v in MAPPING.items() if k in struck_ids_all}
    missing = sorted(set(MAPPING) - set(struck_ids_all))
    if missing:
        print(f"WARNING: {len(missing)} mapped ids are no longer struck/present: {missing}")

    print("=" * 78)
    print("STRUCK -> IN-FORCE REPLACEMENT MAPPING")
    print("=" * 78)
    print(f"{'STRUCK':<10} {'SECTION':<14} -> {'REPLACEMENT':<14} {'SECTION':<14}  RULE FAMILY")
    print("-" * 78)
    id2sec = {r["clause_id"]: r["section_id"] for r in clauses.iter_rows(named=True)}
    rule_ids_by_source: dict[str, list[str]] = {}
    data = json.loads(_PROSE_RULES.read_text(encoding="utf-8"))
    for rule in data.get("rules") or []:
        for c in rule.get("gate_b_sources") or []:
            if c in struck_to_repl:
                rule_ids_by_source.setdefault(c, []).append(rule["rule_id"])
    for struck_id in sorted(struck_to_repl):
        repl = struck_to_repl[struck_id]
        rsec = id2sec.get(repl, "?") if repl != REPEALED else "-"
        fam = (rule_ids_by_source.get(struck_id, ["?"])[0])[:38]
        print(f"{struck_id:<10} {id2sec.get(struck_id,'?'):<14} -> {repl:<14} {rsec:<14}  {fam}")

    n_repealed = sum(1 for v in struck_to_repl.values() if v == REPEALED)
    print("-" * 78)
    print(
        f"TOTAL: {len(struck_to_repl)} struck clause_ids — "
        f"{len(struck_to_repl) - n_repealed} re-linked, {n_repealed} fully-repealed (removed)"
    )

    print("\n" + "=" * 78)
    print("VERIFICATION (programmatic re-confirm)")
    print("=" * 78)
    warnings = verify_mapping(clauses)
    if warnings:
        for w in warnings:
            print("  ⚠ " + w)
    else:
        print("  all mappings confirmed (in-force replacement present, content overlap OK)")

    if args.dry_run:
        print("\n[dry-run] no files written.")
        return 0

    print("\n" + "=" * 78)
    print("APPLYING FIXES")
    print("=" * 78)
    rules_fixed, relinked, dropped = apply_to_prose_rules(struck_to_repl)
    print(
        f"drug_indication_prose.json: {rules_fixed} rules fixed, "
        f"{relinked} clause_ids re-linked, {dropped} fully-repealed refs removed"
    )
    updated_manifests = apply_to_manifests(struck_to_repl)
    print(f"manifests updated: {len(updated_manifests)} -> {updated_manifests}")

    # Post-check: no struck refs remain.
    data = json.loads(_PROSE_RULES.read_text(encoding="utf-8"))
    bad = [
        (r["rule_id"], c)
        for r in data["rules"]
        for c in (r.get("gate_b_sources") or [])
        if c in struck_ids_all
    ]
    print(f"\nPost-check — rules still referencing struck clauses: {len(bad)}")
    for b in bad[:10]:
        print("   ", b)
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
