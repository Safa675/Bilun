# Plan: Deploy OpenHands to VPS + run one agent (smoke test)

**Date:** 2026-07-21
**Status:** Draft v2 — incorporates reviewer feedback (4 valid fixes; 2 phantom
issues rejected with evidence).
**Scope chosen by user:** smoke test first · build image on VPS · remote UI (human-driven)
**Predecessor docs:**
- `plans/tooling/openhands-install-plan.md` — laptop install (proven 2026-07-19)
- `plans/tooling/employee-agents-plan.md` — 3 roles + checkers
- `plans/tooling/mem0-integration-design.md` — memory layer design

## Revision history
- **v1 → v2 (2026-07-21):** reviewer caught 4 real issues — all fixed below:
  1. Step 5 `docker run` now includes the **dual-mount** (`:ro` repo + `:rw` reports)
     matching the laptop proof, so Step 7's "report exists" verification is achievable.
  2. Port-3001 security exposure upgraded from optional note to **mandatory P0
     prerequisite** in Step 5 (ufw restricted to laptop IP, before the port binds).
  3. Smaller fixes: `-e MAX_ITERATIONS=30` added (verified env var, default 100),
     `--pull=always` added, Step 7 reframes cap-exhaustion as "bump and retry"
     not "verification failure."
  4. **Step 0.5 added** — rollback snapshot of VPS state before any write.
- **Two reviewer points rejected with evidence** (not integrated):
  - *"Password leaked earlier, IP 169.58.50.165"* — that IP has 0 grep matches in
    the repo; the password string has 0 matches; no such paste exists in session
    history. Documented VPS is `165.245.243.183` (vps-deploy-plan.md:17,36,39,48,69).
  - *"PR #38 doesn't exist; only #37 merged"* — verified via `gh pr view 38`:
    PR #38 is MERGED (2026-07-20T21:19:22Z), the Dependabot upgrade from earlier
    this session. Plan's reference is correct.

## Goal
OpenHands app + custom Bilun sandbox image running on the VPS at
`http://165.245.243.183:3001`, with `/opt/Bilun` mounted read-only AND
`/opt/Bilun/reports/agent` mounted read-write. A human opens the remote UI, runs
the Reimbursement agent once, and confirms it produces a findings report.
**One agent, one run, manual trigger — that's it.**

If the smoke test passes, the follow-on plans (docker-compose, TLS, mem0 wiring,
cron, all 3 roles) become worth writing. They are explicitly out of scope here.

## What this is NOT
- No TLS / no domain / no reverse proxy for the agent UI (raw `:3001`, IP-only,
  ufw-restricted to the laptop IP)
- No docker-compose yet — single `docker run` commands, like the laptop setup
- No mem0 wiring into `run_checks.sh` (that gap is documented; not this round)
- No scheduler / cron / automation
- No CI integration
- No Docker-in-Docker hardening beyond "ufw-restricted port + dedicated root box"
- All 3 roles not deployed — **Reimbursement only**, the highest-value role

## Why these choices (from investigation)
- **Smoke test first:** the OpenHands+mem0 stack has only ever run on the laptop.
  Jumping straight to docker-compose + cron + 3 roles buries failures. Prove the
  round-trip once, then layer.
- **Build image on VPS:** the 8.24GB image is local-only (no registry). Building
  on the VPS is slower first-time but reproducible and avoids an 8GB network pipe
  from laptop. The Dockerfile is already in the repo at
  `scripts/agent/sandbox/Dockerfile`.
- **Remote UI:** matches how agents run today (human pastes prompt, watches, reads
  report). Headless automation is a separate, larger task.

## Prerequisites (what must be true before starting)

These are verified in Step 0. If any fail, STOP and surface to user.

- [ ] SSH works: `ssh -i ~/.ssh/bilun_vps root@165.245.243.183`
- [ ] VPS has **≥8 GB RAM free** (smoke test = 1 agent; full stack needs ~16 GB)
      — if `<4 GB free`, abort: OpenHands will OOM
- [ ] VPS has **≥20 GB disk free** in `/` (openhands base ~3 GB + torch/mem0
      layering ~5 GB + docker layer cache + repo clone ~2 GB)
