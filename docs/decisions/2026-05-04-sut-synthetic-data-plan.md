---
title: "SUT Synthetic Data Plan"
aliases: ["sut synthetic data", "synthetic sut claims", "sut excel synthetic dataset"]
tags: [decision, sut, synthetic-data, claims, excel]
type: decision
status: provisional
source: "plans/synthetic-data-v2.md"
sources:
  - "plans/synthetic-data-v2.md"
  - "src/bilun/cache/data_loader.py:L5-L10"
  - "src/bilun/cache/data_loader.py:L32-L95"
  - "src/bilun/cache/loaders.py:L8-L52"
  - "src/bilun/domain/optimization/exactness.py:L11-L49"
  - "src/bilun/domain/billing/strategy.py:L13-L38"
last_compiled: 2026-05-04
model: "gpt-5.5"
settled: true
settled_at: 2026-05-04
settled_reason: "User decided v1 should start with one committed, completely Turkish, multi-sheet Excel workbook for 5 visibly synthetic patients."
llm_summary: "SUT synthetic data v1.1 keeps the committed Turkish 5-patient workbook and hardens lab billing links, prescription-to-drug claim FKs, and line-level expected outputs before any 100-patient scaling."
llm_keywords: [sut, synthetic data, excel, claims, procedures, exactness, billing-native, lab linkage, prescription linkage, expected outputs]
llm_questions:
  - "How should we create synthetic SUT data?"
  - "What Excel sheets are needed for synthetic SUT claims?"
  - "How can synthetic data unlock exact SUT features?"
  - "What schema hardening is required before scaling SUT synthetic data to 100 patients?"
related: ["[[sut]]"]
---

# SUT Synthetic Data Plan

## Context
- The user wants to create synthetic data so the SUT module can consume exact billing/procedure inputs, starting with 5 visibly synthetic patients in one multi-sheet Excel workbook where every procedure each patient took is explicitly written.
- Current clean runtime loaders consume Turkish-column Parquet tables for anadata, lab, and prescriptions, while exact SUT features remain gated because claim/procedure/material/drug line inputs are missing.

## Decision / Insight
- Start with one committed billing-native synthetic Excel workbook for 5 patients.
- Workbook sheet names and column headers are completely Turkish.
- Patient IDs should look fake, e.g. `SENTETIK-HASTA-001`.
- V1 uses a deliberately small curated subset of real EK-2B, EK-2C, EK-3, and drug catalog items chosen only to support the 5 canonical scenarios and later 100-patient expansion.
- Require explicit claim headers and procedure line items for every patient; do not infer procedures from ICD codes.
- Generate both current loader-compatible clean Parquets and new exact SUT claim Parquets.
- Treat synthetic data as a development, demo, and regression-test artifact, not real hospital validation.
- Before scaling to 100 patients, v1.1 must harden three traceability gaps: billed lab rows link to billed procedure lines or are explicitly marked non-billed, drug claim rows reference stable prescription IDs, and expected outputs include line-level rows as well as claim-level rows.

## Rationale
- Current SUT exactness gates require explicit procedure codes, dates, itemized lines, admission dates, drug claim lines, and billed amounts.
- Excel is useful for manual review of scenario design, and v1 must be committed so the canonical examples are visible and reviewable.
- Five patients are enough for the first canonical scenario fixture; the 100-patient mix comes after review.
- The v1 prototype already proved the billing-native hierarchy, but weak lab linkage, weak prescription linkage, and claim-only expected outputs would become expensive to clean after 20x scaling.

## Action Items
- Use `plans/synthetic-data-v2.md` as the implementation plan.
- Hand-author or generate canonical patients first in `data/synthetic/sut/sentetik_sut_v2_50_hasta.xlsx`.
- Build a deterministic generator and validator before scaling beyond 50 patients.
- Keep generated data isolated under `data/synthetic/sut/` rather than overwriting production clean inputs.
- For v1.1, strengthen the generator and validator so lab billing status/linkage, `recete_id` foreign keys, and line-level expected outputs are mandatory.

## Source / Date
- Source: user request plus Hermes chat summary and verified code references above
- Date: 2026-05-04
