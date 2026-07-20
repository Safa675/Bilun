#!/usr/bin/env bash
# Full-stack Engineer — deterministic health-check runner.
# Runs endpoint_coverage + frontend guardrails (tsc, vitest). Writes to reports/agent/fullstack/.
#
# Usage:
#   bash agents/fullstack/run_checks.sh
set -uo pipefail   # NOT -e: we want to run all checks even if one fails

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
OUT_DIR="reports/agent/fullstack"
mkdir -p "$OUT_DIR"

# Locate node/npm (per tasks/lessons.md 2026-06-14 — may not be on PATH)
NODE_BIN="$HOME/.local/node-v22.16.0-linux-x64/bin"
if [ -d "$NODE_BIN" ]; then export PATH="$NODE_BIN:$PATH"; fi

echo "[run_checks] Full-stack Engineer — running 3 checkers"
echo "[run_checks] repo: $REPO_ROOT"
echo "[run_checks] output: $OUT_DIR/"
echo ""

echo "=== 1. endpoint_coverage (app.routes × tests/unit/api AST diff) ==="
$PY scripts/agent/endpoint_coverage.py || echo "  endpoint_coverage errored"
echo ""

echo "=== 2. frontend tsc --noEmit (TS strict mode guardrail) ==="
if command -v npx >/dev/null 2>&1; then
    (cd frontend && npx tsc --noEmit 2>&1 | tee "$OUT_DIR/tsc.txt") && \
        echo "  tsc clean -> $OUT_DIR/tsc.txt" || \
        echo "  tsc FAILED — see $OUT_DIR/tsc.txt"
else
    echo "  SKIP: npx not on PATH (node not installed)"
fi
echo ""

echo "=== 3. frontend vitest run (test guardrail) ==="
if command -v npx >/dev/null 2>&1; then
    (cd frontend && npx vitest run --reporter=dot 2>&1 | tee "$OUT_DIR/vitest.txt" | tail -5) && \
        echo "  vitest green -> $OUT_DIR/vitest.txt" || \
        echo "  vitest FAILED — see $OUT_DIR/vitest.txt"
else
    echo "  SKIP: npx not on PATH"
fi
echo ""

echo "[run_checks] done. Findings:"
ls -1 "$OUT_DIR"/*.md "$OUT_DIR"/*.txt 2>/dev/null | sed 's/^/  /'
