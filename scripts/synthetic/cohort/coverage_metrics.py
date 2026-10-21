"""Coverage metrics of the synthetic demo cohort (G12 of the demo coverage-first plan).

Which of the 20 billing-report blocks and which of the 528 Wave A rule ids do the demo patients
light up? This script answers it the same way every time. It runs the engine's patient report over
a claims directory (default: the committed `data/synthetic/sut/claims`), applies the metric map of
`plans/data/2026-10-20-demo-coverage-first-plan.md` section 9.2, writes the numbers per patient and
for the cohort as JSON, and prints the difference from an earlier JSON. A new story is then judged
by what it moved ("block `session_uplift` lights, nothing else moves") and not by hand.

    python -m scripts.synthetic.cohort.coverage_metrics --out /tmp/before.json
    ... add a story, rebuild the cohort ...
    python -m scripts.synthetic.cohort.coverage_metrics --out /tmp/after.json --compare /tmp/before.json

The metrics, per patient and for the cohort (the union over the patients):

- **blocks with output**: a block has output when one of its primary lists holds a row
  (`PRIMARY_LISTS`; `lab` and `copay` also count a non-zero saving, `NUMERIC_OUTPUTS`).
- **Wave A rule ids**, out of the roster of the evidence (528): *evaluated* (one evaluation has
  the status `evaluated`: the rule looked, it may have found nothing), *matched* (one evaluated row
  has the decision `matched`: the rule applies to a claim), *with a row* (the id is in the reviews,
  advisories or financial rows).
- **finding kinds**: the distinct kinds of finding the report shows, written `source:kind`: the
  `surface:kind` of each recommended action, the `claim_compliance` rule ids, the drug-indication
  statuses, violations and findings, the audit-exposure kinds, and `miat:violation`.

Known limits. The report is computed from the claim tables alone, the way
`scripts/synthetic/cohort/engine_proof.py` computes it. The patient's `copay_exemption` (the EK-1/A
chronic-disease input that the app's cache path passes) is not passed, so the copay block shows what
the scripts see, one rate correction fewer than the app on the 8 showcase patients, and no
exemption money. The lab feed `lab_df_pl` (the lab results that the cache path merges into the lab
and capture-gap blocks) is not passed either. A block with output says that the engine produced a
row, not that the row is money or clinically right; and the metrics do not test the correctness of
a finding (the engine proof does). `LIMITS` repeats this for the JSON.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
import json
from pathlib import Path
import sys
from typing import Any

REPO = Path(__file__).resolve().parents[3]
DEFAULT_CLAIMS_DIR = REPO / "data" / "synthetic" / "sut" / "claims"
SCHEMA_VERSION = 1

# Names shown on one line of a diff before "... N more".
LIST_CAP = 12

_UPLIFT_BLOCKS = (
    "session_uplift",
    "drg_uplift",
    "blood_uplift",
    "yatak_puani",
    "icu_puani",
    "yenidogan_yatak",
    "refakatci",
    "anestezi_puani",
    "material_uplift",
    "care_setting_review",
    "procedure_addon_uplift",
    "procedure_capture_gap",
    "drg_package_adequacy",
)

# Plan section 9.2: the lists that make a block "have output". One entry per block of
# `BILLING_BLOCK_SPECS` (a test checks the twenty names).
PRIMARY_LISTS: dict[str, tuple[str, ...]] = {
    "lab": ("flagged_tests",),
    "copay": ("rate_corrections", "exemption_sources"),
    "billing_strategy": ("recommendations",),
    **{name: ("opportunities",) for name in _UPLIFT_BLOCKS},
    "medula_rejection_playbook": ("entries",),  # not `required_inputs_missing`
    "claim_submission_checklist": ("items",),
    "materials": (
        "pre_auth_required",
        "miat_restricted",
        "miat_interval_violations",
        "bundled_separate_billing",
        "prose_bundling_violations",
        "specialty_prose_violations",
        "kdv_price_reviews",
    ),
    "drug_indication": ("violations", "findings", "evaluations"),
}

# "or a non-zero saving": fields whose value alone makes the lab and copay blocks lit.
NUMERIC_OUTPUTS: dict[str, tuple[str, ...]] = {
    "lab": ("hemogram_bundling_savings",),
    "copay": (
        "total_copay_savings_try",
        "visit_copay_savings_try",
        "rx_copay_savings_try",
        "patient_copay_waived_total_try",
    ),
}

LIMITS: tuple[str, ...] = (
    "The report is computed from the claim tables only. The patient's `copay_exemption` (the EK-1/A "
    "chronic-disease input of the app's cache path) is not passed: the copay block shows the rate "
    "corrections of the scripts' path (one fewer than the app on the 8 showcase patients) and no "
    "exemption money.",
    "The lab feed `lab_df_pl` is not passed: lab results that the cache path merges into the lab "
    "and capture-gap blocks are not seen.",
    "A block with output means the engine produced a row, not that the row is money or correct.",
    "A Wave A rule id is evaluated when one of its evaluations has the status `evaluated`; a rule "
    "that looked and found nothing is evaluated and not matched.",
)


# --- the metric functions: pure functions of a report written as plain dicts ---------------------


def _rows(value: object) -> list[Mapping[str, Any]]:
    """The mapping items of a list; anything else is no rows."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _nonzero_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value != 0


