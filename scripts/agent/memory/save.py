"""Save an agent's findings report to memory.

Run this at the END of an agent conversation (Step 4 in the role's system prompt).
Reads the findings report, uses mem0's LLM (glm-4.6) to distill 3-7 facts, stores each
under the role's namespace. Recurring facts update the existing memory (mem0 dedup).

Usage:
    Z_API_KEY=... python scripts/agent/memory/save.py \\
        --role reimbursement_engineer \\
        --report reports/agent/reimbursement/findings-2026-07-20.md

Design notes:
- Only the report FILE is sent to mem0's add() — not raw parquet rows. The LLM extracts
  the distilled facts; we don't hand-craft them. This keeps the integration simple at
  the cost of LLM tokens (~2-5k per save).
- mem0 consolidates semantically-equivalent memories automatically. Running the same
  report twice does NOT create duplicates — the second call updates the first.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, UTC
from pathlib import Path

from scripts.agent.memory.config import get_memory, validate_role

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--role", required=True, help="Agent role namespace")
    parser.add_argument(
        "--report",
        required=True,
        type=Path,
        help="Path to the findings markdown report to distill into memory",
    )
    parser.add_argument(
        "--metadata-json",
        default=None,
        help="Optional JSON string merged into each memory's metadata (e.g. '{\"run_kind\":\"scheduled\"}')",
    )
    args = parser.parse_args()

    role = validate_role(args.role)

    # Resolve report path (allow relative to CWD or PROJECT_ROOT)
    report_path = args.report
    if not report_path.is_absolute():
        report_path = (Path.cwd() / report_path) if (Path.cwd() / report_path).exists() else (PROJECT_ROOT / report_path)
    if not report_path.exists():
        print(f"[save] report not found: {report_path}", file=sys.stderr)
        return 1

    report_text = report_path.read_text(encoding="utf-8")
    if not report_text.strip():
        print(f"[save] report is empty: {report_path}", file=sys.stderr)
        return 1

    # Cap input length to prevent runaway LLM cost AND to keep mem0's fact-extraction
    # focused. Large raw reports (8KB+ of structured markdown) confuse the extractor —
    # it returns 0 memories because the signal-to-noise is too low. The findings REPORT
    # is the durable artifact; memory should hold only the headline distillation. So we
    # extract just the summary section + first ~30 lines (the parts a human would skim).
    MAX_REPORT_CHARS = 2500
    if len(report_text) > MAX_REPORT_CHARS:
        # Try to keep the Summary section if present, else just the head
        summary_marker = report_text.lower().find("## summary")
        if summary_marker != -1 and summary_marker < MAX_REPORT_CHARS:
            # Keep from summary to ~MAX_REPORT_CHARS chars after it
            kept = report_text[summary_marker : summary_marker + MAX_REPORT_CHARS]
        else:
            kept = report_text[:MAX_REPORT_CHARS]
        report_text = kept + "\n\n[... report truncated for memory extraction; full report at the source_report path ...]"
        print(f"[save] truncated report to ~{MAX_REPORT_CHARS} chars (was {len(report_text)}); memory holds summary only")

    import json
    metadata = {
        "run_date": datetime.now(UTC).date().isoformat(),
        "source_report": str(report_path.relative_to(PROJECT_ROOT)) if str(PROJECT_ROOT) in str(report_path) else str(report_path),
    }
    if args.metadata_json:
        try:
            metadata.update(json.loads(args.metadata_json))
        except json.JSONDecodeError as e:
            print(f"[save] bad --metadata-json: {e}", file=sys.stderr)
            return 1

    try:
        m = get_memory()
    except RuntimeError as e:
        print(f"[save] CONFIG ERROR: {e}", file=sys.stderr)
        return 2

    # mem0's add() takes a string OR a list of messages. A plain string is the simplest
    # path — mem0's LLM extracts facts from it. user_id is the namespace.
    print(f"[save] distilling {len(report_text)} chars from {report_path.name} into memory for {role}...")
    result = m.add(
        report_text,
        user_id=role,
        metadata=metadata,
        # inferred=False means "extract facts from this text" (default True behaves same
        # but we make it explicit).
    )

    # mem0 returns a dict with 'results' (memories added/updated) and 'relations'
    added = []
    if isinstance(result, dict):
        for r in result.get("results", []):
            added.append(f"{r.get('event','?')}: {r.get('memory','')[:100]}")

    print(f"[save] done. {len(added)} memories written/updated:")
    for line in added:
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
