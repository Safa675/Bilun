# Wave A release host preflight (read-only)

Inspected 2026-09-27 UTC. No service, proxy, database, release pointer, or
production configuration was changed during this check.

- The current production checkout at `/opt/Bilun` is `bbf9acafc164aa51579e573ea8ac5f5bc1a34ecd` (merged PR #96). The frontend `current` link points to retained release `05114abe4e5176966e55463ee42045bc20022f0d`.
- `bilun-backend`, `bilun-frontend`, and `caddy` are running. Caddy sends `/api/*` and `/health` to loopback port 8001, and other requests to loopback port 3000. The public `/health` returned `status=ok` and `cache_ready=true`; those fields alone do not attest code or source identity.
- The host reports 23 GiB RAM (about 14 GiB available), no swap, eight logical CPUs, and about 237 GiB free on the filesystem containing the checkout/cache. The current DuckDB file is about 13 MiB. These are a snapshot, not a measured candidate build/recovery budget.
- The frontend already has versioned `releases`, `builds`, and `manifests` directories plus a `current` symlink. The backend currently executes directly from `/opt/Bilun` with `.env` and a fixed live cache path. The release gate must prepare a separate backend checkout and cache, then coordinate Caddy traffic, both services, and exact rollback targets before changing the public tuple.

The Caddy configuration has no current maintenance barrier. A candidate barrier
must be implemented and rehearsed on an isolated proxy/config before any live
activation. The 25-minute deploy job and current frontend-first workflow do
not satisfy the accepted Wave A gate; they remain unchanged by this preflight.