def block_rows(name: str, block: object) -> int:
    """Rows in the primary lists of the block `name` (the block as a dict); `KeyError` for an unknown block."""
    keys = PRIMARY_LISTS[name]
    if not isinstance(block, Mapping):
        return 0
    return sum(len(value) for key in keys if isinstance(value := block.get(key), list))


def block_has_output(name: str, block: object) -> bool:
    """True when a primary list holds a row, or (lab, copay) a saving field is not zero."""
    if block_rows(name, block) > 0:
        return True
    if not isinstance(block, Mapping):
        return False
    return any(_nonzero_number(block.get(key)) for key in NUMERIC_OUTPUTS.get(name, ()))


def _rule_ids(rows: object) -> set[str]:
    return {row["rule_id"] for row in _rows(rows) if row.get("rule_id")}


def wavea_sets(detail: object) -> dict[str, Any]:
    """The Wave A rule sets of one patient from `wavea_evidence_detail`.

    `rule_ids` is the size of the roster (the ids the evidence counts), the rest are sets of rule
    ids: `evaluated`, `matched`, `review`, `advisory`, `financial` and `with_row` (their union).
    """
    data = detail if isinstance(detail, Mapping) else {}
    evaluations = [row for row in _rows(data.get("evaluations")) if row.get("rule_id")]
    evaluated_rows = [row for row in evaluations if row.get("evaluation_status") == "evaluated"]
    counts = data.get("counts")
    by_rule = counts.get("by_rule") if isinstance(counts, Mapping) else None
    review = _rule_ids(data.get("reviews"))
    advisory = _rule_ids(data.get("advisories"))
    financial = _rule_ids(data.get("financial_rows"))
    return {
        "rule_ids": len(by_rule) if isinstance(by_rule, Mapping) else 0,
        "evaluated": {row["rule_id"] for row in evaluated_rows},
        "matched": {row["rule_id"] for row in evaluated_rows if row.get("decision") == "matched"},
        "review": review,
        "advisory": advisory,
        "financial": financial,
        "with_row": review | advisory | financial,
    }


def finding_kinds(report: Mapping[str, Any]) -> set[str]:
    """The kinds of finding a report shows, as `source:kind` strings (see the module docstring)."""
    kinds: set[str] = set()
    for row in _rows(report.get("recommended_actions")):
        if row.get("surface") and row.get("kind"):
            kinds.add(f"action:{row['surface']}:{row['kind']}")
    compliance = report.get("claim_compliance")
    for row in _rows(compliance.get("findings") if isinstance(compliance, Mapping) else None):
        if row.get("rule_id"):
            kinds.add(f"compliance:{row['rule_id']}")
    drug = report.get("drug_indication")
    drug = drug if isinstance(drug, Mapping) else {}
    for row in _rows(drug.get("evaluations")):
        if row.get("applicability_status"):
            kinds.add(f"drug_status:{row['applicability_status']}")
    for row in _rows(drug.get("violations")):
        if kind := row.get("violation_kind") or row.get("applicability_status"):
            kinds.add(f"drug_violation:{kind}")
    for row in _rows(drug.get("findings")):
        if row.get("finding_kind"):
            kinds.add(f"drug_finding:{row['finding_kind']}")
    for row in _rows(report.get("audit_exposure_rows")):
        if row.get("kind"):
            kinds.add(f"audit_exposure:{row['kind']}")
    materials = report.get("materials")
    if isinstance(materials, Mapping) and _rows(materials.get("miat_interval_violations")):
        kinds.add("miat:violation")
    return kinds


def patient_metrics(report: Mapping[str, Any], *, claims: int) -> dict[str, Any]:
    """The metrics of one patient's report (as plain dicts); the result is plain JSON."""
    sets = wavea_sets(report.get("wavea_evidence_detail"))
    return {
        "claims": claims,
        "blocks": {name: block_rows(name, report.get(name)) for name in PRIMARY_LISTS},
        "blocks_with_output": sorted(
            name for name in PRIMARY_LISTS if block_has_output(name, report.get(name))
        ),
        "wavea": {
            "rule_ids": sets["rule_ids"],
            "evaluated": len(sets["evaluated"]),
            "matched": len(sets["matched"]),
            "with_row": len(sets["with_row"]),
            "review": len(sets["review"]),
            "advisory": len(sets["advisory"]),
            "financial": len(sets["financial"]),
            "evaluated_ids": sorted(sets["evaluated"]),
            "matched_ids": sorted(sets["matched"]),
            "review_ids": sorted(sets["review"]),
            "advisory_ids": sorted(sets["advisory"]),
            "financial_ids": sorted(sets["financial"]),
        },
        "finding_kinds": sorted(finding_kinds(report)),
    }