- [ ] OS is Linux x86_64 (the openhands base image is `amd64`)
- [ ] Port 3001 is free on the VPS (not bound by anything else)
- [ ] `/opt/Bilun` exists and is a current checkout at `main` HEAD (the web app
      deploys there per `.github/workflows/deploy.yml:51`; PR #38 is merged on
      GitHub so HEAD includes both #37 agent infra and #38 frontend bump)

## Subtasks

### Step 0 — VPS state verification (read-only, mandatory)
- [ ] SSH to `root@165.245.243.183` via `~/.ssh/bilun_vps`
- [ ] Run read-only probes and record output:
  - `uname -a` — OS/arch/kernel
  - `cat /etc/os-release | head -5` — distro
  - `free -h` — RAM (note "available" column, not "total")
  - `df -h /` and `df -h /var` — disk (docker stores layers under `/var/lib/docker`)
  - `docker --version` and `docker compose version` — installed?
  - `which docker` — if missing, note it (Step 1 will install)
  - `docker ps 2>/dev/null` — what's already running?
  - `ss -tlnp | grep -E '3001|3000|8000'` — port conflicts
  - `ls -la /opt/Bilun | head -5` — repo present?
  - `git -C /opt/Bilun log -1 --oneline` — checkout at HEAD? (should show a commit
    from 2026-07-20 or later; if older, Step 2 pulls)
  - `id` — confirm root
- [ ] **Decision gate:** if RAM/disk short → STOP and report to user before any
      write step. If Docker missing → Step 1 runs. If `/opt/Bilun` stale → Step 2
      pulls.
- [ ] Record findings in this plan's Review section before any write step

### Step 0.5 — Snapshot VPS state for rollback (cheap insurance)
Before any write/install/build operation, capture a known-good baseline so the
smoke test can be rolled back if it somehow disturbs the running web app.

- [ ] On the VPS, run:
      ```bash
      {
        echo "=== captured $(date -u +%FT%TZ) ==="
        echo "--- docker ps -a ---"; docker ps -a 2>/dev/null
        echo "--- running systemd services ---"; systemctl list-units --type=service --state=running --no-pager | head -40
        echo "--- bilun service status ---"; systemctl is-active bilun-backend bilun-frontend 2>/dev/null
        echo "--- listening ports ---"; ss -tlnp 2>/dev/null | head -20
      } > /tmp/vps_state_before.txt
      ```
- [ ] Verify the snapshot captured content: `wc -l /tmp/vps_state_before.txt`
      (should be ≥30 lines if the commands worked)
- [ ] This file is the rollback reference. If verification criterion #5
      (web app still healthy) fails at the end, diff current state against this
      file to locate the disturbance.

### Step 1 — Install Docker on VPS (only if Step 0 shows it missing)
- [ ] Use the official convenience script (fast, standard for single-purpose boxes):
      `curl -fsSL https://get.docker.com | sh`
- [ ] Verify: `docker --version`, `docker compose version`, `docker run --rm hello-world`
- [ ] Confirm Docker service is enabled on boot: `systemctl enable --now docker`
- [ ] **Note:** `scripts/deploy/vps-bootstrap.sh` deliberately doesn't install Docker
      (the web app doesn't need it). This is a new runtime concern, additive.
- [ ] **Skip this step entirely if Step 0 found Docker already present.**

### Step 2 — Ensure `/opt/Bilun` is at `main` HEAD
- [ ] `cd /opt/Bilun && git fetch && git status`
- [ ] If behind `main`: `git pull origin main`
- [ ] Verify the agent infra is present (these are the load-bearing paths for
      the smoke test):
      - `ls /opt/Bilun/scripts/agent/sandbox/Dockerfile` — must exist
      - `ls /opt/Bilun/agents/reimbursement/{AGENTS.md,system-prompt.md,run_checks.sh}` — must exist
      - `ls /opt/Bilun/scripts/agent/memory/{config,load,save}.py` — must exist
- [ ] If any are missing → abort; the checkout is in a bad state and the smoke
      test can't proceed. Surface to user.
- [ ] Confirm HEAD commit hash and record it in Review section.

### Step 3 — Build the sandbox image on the VPS
- [ ] `cd /opt/Bilun/scripts/agent/sandbox`
- [ ] Read `Dockerfile` and confirm the base image reference
      (`ghcr.io/openhands/agent-server:1.36.0-python` per investigation)
- [ ] Build:
      ```bash
      docker build -t bilun/agent-server:1.36.0-bilun .
      ```
- [ ] **Expected:** first build takes 10-25 min (openhands base pull + torch CPU
      wheel install + mem0ai + sentence-transformers). Subsequent builds use cache.
- [ ] Verify image exists: `docker images bilun/agent-server`
- [ ] **Risk:** if the build OOMs or runs out of disk → abort, report to user.
      torch CPU wheel compilation is the usual culprit; the Dockerfile pins CPU
      torch so this should be a wheel download, not a compile.

### Step 4 — Prepare secrets
The agent needs the Z-API key. Decision needed (see Open Questions below) on
how to supply it.

- [ ] Confirm approach for `Z_API_KEY`:
      - Option A (simpler, this round): pass via `-e Z_API_KEY=...` on the
        `docker run` line. Key visible in `docker inspect` and shell history.
      - Option B (cleaner): write to `/opt/Bilun/agents/.env` on the VPS
        (gitignored, chmod 600) and use `--env-file`.
- [ ] Confirm the user has a raw Z-API key (NOT the ZCode OAuth token — those
      are incompatible; see `openhands-install-plan.md:23`)
- [ ] If user doesn't have a raw key, STOP — they need to generate one at z.ai

### Step 5 — Lock down port 3001, then launch OpenHands app container

**This step has TWO mandatory sub-parts. Do not run the `docker run` until 5a
is complete — exposing an unauthenticated agent UI with a Docker socket on a
public IP is a P0 security risk (anyone who finds the IP gets a free
container-spawning host + reads the Z-API key).**

#### 5a — ufw restrict port 3001 to the laptop's public IP (MANDATORY, before bind)
- [ ] From the laptop, look up current public IP: `curl -s ifconfig.me`
- [ ] On the VPS, ensure ufw is active: `ufw status` (if inactive, `ufw enable`
      — but FIRST verify SSH (port 22) is allowed to avoid lockout:
      `ufw allow 22/tcp`)
- [ ] Allow 3001 ONLY from the laptop IP:
      `ufw allow from <laptop-public-ip> to any port 3001 proto tcp`
- [ ] Verify the rule: `ufw status numbered | grep 3001`
- [ ] **Do not proceed to 5b until this rule is confirmed in place.**

#### 5b — Launch the container with dual-mount + iteration cap + fresh pull
Mirror the laptop setup (`openhands-install-plan.md:115`) on the VPS, with the
corrections from review:

- [ ] Run:
      ```bash
      docker run -d --rm \
        -e LOG_ALL_EVENTS=true \
        -e SANDBOX_VOLUMES=/opt/Bilun:/workspace/bilun:ro,/opt/Bilun/reports/agent:/workspace/bilun/reports/agent:rw \
        -e SANDBOX_USER_ID=1000 \
        -e MAX_ITERATIONS=30 \
        -e Z_API_KEY=<key-from-step-4> \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v /root/.openhands:/.openhands \
        -p 3001:3000 \
        --add-host host.docker.internal:host-gateway \
        --pull=always \
        --name openhands-app \
        docker.openhands.dev/openhands/openhands:latest
      ```
- [ ] **Mount explanation (the reviewer's fix #1):**
      - `/opt/Bilun:/workspace/bilun:ro` — repo read-only, the propose-don't-execute
        enforcement. Physical guarantee, not just prompt instruction.
      - `/opt/Bilun/reports/agent:/workspace/bilun/reports/agent:rw` — writable
        subdirectory so the agent can write `reports/agent/reimbursement/findings-*.md`.
        This matches the laptop proof's dual-mount pattern; without it, Step 7's
        verification (report exists) would fail.
      - **Files land owned by uid 10001** (the sandbox user). Read-back requires
        either root on the VPS (we are root) or `setfacl -m u:1000:rwx` on the
        reports dir if a non-root user needs to retrieve them.
- [ ] **`MAX_ITERATIONS=30` rationale (reviewer's fix #3):** verified env var,
      default 100. Laptop runs hit 15-20; 30 gives headroom. Reframes Step 7's
      cap-exhaustion as "bump and retry" not "failure." (Caveat: GitHub issue
      #9344 documents a CLI-only 500-cap bug; does NOT apply to the Docker/
      agent-server path used here.)
- [ ] **`--pull=always` rationale (reviewer's fix #3):** avoids a stale `:latest`
      tag being reused from any prior local cache on the VPS.
- [ ] Verify the container is up: `docker ps | grep openhands-app`
- [ ] Verify the port responds from the VPS: `curl -sI http://localhost:3001`
      (expect 200/302)
- [ ] Verify the port is reachable from the laptop (ufw rule working):
      `curl -sI -m 10 http://165.245.243.183:3001`
- [ ] **Caveat from `openhands-install-plan.md:104-108`:** the sandbox runs as
      uid 10001 but Bilun is owned by root on the VPS — the `:ro` subdir mount
      sidesteps the permission clash (same fix as laptop). If permission errors
      appear, revisit.

### Step 6 — Configure LLM in the remote UI
- [ ] From local laptop, open `http://165.245.243.183:3001` in a browser
      (should work — ufw allows laptop IP in Step 5a)
- [ ] Settings → LLM → Advanced:
  - Base URL: `https://api.z.ai/api/coding/paas/v4`
  - Custom Model: `openai/glm-5.2`
        (**MUST include `openai/` prefix** — litellm requires it; bare `glm-5.2`
        fails with `LLMBadRequestError`. Lesson from `openhands-install-plan.md:103`)
  - API Key: the raw Z-API key
- [ ] Save settings; verify no error
- [ ] **Security posture now:** port 3001 is ufw-restricted to the laptop IP only.
      This is the minimum acceptable exposure. If the laptop's public IP changes
      (roaming, ISP rotation), update the ufw rule before reconnecting. For
      stronger isolation in follow-on plans: TLS + `LOCAL_BACKEND_API_KEY` token
      auth + Caddy reverse proxy (out of scope here).

### Step 7 — Run the Reimbursement agent (the actual smoke test)
- [ ] In the remote UI, start a new conversation
- [ ] Paste the contents of `agents/reimbursement/system-prompt.md` as the
      initial message (this is the role definition + day-1 work items)
- [ ] Watch the agent:
  1. Spawn a sandbox using `bilun/agent-server:1.36.0-bilun`
  2. Run `terminal` tool to execute `agents/reimbursement/run_checks.sh`
     (which runs `verification_loop.py` + `stale_clause_refs.py`)
  3. Read findings, write a report to `reports/agent/reimbursement/findings-<date>.md`
     (the `:rw` mount from Step 5b makes this possible)
- [ ] **If the agent hits MAX_ITERATIONS=30 (reviewer's fix #3):** this is
      expected on first runs (laptop Data role hit 15, Reimbursement-with-mem0
      hit 20). Reframe: bump `-e MAX_ITERATIONS=40`, restart the container,
      resume the conversation. NOT a verification failure.
- [ ] **Verification criteria (definition of done for the smoke test):**
  - Agent completes without hitting `MAX_ITERATIONS` cap (or cap is bumped and
    run completes)
  - A report file appears at `/opt/Bilun/reports/agent/reimbursement/findings-*.md`
    (verify via SSH — root can read uid 10001-owned files)
  - Report contains real findings with `file:line` citations (matches the
    established pattern from the laptop runs)
  - Z-API token usage is non-trivial but finite (a few $ worth)

### Step 8 — Capture findings, verify web app unharmed, tear down or leave running
- [ ] Copy the report off the VPS for review:
      `scp -i ~/.ssh/bilun_vps root@165.245.243.183:/opt/Bilun/reports/agent/reimbursement/findings-*.md ./`
- [ ] **Verify web app unharmed (verification criterion #5):**
      - `systemctl is-active bilun-backend bilun-frontend` → both `active`
      - `curl -sI https://app.bilun.tech/health` → 200
      - Diff current state against `/tmp/vps_state_before.txt` (Step 0.5) —
        the only new things should be `openhands-app` container + the sandbox
        container + the image in `docker images`. If anything else differs,
        investigate.
- [ ] Capture any new gotchas in `tasks/lessons.md`
- [ ] **Decision:** tear down the container (`docker stop openhands-app`) or
      leave running with ufw restriction. Default: tear down unless user says
      otherwise — the smoke test is the goal, not a permanent service.

## Open Questions (must resolve before or during execution)

1. **`Z_API_KEY` delivery method** (Step 4 Option A vs B). Need user's call.
   Recommendation: Option B (`/opt/Bilun/agents/.env`, chmod 600, `--env-file`)
   — keeps the key out of `docker inspect` and shell history at the cost of
   one extra file.

2. **Port 3001 exposure posture** — Step 5a makes ufw-restriction **mandatory**
   for this round. The remaining choice is tear-down-after (Step 8 default) vs
   leave-running. Default: tear down.

3. **VPS RAM/disk** — cannot be known until Step 0 runs. If short, the whole
   plan needs re-scoping (bigger VPS, or stay on laptop).

## Out of Scope (explicit)
- TLS / domain for the agent UI (raw HTTP on :3001, ufw-restricted)
- docker-compose (single `docker run` commands this round)
- mem0 Step 0/Step 4 wiring into `run_checks.sh`
- All 3 roles — Reimbursement only
- Cron / scheduler / automation
- Docker-in-Docker security hardening beyond "ufw-restricted port + dedicated box"
  (the Docker socket mount is still a real risk; acceptable for a smoke test on
  a dedicated box, NOT acceptable for long-term — documented as follow-up)
- CI integration for image builds
- Pushing the image to GHCR (building on VPS instead, per user choice)
- Hermes pilot (separate decision, see `openhands-vs-hermes-comparison.md`)

## Risks
- **VPS under-spec'd** — if RAM <4 GB free or disk <20 GB free, build/runtime
  will fail. Step 0 catches this before any write.
- **8 GB image build OOMs** — torch wheel install is the risk point. Mitigation:
  the Dockerfile pins CPU torch (wheel download, not compile).
- **Docker socket exposure** — mounting `/var/run/docker.sock` into the
  openhands-app container is a known production risk (agent can spawn sibling
  containers). Mitigated this round by ufw-restricting port 3001 to the laptop
  IP only (Step 5a). NOT mitigated for long-term — must switch to `remote`
  runtime or a dedicated sandbox host before any persistent deployment.
- **Token cost runaway** — if the agent loops, Z-API tokens burn. Mitigation:
  `MAX_ITERATIONS=30` env cap (Step 5b); monitor Z.ai dashboard.
- **Laptop IP rotation** — if the laptop's public IP changes, the ufw rule from
  Step 5a blocks the laptop too. Re-run 5a with the new IP.

## Verification criteria (definition of done)
1. `docker ps` on the VPS shows `openhands-app` Up + a spawned sandbox container
2. `curl -sI http://165.245.243.183:3001` from the laptop returns 200/302
3. Reimbursement agent completes a full run (MAX_ITERATIONS either not hit,
   or bumped-and-resumed per Step 7)
4. A findings report exists at `/opt/Bilun/reports/agent/reimbursement/findings-*.md`
   with real `file:line` citations (not placeholder text)
5. No regression to the running web app — `bilun-backend` / `bilun-frontend`
   still `active`; `https://app.bilun.tech/health` returns 200; VPS state diff
   against `/tmp/vps_state_before.txt` shows only expected additions
6. Lessons from any gotchas captured in `tasks/lessons.md`

## Review (to be filled in after execution)
<!-- When done, document:
     - VPS specs discovered in Step 0 (RAM/disk/OS)
     - Whether Docker was pre-installed (Step 1 skipped or run)
     - Actual image build time (Step 3)
     - Actual agent run time + Z-API token cost (Step 7)
     - Did MAX_ITERATIONS get hit? Bumped to what?
     - Report quality — real citations vs placeholder?
     - Web app health post-smoke (Step 8 verification #5)
     - Decision: torn down or left running
-->
