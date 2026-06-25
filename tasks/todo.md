## Task: Backend bug fix — Dalga 6 (HIGH cluster)

### Goal
`plans/billing/backend-bug-audit.md` raporundaki kalan HIGH bug'lar. 4 cluster halinde:
- **Cluster A (rate/distribution)**: B-H2 (as-of fallback), B-H3 (rate pollution), B-H4 (key format mismatch)
- **Cluster B (copay)**: B-H5 (total_copay_savings_try field name vs behavior)
- **Cluster C (cache lifecycle)**: B-H9 (failure threshold), B-H10 (half-built guard)
- **Cluster D (API contract)**: B-H15 (fabricated payload), B-H17 (provenance source)
- B-H14 (Decimal float serialization) — scope değer, belki Dalga 7

### Subtasks — Cluster A
- [ ] **B-H2** as-of fallback en eski fiyat döndürüyor → empty map / None (`catalog_membership.py:60-64`). `pricing/temporal.py` ile tutarlı (o None döndürüyor).
- [ ] **B-H3** `copay_rate_matches_catalog` EK-2C-1 dışı kodlarda True döndürüyor → aggregator kirleniyor (`catalog_join.py:74`, `aggregator.py:142-143`).
- [ ] **B-H4** `rate_distribution` key format uyumsuzluğu: `Decimal.normalize()` → "4E+1%" vs float → "40.0%" (`exactness.py:216` vs `aggregator.py:144`). Tek quantize format'a getir.

### Subtasks — Cluster B
- [ ] **B-H5** `total_copay_savings_try` field adı "total" ama sadece visit → `billing_actions.py:98` `or` fallback yanlış total kullanıyor. Field'ı true total yap veya fallback'i kaldır.

### Subtasks — Cluster C
- [ ] **B-H9** Expensive backfill 100% failure'da build COMPLETE → failure threshold ekle (`build_expensive.py`, `builder.py:360-432`).
- [ ] **B-H10** Expensive backfill aktif build'i önce siliyor sonra yazıyor → half-built guard / staging swap (`build_expensive.py:70-76,164-230`).

### Subtasks — Cluster D
- [ ] **B-H15** `get_bill_optimization` claim_dataset None'da fabricated bill-scoped payload → 503 (`optimization.py:265-286`).
- [ ] **B-H17** Provenance cohort summary'den okunuyor → patient/bill satırından oku (`provenance.py:28-38`).

### Out of scope
- B-H14 (Decimal float serialization) — mimari, ayrı değerlendir
- B-C1 (PII) — product kararı, ayrı task


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
