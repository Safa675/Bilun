# VPS Deployment Plan — BILUN product on app.bilun.tech

**Target:** fresh DigitalOcean droplet (Ubuntu 24.04 LTS), `app.bilun.tech` with
automatic HTTPS via Caddy. Marketing site stays on Vercel at `bilun.tech`.

> This is a **documented, repeatable** procedure. You run it yourself on the VPS
> (not me over SSH). The companion script `scripts/deploy/vps-bootstrap.sh`
> automates the idempotent setup steps. Re-run the whole thing on a new server
> when you migrate (coupon → permanent) — that's what makes moving easy.

---

## Architecture after deploy

```
bilun.tech          → Vercel (marketing site, unchanged)
app.bilun.tech      → VPS (165.245.243.183)
                        ├── :443  Caddy (TLS terminator + reverse proxy)
                        ├── :3000 Next.js (product frontend)
                        └── :8001 FastAPI (backend, 127.0.0.1 only)
```

Caddy terminates TLS and proxies:
- `app.bilun.tech/`          → `localhost:3000` (Next.js)
- `app.bilun.tech/api/*`     → `localhost:8001` (FastAPI)  ← belt-and-suspenders; Next.js also proxies /api
- `app.bilun.tech/api/auth/*`→ `localhost:8001` (login/logout)

The auth gate (built in the prior task) sits in front of everything: visitors
land on `/login` unless they have the session cookie.

---

## Prerequisites (do these first, ~15 min)

1. **DigitalOcean droplet:** Ubuntu 24.04 (LTS), 2 vCPU / 4 GB is enough.
   Note the public IP (`165.245.243.183`).

2. **DNS:** at your domain registrar / Vercel DNS, add an **A record**:
   - `app.bilun.tech` → `165.245.243.183` (A, not CNAME)
   - TTL: default is fine.
   - Wait for propagation (dig +short app.bilun.tech should return the IP).

3. **SSH hardening (do NOT skip on a public box):**
   ```bash
   # On your LOCAL machine — generate a key if you don't have one:
   ssh-keygen -t ed25519 -f ~/.ssh/bilun_vps
   # Copy it to the droplet (will ask for the DO root password once):
   ssh-copy-id -i ~/.ssh/bilun_vps.pub root@165.245.243.183
   # Then disable password login on the server (after confirming key login works):
   # edit /etc/ssh/sshd_config → PasswordAuthentication no, PermitRootLogin prohibit-password
   # systemctl restart sshd
   ```

4. **Generate auth credentials** (the product is gated; do this locally):
   ```bash
   cd ~/Documents/Bilun
   python scripts/generate_auth_env.py <your-username> "<your-password>"
   ```
   Copy the three output lines — you'll paste them into `.env` on the VPS.

5. **Get your LLM_API_KEY** (Alibaba Token Plan / OpenAI-compatible) — reuse the one from your local `.env`.

---

## Deployment (run on the VPS, ~20 min)

### Step 0 — SSH in
```bash
ssh -i ~/.ssh/bilun_vps root@165.245.243.183
```

### Step 1 — Bootstrap the server (one command)
This installs system deps, Node 22 LTS, Python 3.13, Caddy, and sets up the
firewall. It's idempotent (safe to re-run):
```bash
curl -fsSL https://raw.githubusercontent.com/Safa675/Bilun/main/scripts/deploy/vps-bootstrap.sh | bash
```
> If you'd rather not pipe to bash blindly, clone first and read it:
> `git clone https://github.com/Safa675/Bilun.git && cd Bilun && bash scripts/deploy/vps-bootstrap.sh`

After this: `ufw` allows only 22/80/443. Node + Python + Caddy are installed.

### Step 2 — Get the code + configure
```bash
cd /opt
git clone https://github.com/Safa675/Bilun.git
cd Bilun
cp .env.example .env
nano .env   # fill in real values:
            #   BILUN_AUTH_USERNAME / _PASSWORD / _SESSION_SECRET (from Step 4 above)
            #   LLM_API_KEY
            #   leave BACKEND_HOST=127.0.0.1
```

### Step 3 — Build + start the app under systemd (so it survives reboot)
```bash
cd /opt/Bilun
./start.sh   # first run: installs deps + builds cache; takes a few minutes
```
Confirm it works: from your laptop, `curl -k https://app.bilun.tech/api/auth/me`
should return `{"authenticated":false,...}` (TLS works, gate works).

Then set up systemd units so it auto-starts/restarts:
```bash
# (the bootstrap script writes these unit files; just enable them)
systemctl enable --now bilun-backend bilun-frontend
```

### Step 4 — Configure Caddy (HTTPS + reverse proxy)
The bootstrap script writes `/etc/caddy/Caddyfile`:
```
app.bilun.tech {
    encode gzip

    # Auth + general API → FastAPI (127.0.0.1:8001)
    handle_path /api/* {
        reverse_proxy 127.0.0.1:8001
    }

    # Everything else → Next.js (127.0.0.1:3000)
    reverse_proxy 127.0.0.1:3000
}
```
Reload Caddy — it auto-provisions the Let's Encrypt cert on first request:
```bash
systemctl reload caddy
```
Visit `https://app.bilun.tech` → you should see the login page over HTTPS.

### Step 5 — Update the marketing site (separate repo)
In the `bilun.tech` repo, add a "Launch app" button to the hero pointing at the
product:
```html
<a class="btn btn--primary" href="https://app.bilun.tech">Launch app</a>
```
Push → Vercel auto-deploys → button live on bilun.tech.

---

## Verification checklist
- [ ] `https://app.bilun.tech` shows the login page (no cert warning).
- [ ] Wrong password → "Invalid username or password".
- [ ] Correct password → logged in to the product workspace.
- [ ] `https://app.bilun.tech/api/patients` without cookie → 401 JSON.
- [ ] Logout button → returns to `/login`.
- [ ] `bilun.tech` marketing site unchanged + "Launch app" button works.
- [ ] Reboot the droplet → services come back (`systemctl status bilun-*`).

---

## Migrating to a new server later (the coupon→permanent move)
Because everything is in git + one `.env`, a move is:
1. New droplet → run Step 1 (bootstrap) → Step 2 (clone + copy old `.env`).
2. Update DNS: `app.bilun.tech` A-record → new IP.
3. Step 3 + Step 4 (systemd + Caddy) — Caddy re-issues the cert automatically.
4. Shut down the old droplet.

~15 minutes, no data migration, no downtime beyond DNS TTL. **You do NOT need
to start on the long-term server** — moving is cheap.

---

## Out of scope (separate tasks)
- CI auto-deploy-on-push (GitHub Action → SSH → pull → restart). Doable once
  the manual flow is proven.
- Backups: the `.cache/bilun.duckdb` rebuilds from git, so there's nothing to
  back up except `.env`. Keep `.env` in a password manager, not on the server.
- Real patient data compliance (KVKK) — only relevant when you load real data;
  the demo uses synthetic records.
- Monitoring/alerting (uptime checks) — `healthchecks.io` pinging
  `https://app.bilun.tech/health` is a good free start.