def summarize(per_patient: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The cohort metrics: the union over the patients' metrics."""
    entries = list(per_patient.values())

    def union(key: str) -> list[str]:
        return sorted({item for entry in entries for item in entry["wavea"][key]})

    lit = sorted({name for entry in entries for name in entry["blocks_with_output"]})
    evaluated, matched = union("evaluated_ids"), union("matched_ids")
    review, advisory, financial = union("review_ids"), union("advisory_ids"), union("financial_ids")
    row_ids = sorted({*review, *advisory, *financial})
    kinds = sorted({kind for entry in entries for kind in entry["finding_kinds"]})
    return {
        "patients": len(entries),
        "claims": sum(entry["claims"] for entry in entries),
        "blocks": {
            "total": len(PRIMARY_LISTS),
            "with_output": len(lit),
            "with_output_names": lit,
            "without_output_names": sorted(set(PRIMARY_LISTS) - set(lit)),
        },
        "wavea": {
            "rule_ids": max((entry["wavea"]["rule_ids"] for entry in entries), default=0),
            "evaluated": len(evaluated),
            "matched": len(matched),
            "with_row": len(row_ids),
            "review": len(review),
            "advisory": len(advisory),
            "financial": len(financial),
            "evaluated_ids": evaluated,
            "matched_ids": matched,
            "row_ids": row_ids,
        },
        "finding_kinds": {"count": len(kinds), "kinds": kinds},
    }


# --- the engine run ------------------------------------------------------------------------------


def measure_patients(
    claims_dir: Path | str = DEFAULT_CLAIMS_DIR, patient_ids: Sequence[str] | None = None
) -> dict[str, dict[str, Any]]:
    """Run the patient report over `claims_dir` and return the metrics of each patient (all, or `patient_ids`)."""
    from src.bilun.cache.build_streaming import json_ready
    from src.bilun.domain.billing.patient_report import compute_patient_billing_report
    from src.bilun.domain.claims.patient_context import build_patient_claim_context

    from .engine_proof import load_showcase_dataset

    dataset = load_showcase_dataset(claims_dir)
    wanted = sorted(dataset.claims_by_patient) if patient_ids is None else list(patient_ids)
    unknown = [pid for pid in wanted if pid not in dataset.claims_by_patient]
    if unknown:
        raise ValueError(f"not a patient of {claims_dir}: {', '.join(unknown)}")
    measured: dict[str, dict[str, Any]] = {}
    for pid in sorted(set(wanted)):
        context = build_patient_claim_context(pid, dataset)
        report = compute_patient_billing_report(pid, claim_context=context)
        measured[pid] = patient_metrics(json_ready(report), claims=len(context.claims))
    return measured


def measure(
    claims_dir: Path | str = DEFAULT_CLAIMS_DIR, patient_ids: Sequence[str] | None = None
) -> dict[str, Any]:
    """The metrics document: per patient and for the cohort, with the stated limits."""
    per_patient = measure_patients(claims_dir, patient_ids)
    return {
        "schema_version": SCHEMA_VERSION,
        "limits": list(LIMITS),
        "cohort": summarize(per_patient),
        "patients": per_patient,
    }


# --- the difference between two documents --------------------------------------------------------


def _cut(items: Sequence[str]) -> str:
    shown = ", ".join(items[:LIST_CAP])
    return shown if len(items) <= LIST_CAP else f"{shown}, ... {len(items) - LIST_CAP} more"


def _change(
    label: str,
    old_items: Iterable[str],
    new_items: Iterable[str],
    old_count: int | None = None,
    new_count: int | None = None,
) -> str | None:
    """`label: 9 -> 10 (+a, -b)`, or None when neither the items nor the counts moved."""
    old_set, new_set = set(old_items), set(new_items)
    before = len(old_set) if old_count is None else old_count
    after = len(new_set) if new_count is None else new_count
    added, removed = sorted(new_set - old_set), sorted(old_set - new_set)
    if not added and not removed and before == after:
        return None
    text = f"{label}: {before} -> {after}"
    names = [f"+{item}" for item in added] + [f"-{item}" for item in removed]
    return f"{text} ({_cut(names)})" if names else text


def _row_ids(entry: Mapping[str, Any]) -> set[str]:
    wavea = entry["wavea"]
    return {*wavea["review_ids"], *wavea["advisory_ids"], *wavea["financial_ids"]}


def diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    """What moved from the metrics document `before` to `after`; an empty list when nothing did."""
    old, new = before["cohort"], after["cohort"]
    old_patients, new_patients = before["patients"], after["patients"]
    candidates = [
        _change("patients", old_patients, new_patients),
        _change("claims", [], [], old["claims"], new["claims"]),
        _change(
            "blocks with output", old["blocks"]["with_output_names"], new["blocks"]["with_output_names"]
        ),
        _change(
            "Wave A rule ids evaluated", old["wavea"]["evaluated_ids"], new["wavea"]["evaluated_ids"]
        ),
        _change("Wave A rule ids matched", old["wavea"]["matched_ids"], new["wavea"]["matched_ids"]),
        _change("Wave A rule ids with a row", old["wavea"]["row_ids"], new["wavea"]["row_ids"]),
        _change("finding kinds", old["finding_kinds"]["kinds"], new["finding_kinds"]["kinds"]),
    ]
    lines = [line for line in candidates if line]
    for pid in sorted({*old_patients, *new_patients}):
        if pid not in old_patients:
            entry = new_patients[pid]
            lines.append(
                f"{pid}: new patient, {len(entry['blocks_with_output'])} blocks with output, "
                f"{entry['wavea']['evaluated']} Wave A rule ids evaluated, "
                f"{entry['wavea']['matched']} matched"
            )
        elif pid not in new_patients:
            lines.append(f"{pid}: patient left the cohort")
        else:
            was, now = old_patients[pid], new_patients[pid]
            parts = [
                _change("blocks with output", was["blocks_with_output"], now["blocks_with_output"]),
                _change("evaluated", was["wavea"]["evaluated_ids"], now["wavea"]["evaluated_ids"]),
                _change("matched", was["wavea"]["matched_ids"], now["wavea"]["matched_ids"]),
                _change("with a row", _row_ids(was), _row_ids(now)),
                _change("finding kinds", was["finding_kinds"], now["finding_kinds"]),
            ]
            changed = [part for part in parts if part]
            if changed:
                lines.append(f"{pid}: " + "; ".join(changed))
    return lines


# --- command line --------------------------------------------------------------------------------


def summary_lines(document: Mapping[str, Any]) -> list[str]:
    """The cohort numbers of a metrics document, as printed by the command."""
    cohort = document["cohort"]
    blocks, wavea = cohort["blocks"], cohort["wavea"]
    return [
        f"patients: {cohort['patients']}, claims: {cohort['claims']}",
        f"blocks with output: {blocks['with_output']} of {blocks['total']} "
        f"({', '.join(blocks['with_output_names'])})",
        f"Wave A rule ids evaluated: {wavea['evaluated']} of {wavea['rule_ids']}",
        f"Wave A rule ids matched: {wavea['matched']}",
        f"Wave A rule ids with a row: {wavea['with_row']} "
        f"(reviews {wavea['review']}, advisories {wavea['advisory']}, financial {wavea['financial']})",
        f"finding kinds: {cohort['finding_kinds']['count']}",
    ]


def load_document(path: Path) -> dict[str, Any]:
    """Read an earlier metrics file; `ValueError` when it is not one this version can compare with."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from None
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
        found = raw.get("schema_version") if isinstance(raw, dict) else raw
        raise ValueError(f"{path}: schema_version {found!r}, this script writes {SCHEMA_VERSION}")
    if not isinstance(raw.get("cohort"), dict) or not isinstance(raw.get("patients"), dict):
        raise ValueError(f"{path}: has no cohort and patients sections")
    return raw


def main(argv: Sequence[str] | None = None) -> int:
    """`python -m scripts.synthetic.cohort.coverage_metrics [--claims-dir DIR] [--out FILE] [--compare FILE]`."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.synthetic.cohort.coverage_metrics",
        description="Measure which report blocks and Wave A rules the demo patients light up.",
    )
    parser.add_argument("--claims-dir", type=Path, default=DEFAULT_CLAIMS_DIR, help="claims tables")
    parser.add_argument("--out", type=Path, help="write the metrics JSON here")
    parser.add_argument("--compare", type=Path, help="print the difference from this earlier JSON")
    parser.add_argument("--patients", nargs="+", help="measure only these patient ids")
    args = parser.parse_args(argv)

    earlier = None
    if args.compare is not None:  # fail before the engine runs, not after
        try:
            earlier = load_document(args.compare)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    document = measure(args.claims_dir, args.patients)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        args.out.write_text(text, encoding="utf-8")
    print("\n".join(summary_lines(document)))
    if earlier is not None:
        lines = diff(earlier, document)
        if lines:
            print(f"changes against {args.compare}:")
            print("\n".join(f"  {line}" for line in lines))
        else:
            print(f"no change against {args.compare}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
