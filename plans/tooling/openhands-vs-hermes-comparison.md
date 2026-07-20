# OpenHands+mem0 vs Hermes Agent — Comparison for the Bilun "AI Employees" Vision

**Date:** 2026-07-20
**Status:** Decision-support doc. Both options researched; OpenHands+mem0 tested
end-to-end; Hermes researched via docs/issues but NOT yet installed.

## What was actually proven

### OpenHands + mem0 — TESTED end-to-end (2026-07-20)
- Custom sandbox image built with Bilun deps + mem0 + CPU torch (8.24GB).
- Reimbursement agent ran twice; run #2 correctly reported **"memory stored TIER-1 count
  (116) matches today's checker output (116) — unchanged, as expected with no remediation."**
- That's the diff-aware loop working: the agent didn't re-discover the baseline, it
  compared against prior memory and reported the delta.
- Real issues surfaced: iteration caps need per-role tuning (Data hit 15, Reimbursement
  with mem0 hit 20), `Z_API_KEY` env forwarding gap, mem0's LLM extractor can't handle
  >2.5KB inputs (fixed by capping report size in save.py).

### Hermes Agent — RESEARCHED but not installed
Real repo: `github.com/NousResearch/hermes-agent` (MIT, ~216k stars, last commit Jul 18
2026 — actively maintained). Built by Nous Research (the Hermes model lineage org).

## Head-to-head on your vision

