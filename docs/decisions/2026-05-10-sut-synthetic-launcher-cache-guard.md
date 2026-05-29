---
title: "SUT Synthetic Launcher Cache Guard"
aliases: ["sut-synthetic-cache-guard", "sut-launcher-synthetic-demo-cache"]
tags: [decision, sut, startup, analytics-cache]
type: decision
status: settled
source: "src/bilun/domain/claims/config.py"
last_compiled: 2026-05-10
llm_summary: "BILUN_DATA_MODE must force synthetic_demo claim inputs and reject/rebuild stale active SUT analytics caches that were built from health/hospital data."
llm_keywords: [sut, start_sut, synthetic_demo, analytics_cache, claim, launcher, stale-cache]
llm_questions:
  - "Why did start_sut use the health data cache?"
  - "How does the SUT launcher enforce synthetic data?"
  - "What should start_sut do with stale SUT analytics caches?"
related: ["[[sut]]", "[[split-sut-ihp]]", "[[2026-05-04-sut-synthetic-data-plan]]"]
---

# SUT Synthetic Launcher Cache Guard

## Key Facts

- `start_sut.sh` previously accepted any active `sut` analytics build with SUT rows, so a stale active cache built from the health/hospital dataset could be reused.
- The SUT configuration now defaults to `BILUN_DATA_MODE=synthetic_demo`, `BILUN_CLAIMS_DIR=data/synthetic/sut/claims` (env vars in `src/bilun/domain/claims/config.py`). The old `SUT_DATA_MODE`/`SUT_CLAIMS_DIR` env vars are deprecated.
- The config validates that the active SUT cache has synthetic-demo provenance and synthetic patient payload rows; if not, it rebuilds and activates a synthetic claim cache.

## Context

The SUT runtime is being migrated away from hospital clean clinical data and toward a claim-native synthetic demo dataset. During migration, an older SUT cache built from health/hospital data could be reused instead of the synthetic SUT fixture, serving the wrong product data.

## Decision / Insight

The SUT launcher must not trust the active `sut` build pointer alone. It must verify synthetic claim-demo provenance before starting the SUT API and must rebuild the active SUT cache from `data/synthetic/sut/claims` when the existing cache is stale, missing, or built from the wrong source.

## Rationale

A split app can have a valid `sut` build pointer while still serving the wrong product data. Since the current SUT product surface is supposed to run on synthetic SUT claims, startup must guard the runtime source, not just the presence of rows.

## Action Items

- The SUT config at `src/bilun/domain/claims/config.py` is the enforcement point for data-source provenance preflight.
- Continue the broader claim-only runtime migration so cache assembly no longer reads synthetic clean Parquets either.
- When real Acıbadem billing claims are introduced, add a separate explicit real-claims launch path rather than weakening synthetic-demo guarantees.

## Source / Date

- Source: `src/bilun/domain/claims/config.py`
- Date: 2026-05-10
