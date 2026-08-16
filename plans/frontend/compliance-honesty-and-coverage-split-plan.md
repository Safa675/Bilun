# Plan: Compliance honesty, coverage split, Red Kuyruğu polish

**Date:** 2026-08-16
**Status:** Ready for review
**Supersedes:** `plans/compliance_tab_full_taxonomy_redesign_plan.md` (8-pillar demo shell)
**Target:**
- `frontend/src/components/tabs/sut/compliance/`
- `frontend/src/components/tabs/sut/sections/RuleDatabaseSection.tsx`
- `frontend/src/components/tabs/sut/operations/MedulaRejectionQueueTab.tsx`
- `frontend/src/lib/workspaceSubtabs.ts`
- `src/bilun/api/routes/` (P1 only)
- `src/bilun/domain/billing/` (P1 only)

---

## 1. Problem

Three product surfaces currently lie, dump, or look unfinished:

1. **Uyumluluk** advertises “8 Boyutlu Denetim Aktif” with fake KPIs (`%98,4`, `₺121.714,71`) and six `DEMO_*` modules. Only exemptions and surcharge are live. Backend already has 29 rule families; patient billing already emits `finding_type: "compliance"` for materials, drug indication, lab, and mandatory payment-method rows. None of that reaches `/?tab=compliance`.
2. **Kural Veritabanı** mounts the live coverage dump (`CoverageSummaryPanel`: top-gap categories, honesty composition, five partial-engine cards, §4.2 %) **above every browse tab**, then a June 2026 archive banner. That is why the tab feels endless, and why “Haziran 2026 — arşiv” looks like a stale dashboard.
3. **Red Kuyruğu** is a real queue over ~10 synthetic MEDULA events, but leftover “reaktif acil ayıklama” copy, unused imports, broken filter pagination, a client-only `matched_only` filter, and a Compliance MEDULA subtab that invents different error codes (`1001/1054/…` vs queue `1688/0612`).

Finishing the 8-pillar taxonomy plan would make this worse: more demo tables pretending to be cohort risk.

---

## 2. Design decision (the elegant path)

**The home Compliance tab is a cohort rollup of findings the product already computes.** It is not a second taxonomy of hardcoded playbooks.

| Do | Do not |
|---|---|
| Show a subtab only when a live API/cache surface exists | Keep DEMO arrays behind a “coming soon” chip |
| Reuse `collect_billing_actions` + `finding_type` + existing alerts | Re-run motors in the frontend or invent a parallel rule catalog |
| Header KPIs = live counts / billed-at-risk | Invent a “%98,4 uyum” score with no definition |
| One MEDULA queue (Red Kuyruğu) | Duplicate playbook with fake codes on Compliance |
| Coverage honesty on its own Rule Database subtab | Keep the dump above Kurallar / Hükümler / … |

Patient-workspace routing stays the source of truth (`workspaceViews.ts` / `billing_actions.py`):

- Compliance findings: `materials`, `drug_indication`, `lab`, `billing_strategy` where kind is `mandatory_compliance` / `compliance_violation`
- Already-live alerts (separate table): `exemptions`, `surcharge`, `copay_rates`
- Not Compliance: `session_uplift` (revenue), `claim_checklist` (audit), `medula_playbook` (informational + operations queue)

`surgical_sessions` and `pre_flight_docs` have **no live compliance surface**. They come off the strip until a later product decision reclassifies those findings.

---

## 3. Target IA

### 3.1 Uyumluluk (`/?tab=compliance`)

**After P0 (honest empty shell):**

```
exemptions | surcharge
```

Header: cohort filter only. No fake radar, no hardcoded badges.

**After P1 (live rollup):**

```
exemptions | surcharge | copay_rates | materials | drug_indication | lab | payment_methods
```

Optional compact chip (not a subtab): live Red Kuyruğu count → `/?tab=operations`.

Header Stats (from live data, `Stat` primitive, no Tailwind rainbow):

- Findings (count)
- Patients with ≥1 finding
- Billed at risk (₺) from compliance actions
- Open MEDULA rejections (from queue `total`, or “—” if ingest off)

Badge counts on the strip = live per-subtab counts. Zero means hide the badge, not invent a number.

### 3.2 Kural Veritabanı (`/?tab=reference-tools` Rule Database)

```
Kapsam | Kurallar | Bölümler | Hükümler | Düz metin | Ertelenenler
```

- Default `rdTab=coverage` (experts land on honesty, not a dump above browse).
- **Kapsam** owns: `CoverageSummaryPanel` (pipeline + top gaps + composition + partial engines) and, collapsed at the bottom, `FactCheckRollupBanner` labeled arşiv.
- Browse tabs have **no** coverage wall. Optional one-line meta in the section description is enough (`{n} kural motoru` already exists).
- Do not reopen the June fact-check program. Do not change `AUDIT_CLOSED = "2026-06"`.

### 3.3 Red Kuyruğu

Keep as the only MEDULA operations surface. Polish; do not redesign into a second Compliance tab.

---

