#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# migrate_vps_frontend.sh
#
# Idempotent migration of the production VPS from in-place Next.js
# to atomic releases under /opt/bilun-frontend.
#
# What it does:
# 1. Creates /opt/bilun-frontend filesystem layout
# 2. Links shared environment: /opt/bilun-frontend/shared/frontend.env -> /opt/Bilun/.env
# 3. Assembles or builds the initial release from current HEAD
# 4. Atomically links /opt/bilun-frontend/current to the release
# 5. Syncs static assets to /opt/bilun-frontend/assets/_next/static
# 6. Updates Caddyfile with /_next/static/ file_server route and validates
# 7. Updates bilun-frontend.service to run node server.js from current
# 8. Reloads systemd & Caddy, restarts bilun-frontend, and verifies all assets
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${BILUN_REPO_DIR:-/opt/Bilun}"
BASE_DIR="${BILUN_FRONTEND_BASE:-/opt/bilun-frontend}"
DOMAIN="${BILUN_DOMAIN:-app.bilun.tech}"

if [[ $EUID -ne 0 ]]; then
  echo "Error: Must run as root (sudo bash $0)" >&2
  exit 1
fi

LOG() { printf '\033[0;32m[migrate]\033[0m %s\n' "$*"; }
WARN() { printf '\033[0;33m[migrate]\033[0m %s\n' "$*" >&2; }

LOG "Initializing /opt/bilun-frontend layout..."
mkdir -p "$BASE_DIR"/{builds,releases,staging,manifests,shared,assets/_next/static}

# 1. Shared environment file
if [[ -f "$REPO_DIR/.env" ]]; then
  ln -sfn "$REPO_DIR/.env" "$BASE_DIR/shared/frontend.env"
  LOG "Linked shared/frontend.env -> $REPO_DIR/.env"
else
  WARN "Notice: $REPO_DIR/.env not found; ensure $BASE_DIR/shared/frontend.env is created."
fi

# 2. Get current commit SHA
CURRENT_SHA=$(git -C "$REPO_DIR" rev-parse HEAD)
LOG "Target commit SHA: $CURRENT_SHA"

# 3. Build/assemble initial release
RELEASE_DIR="$BASE_DIR/releases/$CURRENT_SHA"
if [[ ! -d "$RELEASE_DIR" ]]; then
  LOG "Building initial release for $CURRENT_SHA..."
  # If repo already has standalone built, we can assemble directly, else run full build
  if [[ -f "$REPO_DIR/frontend/.next/standalone/frontend/server.js" ]]; then
    LOG "Using existing standalone build in $REPO_DIR/frontend..."
    python3 -c "
from pathlib import Path
from scripts.deploy.release_manager import assemble_release_payload, build_asset_manifest
import json

staging = Path('$BASE_DIR/staging/$CURRENT_SHA')
assemble_release_payload(Path('$REPO_DIR/frontend'), staging, '$CURRENT_SHA', 'migration')
manifest = build_asset_manifest(staging)
with open('$BASE_DIR/manifests/$CURRENT_SHA.assets', 'w') as f:
    json.dump(manifest, f, indent=2)
"
    mv "$BASE_DIR/staging/$CURRENT_SHA" "$RELEASE_DIR"
  else
    LOG "Building release via build_frontend_release.sh..."
    "$SCRIPT_DIR/build_frontend_release.sh" --sha "$CURRENT_SHA" --repo-dir "$REPO_DIR" --base-dir "$BASE_DIR"
    if [[ -d "$BASE_DIR/staging/$CURRENT_SHA" ]]; then
      mv "$BASE_DIR/staging/$CURRENT_SHA" "$RELEASE_DIR"
    fi
  fi
fi

# 4. Sync static assets to shared store
LOG "Syncing static assets to $BASE_DIR/assets/_next/static..."
python3 -c "
from pathlib import Path
from scripts.deploy.release_manager import sync_shared_assets

sync_shared_assets(Path('$RELEASE_DIR'), Path('$BASE_DIR/assets/_next/static'))
"

# 5. Atomic symlink activation
LOG "Activating release via $BASE_DIR/current..."
python3 -c "
from pathlib import Path
from scripts.deploy.release_manager import atomic_activate_release

atomic_activate_release(Path('$RELEASE_DIR'), Path('$BASE_DIR/current'))
"

# 6. Update Caddyfile with shared asset route
LOG "Updating /etc/caddy/Caddyfile..."
cat > /etc/caddy/Caddyfile <<EOF
$DOMAIN {
    encode gzip

    # Auth + general API → FastAPI (loopback only)
    handle_path /api/* {
        reverse_proxy 127.0.0.1:8001
    }

    # Retained static assets across releases
    handle_path /_next/static/* {
        root * $BASE_DIR/assets/_next/static
        file_server
    }

    # Everything else → Next.js frontend (standalone)
    reverse_proxy 127.0.0.1:3000
}
EOF

if command -v caddy >/dev/null 2>&1; then
  LOG "Validating Caddyfile..."
  caddy validate --config /etc/caddy/Caddyfile
  systemctl reload caddy || systemctl restart caddy
  LOG "Caddy reloaded successfully."
fi

# 7. Update systemd service unit
LOG "Updating /etc/systemd/system/bilun-frontend.service..."
cat > /etc/systemd/system/bilun-frontend.service <<EOF
[Unit]
Description=BILUN Next.js frontend (standalone release)
After=network.target bilun-backend.service

[Service]
Type=simple
WorkingDirectory=$BASE_DIR/current
Environment=NODE_ENV=production
Environment=HOSTNAME=127.0.0.1
Environment=PORT=3000
EnvironmentFile=$BASE_DIR/shared/frontend.env
ExecStart=/usr/bin/node $BASE_DIR/current/server.js
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
LOG "Restarting bilun-frontend service under standalone layout..."
systemctl restart bilun-frontend

sleep 3

# 8. Post-migration verification
LOG "Verifying loopback service (http://127.0.0.1:3000/login)..."
python3 "$SCRIPT_DIR/verify_frontend_assets.py" "http://127.0.0.1:3000/login"

LOG "Verifying public service (https://$DOMAIN/login)..."
python3 "$SCRIPT_DIR/verify_frontend_assets.py" "https://$DOMAIN/login" || WARN "Public verification had warnings (e.g. if DNS/TLS local resolution differs)"

LOG "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
LOG "Migration complete! Frontend is now running from $BASE_DIR/current"
LOG "Active commit: $CURRENT_SHA"
LOG "Next BUILD_ID: $(cat "$RELEASE_DIR/.next/BUILD_ID" 2>/dev/null || echo 'unknown')"
LOG "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
