#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# prune_frontend_releases.sh
#
# Prunes older releases and unreferenced static assets while guaranteeing:
# - Active release (current) is NEVER deleted.
# - Immediate rollback target is NEVER deleted.
# - Assets unreferenced by all retained releases are removed after grace period.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BASE_DIR="${BILUN_FRONTEND_BASE:-/opt/bilun-frontend}"
KEEP="${KEEP_COUNT:-3}"
GRACE="${GRACE_SECONDS:-86400}"

usage() {
  cat <<EOF
Usage: $0 [--base-dir <path>] [--keep <count>] [--grace-seconds <seconds>]
EOF
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-dir) BASE_DIR="$2"; shift 2 ;;
    --keep) KEEP="$2"; shift 2 ;;
    --grace-seconds) GRACE="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown argument: $1" >&2; usage 1 ;;
  esac
done

RELEASES_DIR="$BASE_DIR/releases"
CURRENT_LINK="$BASE_DIR/current"
MANIFESTS_DIR="$BASE_DIR/manifests"
SHARED_ASSETS="$BASE_DIR/assets/_next/static"

python3 -c "
from pathlib import Path
from scripts.deploy.release_manager import prune_old_releases

pruned, deleted_assets = prune_old_releases(
    releases_dir=Path('$RELEASES_DIR'),
    current_link=Path('$CURRENT_LINK'),
    manifests_dir=Path('$MANIFESTS_DIR'),
    shared_assets_static_dir=Path('$SHARED_ASSETS'),
    keep_count=$KEEP,
    grace_seconds=float($GRACE),
)
print(f'[prune] Pruned {len(pruned)} releases: {pruned}')
print(f'[prune] Deleted {deleted_assets} unreferenced stale assets')
"
