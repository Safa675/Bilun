#!/usr/bin/env bash
# Build one staging release in place: Python env, frontend, and (when asked) the synthetic cache.
# Called by update.sh inside a MemoryMax scope:  build.sh RELEASE_DIR CACHE_PATH REBUILD(0|1)
set -Eeuo pipefail
RELEASE=$1 CACHE=$2 REBUILD=$3
cd "$RELEASE"
/usr/bin/python3.13 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv/bin/python -m pip check
(
  cd frontend
  export NODE_OPTIONS=--max-old-space-size=4096
  npm ci --no-audit --no-fund
  npm run build
  mkdir -p .next/standalone/frontend/.next
  cp -a .next/static .next/standalone/frontend/.next/static
  [[ ! -d public ]] || cp -a public .next/standalone/frontend/public
  [[ -f .next/standalone/frontend/server.js ]]
)
[[ $REBUILD == 1 ]] || exit 0
export BILUN_CLAIMS_DIR="$RELEASE/data/synthetic/sut/claims" BILUN_CLEAN_DIR="$RELEASE/data/synthetic/sut/clean"
export BILUN_CACHE_DB_PATH="$CACHE" BILUN_DATA_MODE=synthetic_demo
.venv/bin/python scripts/bilun/build_cache.py --db-path "$CACHE" --activate --sut-data-mode synthetic_demo \
  --sut-claims-dir "$BILUN_CLAIMS_DIR" --sut-clean-dir "$BILUN_CLEAN_DIR" --payload-workers 2 --billing-workers 2
.venv/bin/python - "$CACHE" <<'PY'
import sys, duckdb
with duckdb.connect(sys.argv[1], read_only=True) as con:
    row = con.execute("SELECT active_build_id FROM build_pointer_scopes WHERE scope = 'bilun'").fetchone()
assert row and row[0], "cache lacks an active synthetic build"
PY
