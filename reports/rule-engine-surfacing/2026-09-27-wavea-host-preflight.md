# Wave A release host preflight (read-only)

Inspected 2026-09-27 UTC. No service, proxy, database, release pointer, or
production configuration was changed during this check.

- The current production checkout at `/opt/Bilun` is `bbf9acafc164aa51579e573ea8ac5f5bc1a34ecd` (merged PR #96). A frontend `current` link points to retained release `05114abe4e5176966e55463ee42045bc20022f0d`, but **that link is not the serving frontend**.
- `bilun-backend`, `bilun-frontend`, and `caddy` are running. Caddy sends `/api/*` and `/health` to loopback port 8001, and other requests to loopback port 3000. The public `/health` returned `status=ok` and `cache_ready=true`; those fields alone do not attest code or source identity.
- The host reports 23 GiB RAM (about 14 GiB available), no swap, eight logical CPUs, and about 237 GiB free on the filesystem containing the checkout/cache. The current DuckDB file is about 13 MiB. These are a snapshot, not a measured candidate build/recovery budget.
- The actual `bilun-frontend.service` runs `/usr/bin/npx next start -p 3000` with working directory `/opt/Bilun/frontend`; its live process cwd confirms that path. That build's ID is `MeCog4EdmVoTrRgQFeSuy`, whereas the retained `current` symlink has build ID `yeQsX56V2hl2SVbLDFyve`. The versioned frontend `releases`, `builds`, and `manifests` directories therefore do not presently determine serving identity. Symlink switching alone cannot activate or roll back the frontend. The release gate must migrate the service definition to the prepared versioned release under the traffic barrier, verify the actual served build and static asset routing, and preserve the old directory/build as an exact rollback target.
- The backend executes directly from `/opt/Bilun` with `.env` and a fixed live cache path. The gate must prepare a separate backend checkout and cache, then coordinate Caddy traffic, both services, and exact rollback targets before changing the public tuple.

The Caddy configuration has no current maintenance barrier. A candidate barrier
must be implemented and rehearsed on an isolated proxy/config before any live
activation. The 25-minute deploy job and current frontend-first workflow do
not satisfy the accepted Wave A gate; they remain unchanged by this preflight.
