#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# BILUN VPS bootstrap — idempotent server setup for app.bilun.tech
#
# Run as root on a fresh Ubuntu 24.04 droplet:
#   curl -fsSL https://raw.githubusercontent.com/Safa675/Bilun/main/scripts/deploy/vps-bootstrap.sh | bash
# Or after cloning:
#   bash scripts/deploy/vps-bootstrap.sh
#
# What it does (all idempotent — safe to re-run):
#   1. Installs system deps (build tools, curl, git, ufw)
#   2. Installs Node.js 22 LTS (for the Next.js frontend)
#   3. Installs Python 3.13 (the app requires >=3.13)
#   4. Installs Caddy (auto-HTTPS reverse proxy)
#   5. Configures the firewall (ufw: allow 22/80/443 only)
#   6. Writes the Caddyfile (reverse proxy app.bilun.tech → :3000 + :8001)
#   7. Writes systemd units for bilun-backend + bilun-frontend
#
# What it does NOT do (you do these manually, see plans/deployment/vps-deploy-plan.md):
#   - Clone the repo / fill .env  (Step 2 of the plan — has your secrets)
#   - systemctl enable --now      (Step 3 — only after .env is filled)
#   - DNS A-record for app.bilun.tech  (prerequisite — Caddy needs it for the cert)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DOMAIN="${BILUN_DOMAIN:-app.bilun.tech}"
APP_DIR="${BILUN_APP_DIR:-/opt/Bilun}"
LOG() { printf '\033[0;32m[bootstrap]\033[0m %s\n' "$*"; }
WARN() { printf '\033[0;33m[bootstrap]\033[0m %s\n' "$*" >&2; }

if [[ $EUID -ne 0 ]]; then
  WARN "Must run as root (try: sudo bash $0)"
  exit 1
fi

# ── 1. System deps ───────────────────────────────────────────────────────────
export DEBIAN_FRONTEND=noninteractive
LOG "Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
  curl git build-essential unzip ufw ca-certificates gnupg \
  libssl-dev libffi-dev 2>/dev/null

# ── 2. Node.js 22 LTS ────────────────────────────────────────────────────────
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v 2>/dev/null | cut -d. -f1 | tr -d v)" -lt 22 ]]; then
  LOG "Installing Node.js 22 LTS..."
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y -qq nodejs 2>/dev/null
fi
LOG "Node: $(node -v)  npm: $(npm -v)"

# ── 3. Python 3.13 (the app requires >=3.13) ─────────────────────────────────
if ! command -v python3.13 >/dev/null 2>&1; then
  LOG "Installing Python 3.13..."
  apt-get install -y -qq software-properties-common 2>/dev/null
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update -qq
  apt-get install -y -qq python3.13 python3.13-venv python3.13-dev 2>/dev/null
fi
LOG "Python: $(python3.13 --version)"

# ── 4. Caddy (auto-HTTPS reverse proxy) ──────────────────────────────────────
if ! command -v caddy >/dev/null 2>&1; then
  LOG "Installing Caddy..."
  apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https 2>/dev/null
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  apt-get update -qq
  apt-get install -y -qq caddy 2>/dev/null
fi
LOG "Caddy: $(caddy version | head -1)"

# ── 5. Firewall (ufw: allow SSH, HTTP, HTTPS only) ───────────────────────────
LOG "Configuring firewall (ufw)..."
ufw --force reset >/dev/null
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
# NOTE: 3000 and 8001 are intentionally NOT opened — Caddy proxies to them
# over loopback only, so the product is reachable solely via app.bilun.tech.
ufw --force enable >/dev/null
LOG "ufw active. Only 22/80/443 are exposed."

# ── 6. Caddyfile ─────────────────────────────────────────────────────────────
LOG "Writing /etc/caddy/Caddyfile (domain: $DOMAIN)..."
cat > /etc/caddy/Caddyfile <<EOF
$DOMAIN {
    encode gzip

    # Auth + general API → FastAPI (loopback only).
    # This is belt-and-suspenders: Next.js already proxies /api → :8001, but
    # routing /api/* directly to the backend here avoids a double-hop and keeps
    # the backend reachable through Caddy even if the frontend is restarting.
    handle_path /api/* {
        reverse_proxy 127.0.0.1:8001
    }

    # Everything else → Next.js frontend.
    reverse_proxy 127.0.0.1:3000
}
EOF
systemctl enable caddy >/dev/null 2>&1 || true
# Reload (not restart) so an existing cert isn't disturbed; Caddy provisions
# the cert automatically on first request once DNS resolves.
systemctl reload caddy 2>/dev/null || systemctl restart caddy

# ── 7. systemd units for the app ─────────────────────────────────────────────
# These run the app as root for simplicity on a single-tenant demo box. For a
# multi-tenant/hardened deploy, run as a dedicated unprivileged user.
LOG "Writing systemd units (bilun-backend, bilun-frontend)..."

cat > /etc/systemd/system/bilun-backend.service <<EOF
[Unit]
Description=BILUN FastAPI backend
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python -m uvicorn src.bilun.api:app --host 127.0.0.1 --port 8001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/bilun-frontend.service <<EOF
[Unit]
Description=BILUN Next.js frontend
After=network.target bilun-backend.service

[Service]
Type=simple
WorkingDirectory=$APP_DIR/frontend
Environment=NODE_ENV=production
# The Next.js middleware (frontend/src/middleware.ts) needs BILUN_SESSION_SECRET
# to verify session tokens. Without this, it treats auth as "not configured"
# and lets everyone through — disagreeing with the backend, which enforces auth.
EnvironmentFile=$APP_DIR/.env
ExecStart=$(command -v npx || echo /usr/bin/npx) next start -p 3000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
# NOTE: not enabled here — you enable after cloning + filling .env + first build.

LOG ""
LOG "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
LOG "Bootstrap complete. Next steps (see plans/deployment/vps-deploy-plan.md):"
LOG "  1. cd /opt && git clone https://github.com/Safa675/Bilun.git"
LOG "  2. cd /opt/Bilun && cp .env.example .env && nano .env  (fill secrets)"
LOG "  3. ./start.sh   (first build: installs deps + warms cache)"
LOG "  4. systemctl enable --now bilun-backend bilun-frontend"
LOG "  5. Add DNS A-record: $DOMAIN → this server's IP (if not done)"
LOG "  6. systemctl reload caddy   (provisions the TLS cert)"
LOG "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
