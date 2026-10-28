# Release lanes

The strict paired-release lane was deleted on 2026-10-28 (Safa's decision); the git tag `archive/strict-lane` holds it (its scripts, tests, workflows, runbook and the signed Wave A activation receipt). Since then a build shows its Wave A evidence in every data mode when the evidence itself is complete (the index, schema and row-count checks in `src/bilun/api/routes/wavea_gate.py`); no receipt and no flag gates it.

## Staging

Staging is **synthetic data only**. Require `BILUN_DATA_MODE=synthetic_demo`; the application defaults to this mode and validates synthetic input paths and provenance. Existing generic `real_claims` configuration support is not a launch authorization. A real-claims launch path must be added deliberately and reviewed before use. The staging update is in [AI-RUNBOOK.md](AI-RUNBOOK.md) ("Staging: one operator command"); before a release that may move what the engine reports, see [release-same-bills-check.md](release-same-bills-check.md).

## Public URL currently served by staging

Since 2026-10-09 the Caddy site `app.bilun.tech` proxies to **staging** (`/api/*` and `/health` to `127.0.0.1:8101`, everything else to `127.0.0.1:3100`); the old frozen pair (`5c89ed53`, ports 8001/3000), the last release of the deleted strict lane, keeps running from its own bundle under `/root` but receives no traffic; retiring it is a later step. Switch with `/opt/bilun-staging/caddy-switch.sh to-staging|to-live|status`; every switch backs up the Caddyfile to `/root/caddy-backups`, validates it, only reloads Caddy and rolls back on a failed check. Consequences:

1. Staging updates restart the staging backend and frontend services; while public traffic points to staging this causes a few seconds of public downtime.
2. Developer sign-in on `app.bilun.tech` does not work while staging serves public traffic: staging has no developer identity by design.

## Source freshness

The SGK 2026/39 drug list takes effect on **2026-10-09** and is applied to the EK-4A history as of [PR #222](https://github.com/Safa675/Bilun/pull/222). Bounded clinical-source continuity is admitted through **2026-10-05** only; see `docs/gazette/clinical-source-authority.md`. This does not change rules or imply real-claims readiness.
