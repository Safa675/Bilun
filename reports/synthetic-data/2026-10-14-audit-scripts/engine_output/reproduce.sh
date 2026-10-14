#!/usr/bin/env bash
# Re-runs the whole engine-output audit: engine (in-process, under strace) -> isolation checks -> analyses.
# Everything is written under this script's folder; the repo is only read.
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
OUT="$S/out"
REPO=/home/safa/Documents/Bilun
PY="$REPO/.venv/bin/python"

touch "$S/marker_before"
(cd "$REPO" && git status --porcelain --ignored=matching | grep -v "^!! .*node_modules" || true) > "$S/git_status_before.txt"

strace -f -qq -e trace=open,openat,creat,mkdir,mkdirat,unlink,unlinkat,rename,renameat,renameat2,truncate \
  -o "$S/strace.log" env PYTHONDONTWRITEBYTECODE=1 "$PY" -B "$S/run_reports.py" "$OUT" | tail -2

echo "== isolation checks"
echo "syscalls touching raw data/ or ilay_validation: $(grep -c -e 'raw data' -e 'ilay_validation' "$S/strace.log" || true)"
echo "successful write/create syscalls outside scratch: $(grep -E 'O_WRONLY|O_RDWR|O_CREAT|O_TRUNC|O_APPEND|mkdir|unlink|rename|creat\(|truncate' "$S/strace.log" | grep -v "$S" | grep -v '/dev/' | grep -vc '= -1 E' || true)"
echo "synthetic files opened:"; grep -o '"/home/safa/Documents/Bilun/data/synthetic/[^"]*"' "$S/strace.log" | sort -u
(cd "$REPO" && git status --porcelain --ignored=matching | grep -v "^!! .*node_modules" || true) > "$S/git_status_after.txt"
diff -q "$S/git_status_before.txt" "$S/git_status_after.txt" && echo "git status incl. ignored: unchanged"
echo "repo files newer than run start: $(find "$REPO" \( -path "$REPO/raw data" -o -path '*/ilay_validation' -o -path '*/node_modules' -o -path '*/.git' \) -prune -o -newer "$S/marker_before" -print 2>/dev/null | wc -l)"

echo "== analyses"
"$PY" -I "$S/analyze.py" "$OUT" > "$S/analysis_stdout.txt" 2>&1
"$PY" -I "$S/followup.py" "$OUT" > "$S/followup_stdout.txt" 2>&1
"$PY" -I "$S/followup2.py" "$OUT" > "$S/followup2_stdout.txt" 2>&1
"$PY" -I "$S/followup3.py" "$OUT" > "$S/followup3_stdout.txt" 2>&1
"$PY" -I "$S/tier_a.py" "$OUT" > "$S/tier_a_stdout.txt" 2>&1
"$PY" -I "$S/followup4.py" "$OUT" > "$S/followup4_stdout.txt" 2>&1
sha256sum "$OUT"/*.json "$OUT"/analysis/* | sed "s#$S/##" > "$S/checksums.txt"
echo "done; outputs in $OUT and $S/*_stdout.txt"
