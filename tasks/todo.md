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

---

## Task: Remove MEDULA rejection queue "İncele" column; deep-link fatura id to playbook section

### Goal
In the MEDULA red kuyruğu table, drop the "İncele" Eylem column. Make the Fatura (claim_id) cell a link that opens the patient billing page and scrolls to the MEDULA rejection playbook section for that claim (same deep-link the İncele button used).

### Verified facts
- Component: `frontend/src/components/tabs/sut/operations/MedulaRejectionQueueTab.tsx`.
- Action column header at `:257`, cell `:296-306`.
- Fatura cell is plain text `{row.claim_id}` at `:271`.
- Deep-link helper `buildSutPatientHref(patientId, { claimId, section: "medula-playbook" })` (`lib/constants.ts:105-113`) — already used by the İncele button.
- Patient page `app/patient/[id]/page.tsx:370-378` handles `section=medula-playbook` → scrolls to `#medula-playbook`.
- i18n keys `columns.action` and `actions.review` are used ONLY by this component (TR + EN). Safe to remove.

### Subtasks
- [ ] `MedulaRejectionQueueTab.tsx`: remove Action `<th>` and `<td>`; convert claim_id `<td>` into a styled `<Link>` with the deep-link
- [ ] `messages/tr/operations.ts` + `messages/en/operations.ts`: remove now-unused `columns.action` and `actions.review`
- [ ] Verify: tsc --noEmit clean; no remaining reference to removed keys

### Out of Scope
- Patient billing page / MedulaRejectionPlaybookSection logic (unchanged)
- Backend / API (unchanged)
- Other columns / table structure

### Review
Done. `MedulaRejectionQueueTab.tsx`: removed the 10th "Eylem/İncele" column (header + cell). The Fatura cell (`claim_id`) is now a `<Link>` to `buildSutPatientHref(patient_id, { claimId: claim_id, section: "medula-playbook" })` — same deep-link the old İncele button used, so clicking a bill id opens the patient billing page and scrolls to the MEDULA rejection playbook section for that claim. Table is now 9 cols (header/cell counts aligned). Removed orphaned i18n keys `columns.action` + `actions.review` from TR and EN.

Verified: `tsc --noEmit` exit 0; grep confirms no remaining `operations.queue.columns.action` / `operations.queue.actions.review` references. The `#medula-playbook` scroll target + `section=medula-playbook` handling on the patient page (`page.tsx:370-378`) was already in place and is reused unchanged.

---

## Task: Chatbot tool coverage — fix stale descriptions + expose 2 unreachable algorithms

### Goal
Make every chatbot tool description truthful about what it computes (Gap 1), and expose the two analyzers with no chat path at all (Gap 2): DRG episode costing and the rule-engine validator.

### Verified facts (do not re-litigate)
- `get_billing_report` runs ALL 17 Family-A analyzers via `compute_patient_billing_report`; description says "4". `audit_exposure_try` IS in the patient-scoped report (`report_totals.py:73`, serialized via `asdict` `billing.py:52`).
- `get_optimization_summary` emits `drug_discount_validation` (`aggregator.py:439`); description omits it.
- `metadata.py:47` `billing_algorithms` list is stale (only 4).
- DRG episode costing: NOT reachable — chat path calls outcome with `include_expensive=False` (`chat.py:405`). Fix = new tool calling outcome route with `include_expensive=True`, extract `drg_summary` (keys: n_episodes, total_drg_cost, mean_episode_cost, most_expensive_drg, episodes...). No single DRG shortcut fn exists.
- Rule-engine validator `validate_claim`: NOT reachable. POST route builds dict from `ClaimValidationRequest`. For a stored-claim tool, reconstruct from `get_patient_claim_detail` via adapter: remap material_name→name, material_code→code, unit_price_try→unit_price, billed_amount_try→billed_amount; derive procedure_code from first procedure line; build drug_context from header.primary_icd10 (prescriber_specialty unavailable → omit drug-indication sub-checks).

### Subtasks
- [ ] Fix descriptions: `get_billing_report` (17 surfaces incl audit exposure), `get_optimization_summary` (+drug discount), `metadata.py:47` billing_algorithms
- [ ] Add `get_drg_episode_cost` tool (schema + _TOOL_FUNCTION_MAP + executor)
- [ ] Add `validate_claim` tool (schema + map + executor + reconstruction adapter)
- [ ] Add 2 regression tests in `tests/unit/chatbot/test_tools.py`
- [ ] pytest green

### Out of Scope
- Splitting the 17 algorithms into granular tools (bundling is correct by design — cross-algo dedup)
- The officer+patient tool gate (Gap 3) — separate task
- PII/KVKK, user_role trust (separate)

### Review
Done. Gap 1 + Gap 2 fixed; the chatbot now has truthful tool descriptions and can reach every analyzer.

**Gap 1 — descriptions now match reality:**
- `get_billing_report`: was "4 algorithms" → now names all 17 billing analyzers incl. audit_exposure_try (which was already in the patient-scoped payload but never advertised).
- `get_optimization_summary`: now includes drug-discount validation (EK-4A) — was emitted but omitted from the description.
- `metadata.py:47` `billing_algorithms`: was 4 entries → now 17, matching `compute_patient_billing_report`.

**Gap 2 — two previously-unreachable analyzers exposed as new core tools:**
- `get_drg_episode_cost(patient_id)` — calls the outcome route with `include_expensive=True` and extracts the `drg_summary` block (total/mean DRG cost, episodes, package pricing, pricing_status). Falls back to an `unavailable_reason` marker when there is no DRG data.
- `validate_claim(patient_id, claim_id)` — validates a *stored* claim against bundling/exclusion/material rules via a reconstruction adapter (`_validate_stored_claim`) that remaps stored fields (`material_name→name`, `material_code→code`, `unit_price_try→unit_price`, `billed_amount_try→billed_amount`), derives `procedure_code` from the first procedure line, and serializes the result via the same field mapping as the public `/validate-claim` route. Drug-indication sub-checks are skipped (prescriber_specialty not in stored data) — documented in the tool description.

**Wiring:** both added to `_TOOL_FUNCTION_MAP`, the `_exec` namespace, and `_CORE_TOOL_SCHEMAS` (available to both roles). Officer tool count 11→13; map 13→15.

**Verified:** `pytest tests/unit/chatbot/` → 61 passed (9 pre-existing tool tests + 5 new: schema-exposure check, DRG happy-path, DRG unavailable-path, validate_claim field-remap, validate_claim missing-arg rejection). Smoke-tested imports + map integrity + billing_algorithms=17. No tests asserted the old stale description strings, so the rewording is safe. (Note: a pre-existing, unrelated `_read_active_gazette_version` type-error in the local gazette manifest was observed but NOT touched — it is out of scope and environment-dependent.)

**Out of scope (separate tasks):** the officer+patient tool gate (Gap 3), PII/KVKK, client-trusted user_role, splitting the 17 algorithms into granular tools (bundling is correct by design due to cross-algo dedup).
