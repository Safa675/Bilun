#!/usr/bin/env bash
# Update staging (app.bilun.tech) to a commit of main whose CI is green. Run on the VPS as root:
#   scripts/staging/update.sh [SHA]        (default: the head of main)
# It waits for a running CI job (never builds beside one), builds into a new release folder,
# switches `current`, restarts only the two staging units, rolls back if they do not come up,
# and keeps the last 3 releases. The old frozen pair (port 8001) must stay healthy and unrestarted.
set -Eeuo pipefail
ROOT=/opt/bilun-staging
GIT=(git --git-dir="$ROOT/repository.git")
UNITS=(bilun-staging-backend.service bilun-staging-frontend.service)
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
healthy() { curl -fsS --max-time 3 "$1" | python3 -c 'import json,sys; sys.exit(json.load(sys.stdin).get("status") != "ok")' 2>/dev/null; }
ram_ok() { (( $(awk '$1 == "MemAvailable:" {print $2}' /proc/meminfo) >= 4194304 )); }
old_pair() { systemctl show bilun-backend.service bilun-frontend.service -p MainPID --value | tr '\n' ' '; }
[[ $(id -u) == 0 ]] || die 'run as root on the VPS'

exec 9>"$ROOT/update.lock"; flock -n 9 || die 'another staging update is running'
exec 8>/root/.cache/bilun-land/bilun-ci-watcher.lock
flock -w 3600 8 || die 'a CI job held the runner for an hour; try again later'

"${GIT[@]}" fetch -q --no-tags git@github.com:Safa675/Bilun.git +refs/heads/main:refs/remotes/origin/main
SHA=$("${GIT[@]}" rev-parse --verify "${1:-refs/remotes/origin/main}^{commit}")
"${GIT[@]}" merge-base --is-ancestor "$SHA" refs/remotes/origin/main || die "$SHA is not on main"
CI=$(gh run list -R Safa675/Bilun --workflow ci.yml --commit "$SHA" --json conclusion -q '[.[].conclusion] | index("success") != null')
[[ $CI == true ]] || die "main CI is not green for $SHA"

OLD_RELEASE=$(realpath -e "$ROOT/current"); OLD_CACHE=$(realpath -e "$ROOT/cache-current.duckdb")
OLD_SHA=$(cat "$OLD_RELEASE/STAGING_SOURCE_SHA")
[[ $OLD_SHA != "$SHA" ]] || { echo "staging already runs $SHA"; exit 0; }
OLD_PAIR=$(old_pair)
ram_ok && healthy http://127.0.0.1:8001/health || die 'old pair unhealthy or RAM below 4 GiB; nothing changed'

STAMP=$SHA-$(date -u +%Y%m%dT%H%M%S)
RELEASE=$ROOT/releases/$STAMP CACHE=$OLD_CACHE REBUILD=0
"${GIT[@]}" worktree add -q --detach "$RELEASE" "$SHA"
echo "$SHA" >"$RELEASE/STAGING_SOURCE_SHA"
if ! "${GIT[@]}" diff --quiet "$OLD_SHA" "$SHA" -- data src/bilun/domain src/bilun/cache src/bilun/shared \
    src/bilun/db scripts/bilun scripts/sut 'raw data' pyproject.toml requirements.txt requirements-ci.lock; then
  REBUILD=1 CACHE=$ROOT/caches/$STAMP.duckdb
fi
echo "build $SHA (cache rebuild: $REBUILD), log $ROOT/logs/build-$STAMP.log"
SCOPE=bilun-staging-build-${STAMP: -15}
systemd-run --scope --quiet --unit "$SCOPE" -p MemoryMax=8G nice -n 10 ionice -c3 \
  bash "$RELEASE/scripts/staging/build.sh" "$RELEASE" "$CACHE" "$REBUILD" >"$ROOT/logs/build-$STAMP.log" 2>&1 &
BUILD=$!
while kill -0 $BUILD 2>/dev/null; do
  ram_ok || { systemctl kill -s KILL "$SCOPE.scope"; die 'RAM fell below 4 GiB; build stopped, staging unchanged'; }
  sleep 2
done
wait $BUILD || die "build failed; staging unchanged; log $ROOT/logs/build-$STAMP.log"

switch() { ln -sfnT "$2" "$ROOT/cache-current.duckdb"; ln -sfnT "$1" "$ROOT/current"; systemctl restart "${UNITS[@]}"; }
up() { for _ in $(seq 60); do healthy http://127.0.0.1:8101/health && curl -fsS -o /dev/null --max-time 3 http://127.0.0.1:3100/login && return 0; sleep 2; done; return 1; }
switch "$RELEASE" "$CACHE"
if ! up; then
  switch "$OLD_RELEASE" "$OLD_CACHE"
  die "new staging did not come up; restored $OLD_SHA (release $RELEASE kept for inspection)"
fi
[[ $(old_pair) == "$OLD_PAIR" ]] && healthy http://127.0.0.1:8001/health || die 'old pair restarted or unhealthy after the switch'

for old in $(ls -1dt "$ROOT"/releases/* | tail -n +4); do "${GIT[@]}" worktree remove --force "$old"; done
keep=$(for r in "$ROOT"/releases/*; do basename "$r"; done)
for cache in "$ROOT"/caches/*.duckdb; do
  [[ $cache == "$(realpath -e "$ROOT/cache-current.duckdb")" || $keep == *"$(basename "$cache" .duckdb)"* ]] || rm -f -- "$cache"
done
echo "READY staging=$SHA release=$RELEASE cache=$CACHE"
