# Plan: Install OpenHands (self-hosted) + Z coding-plan LLM

**Date:** 2026-07-19
**Status:** Approved (user answered clarification questions)
**Context:** Continuation of prior session's "3 employee agents" research. OpenHands
was identified as the only existing tool that autonomously modifies a real codebase,
is self-hostable, and is model-agnostic. This plan proves the runtime on the laptop
first; the VPS + agent-role setup is a later task.

## Goal
OpenHands UI running at http://localhost:3001, backed by GLM via the Z coding-plan
endpoint, able to read the Bilun repo. End-to-end functional test passes. Pattern
proven so we can evaluate it as the employee-agent platform.

## Environment (verified this session)
- Docker 29.6.1, Compose 5.3.1, Python 3.13.13, uv 0.11.24 — all present
- Disk 235 GB free, RAM 15 GB free — adequate (OpenHands asks 4 GB min)
- `safa` NOT in `docker` group; `sudo` needs interactive password → user must add themselves
- Port 3000 IN USE by Bilun frontend (next-server pid 748883) → bind OpenHands to 3001
- Z coding-plan base URL confirmed: `https://api.z.ai/api/coding/paas/v4` (the `/coding/`
  path segment routes to the coding-plan tier; source: zcode.z.ai/en/docs/configuration)
- ZCode uses OAuth for the coding plan (`modelProviderFamilyModes.zai = oauth` in
  setting.json) → OpenHands cannot reuse this; user must supply a raw API key from z.ai

## Subtasks
1. **Grant Docker access** — user runs `sudo usermod -aG docker safa && newgrp docker`
   in their own terminal. I cannot (sudo is interactive). Verify: `docker ps` works
   without sudo.
2. **Install OpenHands via uv** — `uv tool install openhands --python 3.12`
   (official recommended path; uv already present at 0.11.24).
3. **Launch on :3001** — `openhands serve` hardcodes `-p 3000:3000` (verified in
   `openhands_cli/gui_launcher.py:187-196`; no `OPENHANDS_PORT` env override exists).
   Since the Bilun frontend is on :3000, bypass the wrapper and run the equivalent
   `docker run` directly with `-p 3001:3000`:
   ```bash
   docker run -it --rm --pull=always \
     -e LOG_ALL_EVENTS=true \
     -e SANDBOX_VOLUMES=/home/safa/Documents/Bilun:/workspace:rw \
     -e SANDBOX_USER_ID=$(id -u) \
     -v /var/run/docker.sock:/var/run/docker.sock \
     -v ~/.openhands:/.openhands \
     -p 3001:3000 \
     --add-host host.docker.internal:host-gateway \
     --name openhands-app \
     docker.openhands.dev/openhands/openhands:$(openhands --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
   ```
   (Command mirrors `gui_launcher.py:127-197` exactly, except `-p 3001:3000` and the
   `SANDBOX_VOLUMES` mount folded in. Omit the `SANDBOX_VOLUMES`/`SANDBOX_USER_ID` lines
   for a first no-mount smoke test, add them for the repo-mount step.)
4. **Smoke-launch verification** — `curl -sI http://localhost:3001` returns 200/302;
   `docker ps` shows openhands-app container healthy.
5. **Configure LLM in UI** — Settings → LLM → Advanced:
   - Base URL: `https://api.z.ai/api/coding/paas/v4`
   - Custom Model: `glm-4.6` (verify exact string at z.ai/model-api before saving)
   - API Key: user-provided raw key (NOT the OAuth token)
6. **Mount Bilun repo** — relaunch with `openhands serve --mount-cwd` from
   `/home/safa/Documents/Bilun` so the agent can read (not yet write) the codebase.
7. **Functional test** — in the UI, ask the agent to `ls` the repo root and report one
   file. Confirms repo access + LLM round-trip end-to-end.
8. **Capture lessons** — any port/permission/Docker gotchas → `tasks/lessons.md`.

## Out of Scope
- Setting up the "3 employee agents" (Reimbursement / Full-stack / Data Engineer) —
  that is the NEXT task once OpenHands is proven to run at all.
