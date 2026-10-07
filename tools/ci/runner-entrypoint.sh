#!/usr/bin/env bash
set -euo pipefail
umask 077
# Registration and diagnostics are tmpfs-only; the container cannot swap.
test "$(cat /sys/fs/cgroup/memory.swap.max)" = "0"
cp -a /opt/actions-runner/. /runner/
mkdir -p "$HOME/.cache"
ln -s /workspace /runner/_work
export BILUN_CI_LOCK_SHA256="$(sha256sum /opt/requirements-ci.lock | cut -d ' ' -f 1)"
IFS= read -r jitconfig
exec /runner/bin/Runner.Listener run --jitconfig "$jitconfig"
