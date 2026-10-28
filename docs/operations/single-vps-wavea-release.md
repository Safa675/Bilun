# Single-VPS Wave A release (archived)

This runbook described the strict paired-release lane: `paired_release prepare|status|activate|rollback` for the backend/frontend pair on loopback 8001/3000, its signed Wave A activation receipt and its rollback. The lane was deleted on 2026-10-28; the git tag `archive/strict-lane` holds the scripts, the tests and the full text of this runbook (`git show archive/strict-lane:docs/operations/single-vps-wavea-release.md`).

What is still running: the pair it last released (`5c89ed53`, ports 8001/3000) runs from its own bundle under `/root` and receives no traffic; retiring it is a later step. The current staging update is in [AI-RUNBOOK.md](AI-RUNBOOK.md) and [RELEASE-LANES.md](RELEASE-LANES.md).