## 4. Phases

Ship as **two PRs**. P0 is frontend-only and does not need a cache rebuild. P1 needs backend + cache (reports already contain `recommended_actions`).

---

### Phase 0 — Stop lying (frontend)

**Goal:** Nothing on Compliance, Rule Database, or Red Kuyruğu claims data it does not have.

#### P0.1 Compliance strip and dashboard

- `COMPLIANCE_SUB_IDS` shrinks to `exemptions` | `surcharge` until P1.
- Delete the radar `Surface` in `SUTComplianceDashboard.tsx` (title “SUT Mevzuat ve Fatura Uyumluluk Merkezi”, chip “8 Boyutlu Denetim Aktif”, `%98,4`, four hardcoded KPI tiles, hardcoded `badgeCounts`).
- Unknown `?compTab=` values (materials, medula_rejections, …) fall back to `exemptions` without rendering demo modules.
- Remove unused `DEMO_*` modules from the dashboard switch. Delete the demo data arrays (do not leave them as unused exports).
- Restyle remaining modules with Bilun primitives (`Surface`, `Stat`, `Chip`, `DataTable`). No `text-emerald-400` / `text-rose-400` / undefined `--text-tertiary`. No “MEDULA Otomasyon Durumu” filler cards that do not read an API.
- i18n: drop keys that only existed for the 8-pillar marketing copy; keep exemption/surcharge labels.

**Delete (do not keep as stubs):**

- `modules/MaterialsCompliance.tsx` DEMO array (rewritten in P1)
- `PaymentMethodCompliance.tsx`, `SurgicalSessionCompliance.tsx`, `DiagnosticLabCompliance.tsx`, `PreFlightDocsCompliance.tsx`, `MedulaPlaybookCompliance.tsx`

If a file is easier to rewrite in P1 than delete-and-restore, empty it of `DEMO_*` and stop exporting it from the dashboard in P0. No demo rows in the shipped tree.

#### P0.2 Rule Database coverage subtab

- Add `coverage` to `RuleDatabaseSubSection` / `RULE_DATABASE_SUB_IDS` (first).
- Move `CoverageSummaryPanel` from above `TabsRoot` into `TabsContent value="coverage"`.
- Move `FactCheckRollupBanner` into the same tab, **collapsed by default**, still titled “Algoritma denetimi (Haziran 2026 — arşiv)”. Subtitle stays: frozen snapshot, live coverage is the panel above it (now in the same tab, not a different clock on browse views).
- Default `rdTab` when missing: `coverage`.
- i18n: `sections.ruleDatabase.tabs.coverage` = “Kapsam” / “Coverage”.
- Tests: `workspaceSubtabs` + any Rule Database section tests that assumed the panel is always mounted.

#### P0.3 Red Kuyruğu polish

- Delete unused `operations.queue.subtitle` (“reaktif acil ayıklama…”) from tr/en. Remove unused `Eyebrow` import.
- EN nav: `homeTabs.operations.label` → “Rejection Queue” (TR stays “Red Kuyruğu”). Align chat `defaultPrompts.operations` to “red kuyruğu”, not “fatura operasyonları”.
- Filter `onChange` calls `setPage(1)` (do not stuff `page` into filter state).
- Add API query `playbook_matched` (bool) next to existing `rebill_permitted`; wire the checkbox to the server. Stop client-filtering the current page.
- Stage / sonuç kodu: `<select>` from distinct values on the current result set, or a `facets` object on the queue response (`sonuc_kodu[]`, `medula_stage[]`). No English snake placeholders in the TR UI.
- KPI row from the response: `total`, matched count (if facets), rebill-permitted count. Use `Stat`. Loading: table skeleton, not a blank main.
- Show `corrective_steps_tr` in an expand/drawer on the row — do not add a ninth always-on column of paragraphs.
- Tokens: replace raw `text-slate-950` links with existing link/button classes.

**P0 definition of done**

- Opening `/?tab=compliance` shows only live exemption + surcharge tables; no ₺121k, no %98,4, no demo patients.
- Opening Rule Database lands on Kapsam; Kurallar is a browse list without the honesty wall.
- Changing a Red Kuyruğu filter resets to page 1 and `matched_only` changes `total`.
- `npx tsc --noEmit` + vitest for touched FE files green.
- No cache rebuild.

---

### Phase 1 — Wire live families (backend + FE)

**Goal:** Compliance subtabs that already have engines show **this cohort’s** rows, from cache, same taxonomy as the patient workspace.

#### P1.1 Cohort compliance index (cache-time, not request-time scan)

Cached `patient_billing_report_rows` already store full reports with `recommended_actions`. Do **not** JSON-scan every patient on each Compliance page load.

At cache build (same pass that writes billing reports), write `cohort_compliance_index`:

```
{
  n_patients,
  n_findings,
  n_patients_with_findings,
  billed_at_risk_try,
  by_surface: { materials, drug_indication, lab, payment_methods: { n, billed_try } },
  rows: [{
    patient_id, claim_id, surface, kind, finding_type,
    billed_try, detail, procedure_code, material_code, drug_code,
    sut_section_id, action_id
  }]
}
```

