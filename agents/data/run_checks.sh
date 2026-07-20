#!/usr/bin/env bash
# Data Engineer — deterministic health-check runner.
# Runs pipeline_smoke + parquet_freshness. Writes to reports/agent/data/.
#
# Usage:
#   bash agents/data/run_checks.sh
#   bash agents/data/run_checks.sh --smoke-limit 3   # smaller/faster smoke run
set -uo pipefail   # NOT -e: run both checks even if one fails

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
OUT_DIR="reports/agent/data"
mkdir -p "$OUT_DIR"

SMOKE_LIMIT=5
if [ "${1:-}" = "--smoke-limit" ] && [ -n "${2:-}" ]; then
    SMOKE_LIMIT="$2"
fi

echo "[run_checks] Data Engineer — running 2 checkers"
echo "[run_checks] repo: $REPO_ROOT"
echo "[run_checks] output: $OUT_DIR/"
echo ""

echo "=== 1. pipeline_smoke (convert -> curate -> extract -> coverage -> validate) ==="
$PY scripts/agent/pipeline_smoke.py --limit "$SMOKE_LIMIT" 2>&1 | tee "$OUT_DIR/pipeline_smoke_console.txt" | tail -8
echo ""

echo "=== 2. parquet_freshness (raw vs curated mtimes + version_manifest) ==="
$PY scripts/agent/parquet_freshness.py || echo "  parquet_freshness errored"
echo ""

echo "[run_checks] done. Findings:"
ls -1 "$OUT_DIR"/*.md "$OUT_DIR"/*.txt 2>/dev/null | sed 's/^/  /'
echo ""
echo "[run_checks] Review freshness.md, then write your agent report to"
echo "[run_checks]   $OUT_DIR/findings-\$(date +%Y-%m-%d).md"
