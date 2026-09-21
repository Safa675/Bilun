#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build_frontend_release.sh
#
# Builds a standalone, immutable Next.js release in a disposable detached
# git worktree. Never mutates the active production directory or live release.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${BILUN_REPO_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
BASE_DIR="${BILUN_FRONTEND_BASE:-/opt/bilun-frontend}"

SHA=""
RUN_ID="run-$(date +%s)-$$"

usage() {
  cat <<EOF
Usage: $0 --sha <40-char-git-sha> [--run-id <run-id>] [--repo-dir <path>] [--base-dir <path>]
EOF
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sha) SHA="$2"; shift 2 ;;
    --run-id) RUN_ID="$2"; shift 2 ;;
    --repo-dir) REPO_DIR="$2"; shift 2 ;;
    --base-dir) BASE_DIR="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown argument: $1" >&2; usage 1 ;;
  esac
done

if [[ -z "$SHA" ]]; then
  echo "Error: --sha is required" >&2
  usage 1
fi

BUILDS_DIR="$BASE_DIR/builds"
RELEASES_DIR="$BASE_DIR/releases"
STAGING_DIR="$BASE_DIR/staging"
MANIFESTS_DIR="$BASE_DIR/manifests"

mkdir -p "$BUILDS_DIR" "$RELEASES_DIR" "$STAGING_DIR" "$MANIFESTS_DIR"

python3 -c "
from pathlib import Path
from scripts.deploy.release_manager import build_worktree_release

build_worktree_release(
    repo_dir=Path('$REPO_DIR'),
    sha='$SHA',
    run_id='$RUN_ID',
    builds_dir=Path('$BUILDS_DIR'),
    staging_dir=Path('$STAGING_DIR'),
    releases_dir=Path('$RELEASES_DIR'),
    manifests_dir=Path('$MANIFESTS_DIR'),
)
"