Row filter: `finding_type == "compliance"`. Map `billing_strategy` → subtab `payment_methods`. Copay exemption **rows** from billing actions may duplicate the alerts table — **do not** put them in this index; exemptions stay on `/patient-alerts`.

Implementation sketch:

- `src/bilun/domain/billing/cohort_compliance.py` — Polars/`list` flatten from in-memory reports (already in `builder` ctx). No Python row loop over a dataframe; reports are dicts, one pass.
- DuckDB table `cohort_compliance_index` (single JSON payload, same pattern as `cohort_recovery_summary`).
- `GET /api/compliance-index?surface=&limit=&offset=` (+ optional patient-id filter for the cohort bar).
- Tests: fixture report with mixed finding types → only compliance rows; payment optional_override excluded; materials kinds preserved.

Cache rebuild required after this lands (`BILUN_STARTUP_POLICY=rebuild`). Old caches return 503/empty with `artifacts_available: false`, not zeros.

#### P1.2 Alerts: add `copay_rates` subtab

`GET /patient-alerts?category=copay_rates` already exists. Clone the exemptions/surcharge module pattern. No new backend.

#### P1.3 Compliance modules from the index

One shared table primitive (patient, claim, code/name, kind, ₺, SUT §, link via `buildSutBillingHref` + `?section=`):

| Subtab | `surface` / source | Patient workspace section |
|---|---|---|
| materials | `materials` | `materials-pre-check` |
| drug_indication | `drug_indication` | `drug-indication` |
| lab | `lab` | `billing-lab` |
| payment_methods | `billing_strategy` compliance kinds | `billing-strategy` |

Dashboard header Stats and strip badges read the index summary (and alerts summaries for exemptions/surcharge/copay_rates). Cohort filter intersects `patient_id`.

#### P1.4 MEDULA on Compliance

No playbook module. If a count is useful, one `Chip`/`Stat` linking to `/?tab=operations` using `GET /api/medula-rejections/queue?page_size=1` `total` (or ingest-status + total). Same codes as Red Kuyruğu.

**P1 definition of done**

- Every Compliance subtab row is traceable to a cached billing action or a patient-alert row.
- Header numbers change when the cohort filter changes.
- A patient with a material pre-auth finding appears on Compliance → materials and deep-links to the same section as the patient workspace.
- İlaç endikasyon is visible on the home tab.
- `pytest` for the new index + FE vitest + `tsc` green.
- Cache rebuilt once; `/health` shows the new build.

---

### Phase 2 — Later (explicitly out of this plan’s implementation)

Only if product asks after P0+P1:

- Promote `claim_checklist` / surgical session rules into compliance (today they are audit / revenue).
- Encode remaining gap families so they *produce* findings (that is Rule Database / encoder work, not this UI).
- Live MEDULA SOAP ingest.
- Re-run the 28-unit algorithm fact-check.

---

## 5. UI contract (Bilun design system)

From `tasks/lessons.md` 2026-08-16:

- Primitives only: `Surface`, `Eyebrow`, `Stat`, `DataTable`, `Chip`, `Button`.
- No marketing subtitles, no “360 derece kohort denetimi” banners, no decorative status cards.
- Status color ≠ brand gold. No `text-emerald-400` / `text-rose-400` on KPIs.
- Tables and filters should be self-explanatory; if a sentence is needed, it is an empty state, not a header essay.

---

## 6. Test plan

**P0**

- [ ] `/?tab=compliance` — 2 subtabs, live alerts, no demo names (`SENTETIK-HASTA` only if they are real alert rows).
- [ ] Direct URL `?compTab=materials` → exemptions fallback, no demo table.
- [ ] Rule Database default = Kapsam; switching to Kurallar hides gap cards.
- [ ] Fact-check block collapsed; title still contains “arşiv”.
- [ ] Red Kuyruğu: filter change → page 1; matched-only → `total` updates; EN label; no subtitle in DOM.
- [ ] vitest + `tsc --noEmit`.

**P1**

- [ ] Index unit test: mixed `finding_type` fixture.
- [ ] After cache rebuild, Compliance materials/lab/indication/payment show the same patients as opening those workspace sections.
- [ ] Cohort filter reduces header counts.
- [ ] Empty cohort / no ingest → honest empty, not 0 disguised as health.
- [ ] pytest + vitest + tsc.

---

## 7. Out of scope

- Encoding new SUT clauses / changing `coverage_status`.
- Changing `has_algorithmic_gap` semantics.
- Live re-audit of June 2026 fact-check units.
- Revenue Dashboard changes.
- Patient workspace three-engine IA (already separate).
- Real MEDULA submission / rebill.
- Keeping the 8-pillar demo modules as placeholders.

---

## 8. Suggested PR split

| PR | Contents | Rebuild? |
|---|---|---|
| A | P0.1 + P0.2 + P0.3 | No |
| B | P1.1–P1.4 | Yes |
