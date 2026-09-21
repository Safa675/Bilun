#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# rollback_frontend.sh
#
# Manually roll back the active frontend to a previous release.
# Atomically restores the current symlink, restarts the service, and verifies.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${BILUN_FRONTEND_BASE:-/opt/bilun-frontend}"
TARGET_SHA=""
PORT="${PORT:-3000}"

usage() {
  cat <<EOF
Usage: $0 [--to <40-char-git-sha>] [--base-dir <path>] [--port <port>]
If --to is omitted, rolls back to the most recent previous release.
EOF
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --to) TARGET_SHA="$2"; shift 2 ;;
    --base-dir) BASE_DIR="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown argument: $1" >&2; usage 1 ;;
  esac
done

CURRENT_LINK="$BASE_DIR/current"
RELEASES_DIR="$BASE_DIR/releases"

if [[ ! -L "$CURRENT_LINK" ]]; then
  echo "Error: $CURRENT_LINK is not a symlink" >&2
  exit 1
fi

CURRENT_TARGET="$(readlink -f "$CURRENT_LINK")"
CURRENT_SHA="$(basename "$CURRENT_TARGET")"

if [[ -z "$TARGET_SHA" ]]; then
  # Find the newest release that is NOT the current active one
  TARGET_PATH=$(find "$RELEASES_DIR" -maxdepth 1 -mindepth 1 -type d ! -name "$CURRENT_SHA" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2- || true)
  if [[ -z "$TARGET_PATH" || ! -d "$TARGET_PATH" ]]; then
    echo "Error: No previous release found in $RELEASES_DIR to roll back to!" >&2
    exit 1
  fi
  TARGET_SHA="$(basename "$TARGET_PATH")"
fi

TARGET_DIR="$RELEASES_DIR/$TARGET_SHA"
if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Error: Target release directory does not exist: $TARGET_DIR" >&2
  exit 1
fi

echo "[rollback] Rolling back from $CURRENT_SHA to $TARGET_SHA..."

python3 -c "
from pathlib import Path
from scripts.deploy.release_manager import atomic_rollback

atomic_rollback(
    previous_target=Path('$TARGET_DIR'),
    current_link=Path('$CURRENT_LINK'),
)
"

echo "[rollback] Restarting bilun-frontend service..."
if command -v systemctl >/dev/null 2>&1; then
  systemctl restart bilun-frontend
fi

echo "[rollback] Verifying restored release on port $PORT..."
sleep 2
python3 "$SCRIPT_DIR/verify_frontend_assets.py" "http://127.0.0.1:$PORT/login"

echo "[rollback] SUCCESS: Successfully rolled back to $TARGET_SHA."
