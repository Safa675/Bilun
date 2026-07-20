"""Load an agent's prior memory + print a 'Prior context' summary.

Run this at the START of an agent conversation (Step 0 in the role's system prompt).
The agent reads the printed output to know what it found last run, so it can diff
rather than re-discover the baseline.

Usage:
    Z_API_KEY=... python scripts/agent/memory/load.py --role reimbursement_engineer
    Z_API_KEY=... python scripts/agent/memory/load.py --role reimbursement_engineer --query "wrong mappings"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, UTC

from scripts.agent.memory.config import get_memory, validate_role


def _format_memory(rec: dict) -> str:
    """Format one memory record for human reading."""
    memory = rec.get("memory", "")
    created = rec.get("created_at", "")
    # mem0 timestamps look like '2026-07-20T12:34:56' — extract date for brevity
    date_part = created.split("T")[0] if "T" in created else created
    categories = rec.get("categories") or {}
    cat_str = f" [{','.join(categories.keys())}]" if categories else ""
    return f"- ({date_part}){cat_str} {memory}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--role", required=True, help="Agent role namespace")
    parser.add_argument(
        "--query",
        default=None,
        help="Semantic search query. If omitted, returns all memories for the role (most recent first).",
    )
    parser.add_argument("--limit", type=int, default=10, help="Max memories to return")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON instead of human text")
    args = parser.parse_args()

    role = validate_role(args.role)

    try:
        m = get_memory()
    except RuntimeError as e:
        print(f"[load] CONFIG ERROR: {e}", file=sys.stderr)
        return 2

    if args.query:
        results = m.search(args.query, filters={"user_id": role}, limit=args.limit)
        records = results.get("results", []) if isinstance(results, dict) else (results or [])
        header = f"search('{args.query}', {role})"
    else:
        results = m.get_all(filters={"user_id": role}, limit=args.limit)
        records = results.get("results", []) if isinstance(results, dict) else (results or [])
        header = f"all memories ({role})"

    if args.json:
        print(json.dumps({"role": role, "count": len(records), "records": records}, indent=2, default=str))
        return 0

    # Human-readable output (what the agent reads at conversation start)
    print(f"=== Prior context ({role}) ===")
    print(f"Loaded: {datetime.now(UTC).isoformat(timespec='seconds')}")
    print(f"Total memories: {len(records)}")
    print()
    if not records:
        print("(no prior memory — this looks like the first run)")
        print()
        print("Proceed with a fresh investigation. Baseline checker outputs are at")
        print("reports/agent/<role>/baseline-*.md if any exist.")
        return 0

    print(f"--- {header} (top {len(records)}) ---")
    for rec in records:
        print(_format_memory(rec))
    print()
    print("Use this to DIFF against today's checker output. Report 'N new, M resolved' —")
    print("do NOT re-list the entire baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
