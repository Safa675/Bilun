#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy_frontend.sh
#
# End-to-end atomic deployment pipeline for the Bilun Next.js frontend:
# 1. Advisory deploy lock
# 2. Disposable detached worktree build
# 3. Private port candidate server & full asset verification
# 4. Shared static asset sync with checksum collision protection
# 5. Atomic symlink activation
# 6. Service restart & loopback + public verification
# 7. Backward compatibility check for retained previous assets
# 8. Automatic rollback if activation/verification fails
# 9. Retention pruning
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${BILUN_REPO_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
BASE_DIR="${BILUN_FRONTEND_BASE:-/opt/bilun-frontend}"

SHA=""
RUN_ID="ci-$(date +%s)"
PORT="${PORT:-3000}"
CANDIDATE_PORT="${CANDIDATE_PORT:-3099}"
PUBLIC_URL="${PUBLIC_URL:-https://app.bilun.tech/login}"
SKIP_PUBLIC="${SKIP_PUBLIC:-0}"

usage() {
  cat <<EOF
Usage: $0 --sha <40-char-git-sha> [--run-id <run-id>] [--repo-dir <path>] [--base-dir <path>] [--public-url <url>]
EOF
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sha) SHA="$2"; shift 2 ;;
    --run-id) RUN_ID="$2"; shift 2 ;;
    --repo-dir) REPO_DIR="$2"; shift 2 ;;
    --base-dir) BASE_DIR="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --candidate-port) CANDIDATE_PORT="$2"; shift 2 ;;
    --public-url) PUBLIC_URL="$2"; shift 2 ;;
    --skip-public) SKIP_PUBLIC=1; shift 1 ;;
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
ASSETS_DIR="$BASE_DIR/assets/_next/static"
CURRENT_LINK="$BASE_DIR/current"
LOCK_FILE="$BASE_DIR/deploy.lock"

mkdir -p "$BUILDS_DIR" "$RELEASES_DIR" "$STAGING_DIR" "$MANIFESTS_DIR" "$ASSETS_DIR"

# Acquire advisory flock for entire deploy transaction
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[deploy] Waiting for concurrent deploy to release lock at $LOCK_FILE..."
  flock 9
fi
echo "[deploy] Deploy lock acquired."

PREVIOUS_TARGET=""
if [[ -L "$CURRENT_LINK" ]]; then
  PREVIOUS_TARGET="$(readlink -f "$CURRENT_LINK" 2>/dev/null || true)"
fi

echo "=== BILUN FRONTEND DEPLOYMENT TRANSACTION ==="
echo "Target commit SHA:  $SHA"
echo "Workflow Run ID:    $RUN_ID"
echo "Previous active:    ${PREVIOUS_TARGET:-<none>}"
echo "Releases root:      $RELEASES_DIR"
echo "============================================="

