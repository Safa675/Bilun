# Design: mem0 Memory Layer for the 3 Employee Agents

**Date:** 2026-07-20
**Status:** Design doc — not yet built. Sequenced AFTER the custom sandbox image is
proven (you can't test memory before the agents can run).
**Predecessor:** `plans/tooling/employee-agents-plan.md` (the 3 roles + checkers).

## Problem
Each OpenHands conversation is amnesiac — fresh sandbox, zero memory of prior runs. The
Reimbursement Engineer that found 116 superseded-clause refs last Tuesday has no memory of
that finding this Tuesday. It re-runs the checker, re-flags the same 116, can't tell you
"3 of these were fixed since last run, 2 are new." This is the gap between "scout you
launch once" and "employee who builds on prior work."

mem0 ([github.com/mem0ai/mem0](https://github.com/mem0ai/mem0)) is the proposed fix: a
persistent memory layer that each agent reads at conversation start and writes to at
conversation end. This doc specifies the integration without building it.

## Design goals
1. **Per-role namespaces** — Reimbursement's memory must not pollute Full-stack's. mem0's
   `user_id` field is the namespace; map 1:1 to roles.
2. **Diff-aware reports** — each run's report begins "since last run: N new findings, M
   resolved, K still pending." This requires loading prior memory before running checkers.
3. **No token-bloat** — memory should hold distilled facts ("187 wrong mappings found
   2026-07-20; 26 resolved by commit 06ba72f; 161 pending triage"), not raw parquet rows.
4. **Self-hosted only** — no external API dependency. Qdrant on disk (laptop) → Qdrant
   container (VPS later).
5. **Approval-gate preserved** — memory tracks "proposed" vs "applied" so the human
   decision loop isn't bypassed.

## Architecture

```
                    ┌─────────────────────────────────┐
                    │  mem0 container (Qdrant + API)  │
                    │  data: ~/.bilun-mem0/qdrant/    │
                    │  user_id namespaces:            │
                    │    reimbursement_engineer       │
                    │    fullstack_engineer           │
                    │    data_engineer                │
                    └──────────────┬──────────────────┘
                                   │ search() / add()
                                   ▼
  Agent conversation (OpenHands sandbox)
    │
    ├─ Step 0 (NEW): run `agents/memory/load.py --role <role>`
    │   → queries mem0 for last-run findings + pending items
    │   → prints a "prior context" summary the agent reads before doing anything
    │
    ├─ Step 1: bash agents/<role>/run_checks.sh   (existing)
    ├─ Step 2: diff current findings vs prior memory (NEW — in the prompt)
    ├─ Step 3: write findings report              (existing)
    │
    └─ Step 4 (NEW): run `agents/memory/save.py --role <role>`
        → extracts distilled facts from this run's findings
        → adds to mem0 with the role's user_id
        → marks which findings are new vs recurring
```

## Namespaces per role

| Role | `user_id` | What gets stored | Example memory entries |
|---|---|---|---|
| Reimbursement | `reimbursement_engineer` | wrong-mapping counts, stale-clause tiers, partial-rule status, SUT-version deltas | `"2026-07-20: 187 suspected wrong mappings (22 distinct sut_codes); 26 pre-fix residue per commit 06ba72f. Top suspect: EK-3 KN1069 intrathecal pump kit."` |
| Full-stack | `fullstack_engineer` | endpoint-coverage %, untested endpoint list, dead test calls, TS errors | `"2026-07-20: 29/37 endpoints untested (21.6%). Top gap: GET /api/billing-report/{patient_id}. 3 dead /api/sut/* calls in test_sut_chat.py:515-517."` |
| Data | `data_engineer` | pipeline-smoke status, freshness violations, MÜLGA audit results | `"2026-07-20: pipeline_smoke PASS (17.6s). 2026.07.01 consolidated SUT NOT ingested — pending Safa's approval. 21 stale-curated parquets."` |

**Cross-role isolation is enforced by `user_id`.** A search by Reimbursement never sees
Full-stack's entries. Optional later: a shared `meta` namespace for repo-wide facts ("Safa
is waiting on Acibadem data") that all roles read.

## What gets written to memory (and what doesn't)

**WRITE (distilled facts, <500 chars each):**
- Checker headline numbers (coverage %, gap counts, freshness violations)
- New findings since last run ("3 new wrong mappings vs last run")
- Resolved items ("commit X resolved Y wrong mappings")
- Pending decisions ("Safa has not yet approved ingesting 2026.07.01")
- Context anchors ("drug_indication_prose intentionally implemented — do NOT re-flag")

**DO NOT WRITE:**
- Raw parquet rows (the parquet is the source of truth; memory holds the summary)
- Full report text (that lives in `reports/agent/<role>/findings-<date>.md`)
- Anything >500 chars (forces distillation; prevents memory bloat)
- Secrets (LLM keys, etc.)

## When memory loads (prompt integration)

The role's `system-prompt.md` gains a new Step 0:

```bash
# Step 0 (before running checkers): load prior memory
python /workspace/bilun/agents/memory/load.py --role reimbursement_engineer
```

This prints a "Prior context" block the agent reads:
```
=== Prior context (reimbursement_engineer) ===
Last run: 2026-07-20 (3 days ago)
- 187 wrong mappings found; 26 marked pre-fix residue; 161 pending triage.
- drug_indication_prose intentionally implemented (DO NOT re-flag).
- finans_pricing_audit.py import bug reported; fix pending.
- Open question: are the 161 pending mappings resolver bugs or hospital errors?
```

The agent then knows: re-running the checker should show roughly the same numbers, and its
job is to **diff and explain the delta**, not re-discover the baseline.

## When memory saves (end of run)

`agents/memory/save.py` runs as the LAST step of `run_checks.sh`:

```bash
# After the report is written:
python /workspace/bilun/agents/memory/save.py \
    --role reimbursement_engineer \
    --report reports/agent/reimbursement/findings-$(date +%Y-%m-%d).md
```

The script:
1. Reads the report.
2. Uses mem0's LLM to extract 3-7 distilled facts (configurable).
3. Adds each to mem0 under the role's `user_id` with metadata `{run_date, checker, severity}`.
4. Marks recurring findings (mem0's dedup handles this automatically — same fact updates
   the existing entry instead of creating a duplicate).

## Configuration (self-hosted, OpenAI-compatible LLM)

mem0 needs an LLM for fact extraction. We point it at the same Z-API GLM endpoint the
agents use, so there's no new API key. Config (`agents/memory/config.py`):

```python
from mem0 import Memory

CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "bilun_agents",
            "path": "/workspace/mem0/qdrant",  # persisted via a docker volume
        },
    },
    "llm": {
        "provider": "openai",  # openai-compatible — works with Z-API
        "config": {
            "model": "glm-4.6",  # cheaper than 5.2 for fact extraction
            "api_key": os.environ["Z_API_KEY"],
            "openai_base_url": "https://api.z.ai/api/coding/paas/v4",
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "embedding-3",  # or whatever Z-API exposes
            "api_key": os.environ["Z_API_KEY"],
            "openai_base_url": "https://api.z.ai/api/coding/paas/v4",
        },
    },
}

mem = Memory.from_config(CONFIG)
```

**Known caveat (mem0 Issue #4910):** some mem0 components override `LLM_BASE_URL` from DB
config, breaking OpenAI-compatible proxies. Workaround: set `OPENAI_BASE_URL` AND
`LLM_BASE_URL` env vars both to the Z-API endpoint. Verify during implementation.

## Deployment

**Laptop (experimental, this round):**
- mem0 runs in its own Docker container alongside `openhands-app` + the sandbox.
- Qdrant data persists at `~/.bilun-mem0/qdrant/` (host volume).
- `docker-compose.yml` under `agents/memory/` defines: mem0 + qdrant.

**VPS (future, once laptop-proven):**
- Same compose file, deployed to the VPS. The 3-role architecture is unchanged.
- Add a nightly cron that triggers each role's `run_checks.sh` + agent conversation.

## Token cost model

Each agent run now costs **2 LLM calls instead of 1**:
1. The agent itself (glm-5.2, reasoning + checker interpretation): ~10-30k tokens/run.
2. mem0 fact extraction (glm-4.6, just distilling the report): ~2-5k tokens/run.

The trade is: +30% tokens per run, but the agent stops re-discovering the same baseline
every time. Net positive if runs happen ≥2× per week per role. Net negative if you run
once a month (memory rots; just read the report).

**Recommendation:** enable mem0 only for Reimbursement first (highest re-run frequency —
the wrong-mapping count changes as you fix them). Full-stack and Data can stay amnesiac
until their re-run cadence justifies it.

## Risks / open questions
- **Memory rot** — if the codebase changes but memory isn't updated, the agent reasons
  against stale facts. Mitigation: `save.py` always overwrites the headline numbers, so
  the latest count is always current. Detailed facts (e.g. "KN1069 is a pump kit") are
  evergreen and won't rot.
- **mem0 fact-extraction quality** — glm-4.6 may extract noisy or wrong facts. Mitigation:
  the human reviews the distilled facts in the report before they're trusted; mem0 entries
  carry `confidence` and can be manually deleted.
- **Qdrant persistence across restarts** — must verify the host volume survives container
  recreation. Test: write a memory, recreate the container, search — must return the entry.
- **Cross-role shared context** — deferred. Each role only sees its own namespace in v1.
- **Privacy** — mem0 stores distilled facts about the codebase locally (Qdrant on disk).
  No external transmission except the Z-API LLM call for extraction (same as the agent
  itself). Acceptable for Bilun's scope.

## Subtasks (when this gets built — NOT this round)

1. Add `agents/memory/{config.py,load.py,save.py,__init__.py}`.
2. Add `agents/memory/docker-compose.yml` (mem0 + qdrant).
3. Add Step 0 (load) + Step 4 (save) to each role's `system-prompt.md` + `run_checks.sh`.
4. Test: run Reimbursement twice; confirm the second run's report says "since last run:
   0 new findings" (proves memory load + diff works).
5. Test: fix one wrong mapping between runs; confirm the second report says "1 resolved."
6. Capture lessons; document the token-cost reality after N runs.

## Definition of Done (when built)
- `docker compose up` under `agents/memory/` starts mem0 + qdrant cleanly.
- `load.py --role <r>` returns the last run's distilled facts in <2s.
- `save.py --role <r> --report <path>` adds 3-7 facts to mem0 under the right namespace.
- Two consecutive Reimbursement runs produce diff-aware reports (not identical baselines).
- No cross-role leakage: Full-stack search returns zero Reimbursement entries.
- mem0 survives container restart (Qdrant volume verified).

## What this design deliberately does NOT do
- **Does not give agents judgment.** Memory tells them "what was true last run," not
  "what matters most right now." The priority-sense gap (the hardest autonomous-agents
  problem) is not solved by memory alone.
- **Does not auto-apply fixes.** Memory tracks "pending Safa's approval" but never applies
  anything. The approval gate is unchanged.
- **Does not enable 7/24 autonomy.** Still manual launch. The scheduler + VPS are separate
  future work.
- **Does not store raw data.** Parquet stays the source of truth; memory holds summaries.
