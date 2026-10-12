# Release lanes

The strict paired-release lane is **PAUSED** by Safa's decision while the product uses synthetic data and no real-money workflow. Keep its code, pins and existing runbook unchanged: the application imports deploy modules during startup and activation.

Strict scope: `scripts/deploy/*`, `docs/operations/single-vps-wavea-release.md`, `tests/unit/deploy` and `tests/integration/deploy`. Audit results do not reopen the lane or authorize deployment.

## Fast lane

The fast lane is **staging only, synthetic data only**. Require `BILUN_DATA_MODE=synthetic_demo`; the application defaults to this mode and validates synthetic input paths and provenance. Existing generic `real_claims` configuration support is not a launch authorization. A real-claims launch path must be added deliberately and reviewed before use.

Default pytest and CI exclude `strict_release` through the collection hook when no `-m` expression is given and `BILUN_STRICT_RELEASE` is not `1`; `scripts/ci_local.sh` explicitly selects `-m "not strict_release"`. Product imports of deploy modules remain tested. The separate Strict Release workflow audits only `-m strict_release` on the laptop runner. Strict failures may document drift while paused; do not fix them or treat them as a fast-lane merge gate.

## Public URL currently served by staging

Since 2026-10-09 the Caddy site `app.bilun.tech` proxies to **staging** (`/api/*` and `/health` to `127.0.0.1:8101`, everything else to `127.0.0.1:3100`); the strict lane's live pair (`5c89ed53`, ports 8001/3000) keeps running but receives no traffic. Switch with `/opt/bilun-staging/caddy-switch.sh to-staging|to-live|status`; every switch backs up the Caddyfile to `/root/caddy-backups`, validates it, only reloads Caddy and rolls back on a failed check. Consequences:

1. While public traffic points to staging, `/etc/caddy/Caddyfile` differs from the strict release lane's exact `OLD_CADDYFILE`.
2. Before reopening the strict release lane, run `/opt/bilun-staging/caddy-switch.sh to-live` and verify that the reviewed live Caddyfile and the live health checks are restored.
3. Staging updates restart the staging backend and frontend services; while public traffic points to staging this causes a few seconds of public downtime.
4. Developer sign-in on `app.bilun.tech` does not work while staging serves public traffic: staging has no developer identity by design.

## Reopen trigger and checklist

Reopen **before any non-synthetic data, real claims or real money reaches the product**. Safa must explicitly confirm that this trigger has happened before agents start strict-lane work.

Based on `~/work/bilun-deploy-plan/DEPLOY-PLAN.md` (2026-10-08):

1. **Run the strict-release workflow and refresh drifted pins.** Then freeze the candidate SHA and green main/push CI after UI/dependency work.
2. Extract only the needed measurement tools and negative tests from #186; they do not grant acceptance authority.
3. In separately approved private staging, measure the live-to-old cache bridge and two independent productions of all 19 tables. Resolve historical source/config gaps, WAL/locks and every unexplained difference.
4. Review a narrow acceptance profile: exact SHA/tree, inputs, source/config/runtime/dependency identities, producer ASTs, manifests/receipts and allowed differences. Reject unknown drift; preserve amounts, counts, findings, identities, order and adjacent fields. No generic text/null/build-ID exemptions.
5. Connect that profile to prepare, semantic/HTTP/rehearsal and signing checks; retain prior profiles.
6. Refresh final-main CI, pins and measurements, then separately authorize paired-release prepare using `online-read-lock`. Maintenance or downtime requires explicit approval.
7. Review `prepared.json`/status, actual backend/frontend HTTP/UI results, old-interpreter identity and rollback proof; present the concrete candidate for activation approval.
8. Separately authorize activation and automatic rollback to the old pair, then verify status/the live pair and retain the journal/bundle.

## Source freshness

The SGK 2026/39 drug list takes effect on **2026-10-09** and is applied to the EK-4A history as of [PR #222](https://github.com/Safa675/Bilun/pull/222). Bounded clinical-source continuity is admitted through **2026-10-05** only; see `docs/gazette/clinical-source-authority.md`. This pause does not change rules or imply real-claims readiness.