# ── 1. Build & assemble release ──────────────────────────────────────────────
echo "[deploy] Building release for $SHA..."
STAGING_RELEASE=$(python3 -c "
from pathlib import Path
from scripts.deploy.release_manager import build_worktree_release

path = build_worktree_release(
    repo_dir=Path('$REPO_DIR'),
    sha='$SHA',
    run_id='$RUN_ID',
    builds_dir=Path('$BUILDS_DIR'),
    staging_dir=Path('$STAGING_DIR'),
    releases_dir=Path('$RELEASES_DIR'),
    manifests_dir=Path('$MANIFESTS_DIR'),
)
print(path)
")

# If release was already built and identical, STAGING_RELEASE points to RELEASES_DIR/$SHA
if [[ "$STAGING_RELEASE" == "$RELEASES_DIR/$SHA" && "$PREVIOUS_TARGET" == "$RELEASES_DIR/$SHA" ]]; then
  echo "[deploy] Release $SHA is already active on current. Deployment is idempotent no-op."
  exit 0
fi

# ── 2. Candidate verification on private port ────────────────────────────────
if [[ -d "$STAGING_DIR/$SHA" ]]; then
  echo "[deploy] Starting candidate server on private port $CANDIDATE_PORT..."
  
  CANDIDATE_PID=""
  cleanup_candidate() {
    if [[ -n "$CANDIDATE_PID" ]] && kill -0 "$CANDIDATE_PID" 2>/dev/null; then
      echo "[deploy] Stopping candidate server (PID $CANDIDATE_PID)..."
      kill -15 "$CANDIDATE_PID" 2>/dev/null || true
      wait "$CANDIDATE_PID" 2>/dev/null || true
    fi
  }
  trap cleanup_candidate EXIT

  PORT="$CANDIDATE_PORT" HOSTNAME=127.0.0.1 NODE_ENV=production node "$STAGING_DIR/$SHA/server.js" > /tmp/candidate_server.log 2>&1 &
  CANDIDATE_PID=$!

  # Poll candidate until ready
  CANDIDATE_READY=0
  for i in $(seq 1 30); do
    if curl -s -o /dev/null "http://127.0.0.1:$CANDIDATE_PORT/login"; then
      CANDIDATE_READY=1
      break
    fi
    sleep 0.5
  done

  if [[ $CANDIDATE_READY -ne 1 ]]; then
    echo "[deploy] ERROR: Candidate server failed to start on port $CANDIDATE_PORT!" >&2
    tail -n 30 /tmp/candidate_server.log >&2 || true
    rm -rf "$STAGING_DIR/$SHA"
    exit 1
  fi

  echo "[deploy] Verifying candidate HTML and referenced assets on private port..."
  if ! python3 "$SCRIPT_DIR/verify_frontend_assets.py" "http://127.0.0.1:$CANDIDATE_PORT/login"; then
    echo "[deploy] ERROR: Candidate asset verification failed! Aborting deployment." >&2
    rm -rf "$STAGING_DIR/$SHA"
    exit 1
  fi
  echo "[deploy] Candidate passed all asset verifications."

  cleanup_candidate
  trap - EXIT

  # ── 3. Publish to shared asset store & finalize release directory ──────────
  echo "[deploy] Syncing static assets to shared store with collision protection..."
  python3 -c "
from pathlib import Path
from scripts.deploy.release_manager import sync_shared_assets

copied, skipped = sync_shared_assets(
    release_dir=Path('$STAGING_DIR/$SHA'),
    shared_assets_static_dir=Path('$ASSETS_DIR'),
)
print(f'[deploy] Static assets synced: {copied} copied, {skipped} identical skipped')
"

  TARGET_RELEASE="$RELEASES_DIR/$SHA"
  if [[ -d "$TARGET_RELEASE" ]]; then
    rm -rf "$TARGET_RELEASE"
  fi
  mv "$STAGING_DIR/$SHA" "$TARGET_RELEASE"
else
  TARGET_RELEASE="$RELEASES_DIR/$SHA"
fi

# Pick a previous asset to test backward compatibility after activation
PREVIOUS_ASSET_REL=""
if [[ -n "$PREVIOUS_TARGET" && -f "$MANIFESTS_DIR/$(basename "$PREVIOUS_TARGET").assets" ]]; then
  PREVIOUS_ASSET_REL=$(python3 -c "
import json
with open('$MANIFESTS_DIR/$(basename "$PREVIOUS_TARGET").assets') as f:
    data = json.load(f)
    print(next(iter(data.keys()), ''))
" 2>/dev/null || true)
fi

# ── 4. Atomic activation with automated rollback trap ────────────────────────
echo "[deploy] Activating release $SHA atomically..."

rollback_on_failure() {
  echo "::error::[deploy] ACTIVATION/VERIFICATION FAILED! Triggering automatic rollback..." >&2
  if [[ -n "$PREVIOUS_TARGET" && -d "$PREVIOUS_TARGET" ]]; then
    echo "[deploy] Rolling back current symlink to $PREVIOUS_TARGET..."
    python3 -c "
from pathlib import Path
from scripts.deploy.release_manager import atomic_rollback
atomic_rollback(Path('$PREVIOUS_TARGET'), Path('$CURRENT_LINK'))
"
    if command -v systemctl >/dev/null 2>&1; then
      echo "[deploy] Restarting bilun-frontend service on restored release..."
      systemctl restart bilun-frontend || true
    fi
    echo "[deploy] Verifying restored release on loopback..."
    python3 "$SCRIPT_DIR/verify_frontend_assets.py" "http://127.0.0.1:$PORT/login" || true
    echo "::error::[deploy] Rollback to $PREVIOUS_TARGET complete. Deployment failed." >&2
  else
    echo "::error::[deploy] No previous release available for rollback!" >&2
  fi
  exit 1
}

trap rollback_on_failure ERR

python3 -c "
from pathlib import Path
from scripts.deploy.release_manager import atomic_activate_release
atomic_activate_release(Path('$TARGET_RELEASE'), Path('$CURRENT_LINK'))
"

echo "[deploy] Restarting bilun-frontend service..."
if command -v systemctl >/dev/null 2>&1; then
  systemctl restart bilun-frontend
fi

# Give service a moment to bind
sleep 2

echo "[deploy] Verifying active release on loopback (http://127.0.0.1:$PORT/login)..."
python3 "$SCRIPT_DIR/verify_frontend_assets.py" "http://127.0.0.1:$PORT/login"

if [[ "$SKIP_PUBLIC" -eq 0 && -n "$PUBLIC_URL" ]]; then
  echo "[deploy] Verifying public endpoint ($PUBLIC_URL)..."
  python3 "$SCRIPT_DIR/verify_frontend_assets.py" "$PUBLIC_URL"
fi

if [[ -n "$PREVIOUS_ASSET_REL" ]]; then
  echo "[deploy] Verifying backward compatibility: testing previous asset $PREVIOUS_ASSET_REL..."
  PREV_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/_next/static/$PREVIOUS_ASSET_REL" || true)
  if [[ "$PREV_STATUS" != "200" ]]; then
    echo "[deploy] ERROR: Previous release asset returned HTTP $PREV_STATUS (expected 200)!" >&2
    false # Trigger ERR trap
  fi
  echo "[deploy] Backward compatibility verified: previous asset remains HTTP 200."
fi

# Clear error trap on success
trap - ERR

# ── 5. Retention pruning ─────────────────────────────────────────────────────
echo "[deploy] Pruning old releases..."
"$SCRIPT_DIR/prune_frontend_releases.sh" --base-dir "$BASE_DIR" --keep 3 || true

BUILD_ID=$(cat "$TARGET_RELEASE/.next/BUILD_ID" 2>/dev/null || echo "unknown")
echo "=== DEPLOYMENT SUCCESSFUL ==="
echo "Active SHA:      $SHA"
echo "Next BUILD_ID:   $BUILD_ID"
echo "Working link:    $(readlink -f "$CURRENT_LINK")"
echo "============================="
