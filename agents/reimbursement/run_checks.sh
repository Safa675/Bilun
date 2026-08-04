#!/usr/bin/env bash
# Reimbursement Engineer — deterministic health-check runner.
# Runs the 3 reimbursement-scoped checkers and writes findings to reports/agent/reimbursement/.
# Safe to run locally (no agent needed) to regenerate the baseline.
#
# Usage:
#   bash agents/reimbursement/run_checks.sh          # run all 2
#   bash agents/reimbursement/run_checks.sh --quiet  # suppress per-checker stdout
set -euo pipefail

# Resolve repo root regardless of where this is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
OUT_DIR="reports/agent/reimbursement"
mkdir -p "$OUT_DIR"

QUIET="${1:-}"
REDIRECT="/dev/stdout"
if [ "$QUIET" = "--quiet" ] || [ "$QUIET" = "-q" ]; then
    REDIRECT="/dev/null"
fi

echo "[run_checks] Reimbursement Engineer — running 2 checkers"
echo "[run_checks] repo: $REPO_ROOT"
echo "[run_checks] output: $OUT_DIR/"
echo ""

echo "=== 1. stale_clause_refs (rule gate_b_sources × sut_clauses staleness) ==="
$PY scripts/agent/stale_clause_refs.py $QUIET
echo ""

echo "=== 2. build_sut_coverage (rule_registry coverage matrix) ==="
# NOTE: build_sut_coverage writes 4 parquets to data/gazette/ by default — that would
# mutate committed artifacts (learned 2026-07-20). Redirect to a temp dir so the check
# is read-only w.r.t. the repo; we only want the console summary for the agent.
COV_TMP="$(mktemp -d)"
$PY scripts/sut/build_sut_coverage.py --output-dir "$COV_TMP" > "$OUT_DIR/sut_coverage_console.txt" 2>&1 && \
    echo "  coverage matrix computed -> $COV_TMP (console log: $OUT_DIR/sut_coverage_console.txt)" || \
    echo "  build_sut_coverage FAILED — see $OUT_DIR/sut_coverage_console.txt"
rm -rf "$COV_TMP"
echo ""

echo "[run_checks] done. Findings:"
ls -1 "$OUT_DIR"/*.md "$OUT_DIR"/*.json 2>/dev/null | sed 's/^/  /'
echo ""
echo "[run_checks] Review the markdown files above, then write your agent report to"
echo "[run_checks]   $OUT_DIR/findings-\$(date +%Y-%m-%d).md"
