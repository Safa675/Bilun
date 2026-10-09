#!/usr/bin/env bash
set -euo pipefail
export CI=true

cd "$(dirname "${BASH_SOURCE[0]}")/.."
python=/home/safa/Documents/Bilun/.venv/bin/python

/home/safa/miniforge3/bin/ruff check src/ scripts/

mkdir -p "$HOME/.cache"
basetemp=$(mktemp -d "$HOME/.cache/codex-ci-pytest.XXXXXX")
trap 'rm -rf -- "$basetemp"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"$python" -m pytest -q -n auto -m "not strict_release" --durations=20 --basetemp="$basetemp"
rm -rf -- "$basetemp"

"$python" scripts/sut/compile_rules.py --check
"$python" scripts/sut/audit_manifest_parity.py --drug-only

cd frontend
npm ci
npx tsc --noEmit
npx vitest run
npm run build
"$python" ../scripts/deploy/verify_public_assets.py --frontend .
