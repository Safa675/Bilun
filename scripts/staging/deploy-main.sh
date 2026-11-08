#!/usr/bin/env bash
# Keep staging (app.bilun.tech) on the head of main. bilun-deploy-main.timer runs this as root every 5 minutes;
# installed as /usr/local/sbin/bilun-deploy-main (docs/operations/AI-RUNBOOK.md). When main has moved and its CI is
# green, it runs that commit's own scripts/staging/update.sh, which builds, switches and rolls back on failure.
# A commit whose CI is still running is tried on the next run. One whose CI failed is never deployed, and one whose
# update failed 3 times is left alone until main moves on, so staging stays on the last good commit.
set -Eeuo pipefail
ROOT=/opt/bilun-staging
GIT=(git --git-dir="$ROOT/repository.git")
FAILED=$ROOT/deploy-main.failed # "<sha> <failed updates>"
TRIES=3

"${GIT[@]}" fetch -q --no-tags git@github.com:Safa675/Bilun.git +refs/heads/main:refs/remotes/origin/main
SHA=$("${GIT[@]}" rev-parse --verify 'refs/remotes/origin/main^{commit}')
[[ $(cat "$ROOT/current/STAGING_SOURCE_SHA") != "$SHA" ]] || exit 0
failed_sha="" failures=0
[[ -r $FAILED ]] && read -r failed_sha failures <"$FAILED"
[[ $failed_sha == "$SHA" ]] || failures=0
((failures < TRIES)) || exit 0
# Another update (a manual one) holds the lock: try on the next run.
flock -n "$ROOT/update.lock" true || exit 0

CI=$(gh run list -R Safa675/Bilun --workflow ci.yml --commit "$SHA" --json status,conclusion -q '
  if length == 0 then "pending"
  elif any(.conclusion == "success") then "success"
  elif any(.status != "completed") then "pending"
  else "failed" end')
case $CI in
  pending) exit 0 ;;
  failed) echo "main $SHA: CI failed, staging stays on $(cat "$ROOT/current/STAGING_SOURCE_SHA")"; exit 0 ;;
esac

SCRIPT=$(mktemp)
trap 'rm -f "$SCRIPT"' EXIT
"${GIT[@]}" show "$SHA:scripts/staging/update.sh" >"$SCRIPT"
echo "main $SHA: CI green, updating staging"
if ! bash "$SCRIPT" "$SHA"; then
  echo "$SHA $((failures + 1))" >"$FAILED"
  exit 1
fi
rm -f "$FAILED"
