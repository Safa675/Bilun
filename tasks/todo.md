## Task: Deploy BILUN to VPS (app.bilun.tech)

### Goal
Deploy the Bilun product to the DigitalOcean VPS at 165.245.243.183, accessible
at https://app.bilun.tech with auto-HTTPS via Caddy.

### Subtasks

#### Prerequisites
- [ ] Set DNS A record: `app.bilun.tech` → `165.245.243.183` via Vercel DNS
- [ ] Generate auth credentials locally (username=bilun_admin, password=12345)
- [ ] Commit and push deploy scripts + plans to GitHub (they're untracked)

#### Server Setup (Step 1 — Bootstrap)
- [ ] Run vps-bootstrap.sh on VPS (installs Node 22, Python 3.13, Caddy, ufw)
- [ ] Verify: Node, Python, Caddy installed; ufw allows 22/80/443 only

#### App Deployment (Steps 2–3)
- [ ] Clone repo to /opt/Bilun on VPS
- [ ] Create .env on VPS with auth creds + LLM_API_KEY
- [ ] Run start.sh to build (install deps, warm cache)
- [ ] Enable systemd services: bilun-backend + bilun-frontend

#### HTTPS + Reverse Proxy (Step 4)
- [ ] Verify Caddyfile is correct
- [ ] Reload Caddy to provision TLS cert
- [ ] Verify https://app.bilun.tech shows login page

#### Verification
- [ ] HTTPS works (no cert warnings)
- [ ] Login works with correct password
- [ ] Wrong password returns error
- [ ] /api endpoints return 401 without session
- [ ] Services survive reboot (systemctl status)

### Out of Scope
- CI auto-deploy (GitHub Actions)
- Marketing site "Launch app" button update
- Real patient data compliance (KVKK)
- Monitoring/alerting