- Renting the VPS — local laptop install first; VPS replication is later.
- Writing per-module AGENTS.md / system prompts — next task.
- Write access to the repo + branch-per-agent — read-only smoke test this round.
- Wiring deterministic health-check scripts (Finans Coder verifier etc.) — later task,
  built before any autonomous mode (these are the "moat", per prior session).

## Risks / Open Questions
- ~~`OPENHANDS_PORT` env var~~ RESOLVED: not honored; launcher hardcodes :3000. Using
  raw `docker run -p 3001:3000` instead (verified command in step 3).
- Z coding-plan uses OAuth in ZCode; OpenHands needs a raw API key. User must generate
  one at the Z.ai platform — I cannot retrieve it.
- Exact model string: **`glm-4.6`** confirmed (z.ai/blog/glm-4.6,
  docs.z.ai/devpack/overview) as the current coding-plan model.
- OpenHands image is ~2 GB; first `docker run --pull=always` may take several minutes.

## Definition of Done
- `curl -sI http://localhost:3001` returns a 2xx/3xx
- `docker ps` shows the openhands container Up
- LLM settings saved without error in the UI
- Agent successfully `ls`s `/home/safa/Documents/Bilun` and reports a real filename

## Review — Completed (2026-07-19)

All Definition-of-Done criteria met. Full agent loop proven end-to-end:
glm-5.2 (Z coding-plan) → agent reasoning → `terminal` tool → `cat AGENTS.md | head -5`
(exit 0, working_dir `/workspace/bilun`) → agent reported real content verbatim.

**What was built:**
- OpenHands app-server running at `http://localhost:3001` (container `openhands-app`)
- One healthy sandbox (`oh-agent-server-3iR1Hpbq2lltmpELW2ETP9`, agent-server at `:52527`)
- LLM config in `~/.openhands/settings.json`: model `openai/glm-5.2`, base_url
  `https://api.z.ai/api/coding/paas/v4`, api_key set (masked on read-back)

**Five things the plan got wrong, caught during execution (all in tasks/lessons.md):**
1. ~~`OPENHANDS_PORT` env override~~ — doesn't exist; `serve` hardcodes :3000. Used raw
   `docker run -p 3001:3000`.
2. ~~Model `glm-4.6`~~ — the coding plan exposes the full list incl. `glm-5.2`; used that.
3. **Model string must be `openai/glm-5.2`**, not bare `glm-5.2` — litellm requires a
   provider prefix; it strips it before forwarding to Z-API (which rejects the prefix).
   First agent run failed with `LLMBadRequestError`; fixed.
4. **Repo must mount as `/workspace/bilun:ro` (read-only subdir)**, not as `/workspace` root.
   Bare `/workspace` mount failed: sandbox runs as uid 10001 (hardcoded), Bilun owned by
   safa/1000 → `PermissionError: /workspace/conversations`. Subdir mount keeps `/workspace`
   image-owned (writable) + Bilun read-only.
5. **Tool name is `terminal`** (registered lowercase), not `TerminalTool` (class name) —
   `ToolDefinition 'TerminalTool' is not registered`. Get registered names via
   `GET /api/tools/` on the agent-server.

**Operational notes for next session:**
- App + sandbox containers are still running. To restart after reboot:
  `sg docker -c "docker run -d --rm -e LOG_ALL_EVENTS=true -e SANDBOX_VOLUMES=/home/safa/Documents/Bilun:/workspace/bilun:ro -e SANDBOX_USER_ID=$(id -u) -v /var/run/docker.sock:/var/run/docker.sock -v /home/safa/.openhands:/.openhands -p 3001:3000 --add-host host.docker.internal:host-gateway --name openhands-app docker.openhands.dev/openhands/openhands:latest`
  (the `sg docker -c` wrapper is needed until a fresh login picks up the docker group)
- Settings survive restarts (host volume `~/.openhands`).
- The repo is READ-ONLY to the agent. Write access (branch-per-agent) is a deliberate
  next step, not enabled here.

**Out-of-scope items confirmed still out of scope:**
- "3 employee agents" (Reimbursement/Full-stack/Data Engineer) — next task
- Per-module AGENTS.md + system prompts — next task
- Deterministic health-check scripts — later task (the "moat")
- VPS replication — later task