| Dimension | OpenHands + mem0 (tested) | Hermes Agent (researched) |
|---|---|---|
| **"Employees that learn over time"** | ✅ Via mem0 — proven diff-aware loop today | ✅ **Native** — built-in skill extraction (`SKILL.md` files in `.hermes/skills/`), DSPy+GEPA self-evolution repo |
| **Persistent memory** | ✅ mem0 + Qdrant (we built it) | ✅ Built-in `MEMORY.md` (file-based, auditable) + optional ChromaDB |
| **3 specialized roles** | ✅ Manual via `agents/<role>/AGENTS.md` + system prompts | ✅ Native subagents with per-agent `system_prompt`, `model`, `tools`, `cwd` |
| **Z-API / GLM compat** | ✅ **Proven** end-to-end on your endpoint | ⚠️ First-class `zai` provider BUT 3 active bugs: auth scope ([#4167](https://github.com/NousResearch/hermes-agent/issues/4167)), 429 rate-limit loops ([reddit](https://www.reddit.com/r/hermesagent/comments/1uim8li/)), model-list lag ([#8461](https://github.com/NousResearch/hermes-agent/issues/8461)) |
| **Read-only / propose-only** | ✅ Docker `:ro` mount — physically enforced | ✅ Read-only mounts + workspace allow-lists documented |
| **Skill inspection/editing** | N/A (mem0 stores in Qdrant, harder to audit) | ✅ **Skills are markdown files** — `cat`, edit, `rm`, git-commit |
| **Maturity for 7/24 unattended** | Established (ex-OpenDevin, many field reports) | ⚠️ **No credible multi-week unattended field reports found** — younger in production |
| **Multi-week "learning compounding" proof** | None (we just built it) | ⚠️ **Mechanism real, benefit anecdotal** — no citable benchmark showing skills measurably improve outcomes over N runs |
| **Install complexity** | Moderate (Docker image we already built) | Higher (Rust core + Python tools + optional ChromaDB; native installer or cargo) |
| **"Managed employee" pattern** | We hand-rolled it (AGENTS.md + system-prompt.md) | ✅ Sibling repo [`hermes-paperclip-adapter`](https://github.com/NousResearch/hermes-paperclip-adapter) — "run Hermes as a managed employee in a Paperclip company" |

## The honest tension

**Hermes fits the *narrative* of your vision better.** Skills as markdown files, native
subagents, the Paperclip "employee" adapter, self-evolution via DSPy+GEPA — that's
architecturally closer to "AI employees that get better every day" than OpenHands+mem0 is.

**OpenHands fits the *proven-working* reality better.** You have a working diff-aware
loop today. The Z-API path is debugged. The sandboxing is battle-tested. The 3 roles
produce cited findings in 80-195s each.

The gap between them is **smaller than it looks** because:
1. mem0 gives OpenHands the same persistent-memory capability Hermes has natively.
2. The "skills" advantage is real but **unproven at your scale** — no benchmark shows
   skills compound into better outcomes for a specific codebase over N runs.
3. The infrastructure we built (5 checkers, 3 role AGENTS.md, reports layout, mount
   config) **transfers to either tool** — it's not OpenHands-specific.

## What the Hermes research flagged as risks

If you switch to Hermes, expect to hit:
1. **Auth scope failure on first run** ([#4167](https://github.com/NousResearch/hermes-agent/issues/4167)) — Z-API keys lack the `inference:mint_agent_key` scope Hermes requests. Budget time for the workaround.
2. **429 rate-limit loops** — Z-API's per-minute caps × Hermes's parallel subagent fan-out = retry storms. You'd need to lower `parallel_tool_calls` + add backoff.
3. **Younger in production** — no credible multi-week unattended field reports. OpenHands has many.
4. **The "learning loop improves outcomes" claim is unverified** — mechanism is real (you can inspect the skill files), but whether it actually makes the agent better at *your* tasks over time is anecdotal, not benchmarked.

## Recommendation

**Stay on OpenHands+mem0 as the daily driver; run a 2-week Hermes pilot in parallel.**

Reasoning:
- OpenHands+mem0 is **proven working today** with your Z-API tokens. Switching to Hermes
  trades a working path for a debugging project (3 known Z-API bugs).
- The OpenHands investment is mostly tool-agnostic (checkers, roles, reports) — if the
  Hermes pilot shows real skill-compounding benefit, migration cost is bounded.
- The Hermes pilot's success criterion should be **measurable**, not vibes: after ~10 runs
  on the same role, do `.hermes/skills/` files contain genuinely useful, non-noisy
  knowledge *for the Bilun codebase*? If yes, migrate. If no, the "learning" narrative is
  marketing for your use case.

**Concrete pilot plan (if you choose to run it):**
1. Install Hermes in a side container, `zai` provider, `glm-5.2`, read-only Bilun mount.
2. Reproduce ONE existing OpenHands run (same Reimbursement prompt) — compare proposal quality.
3. Hit [#4167](https://github.com/NousResearch/hermes-agent/issues/4167) + 429 issues early; fix before judging quality.
4. After ~10 runs, inspect `.hermes/skills/` + `MEMORY.md` — judge if skills are useful.
5. Compare token cost per run (OpenHands+mem0 vs Hermes) — Hermes's skill retrieval may
   reduce tokens over time, OR its parallel fan-out may increase them.

## What this means for your "AI employees" vision

Both tools can serve the vision. The vision's success is **70% determined by the harness**
(review gates, deterministic checkers, propose-only enforcement, stuck-detection) and
**30% by the agent runtime**. You've built the harness already. The runtime is swappable.

The one thing neither tool solves: **priority sense** — knowing what matters most right
now. mem0/Hermes-skills tell the agent "what was true last run," not "what Safa cares about
this week." That gap is human input, and no tool closes it automatically.

## Citations
- Hermes repo: https://github.com/NousResearch/hermes-agent
- Hermes docs: https://hermes-agent.nousresearch.com/docs/
- Z.AI provider docs: https://hermes-agent.nousresearch.com/docs/user-guide/providers/zai
- Skills system: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
- Auth bug: https://github.com/NousResearch/hermes-agent/issues/4167
- 429 thread: https://www.reddit.com/r/hermesagent/comments/1uim8li/
- Paperclip adapter: https://github.com/NousResearch/hermes-paperclip-adapter
- Self-evolution: https://github.com/NousResearch/hermes-agent-self-evolution
