#!/usr/bin/env bash
#
# Weekly parkrun fetch, for cron on the Raspberry Pi.
#
# Fetches the athlete's full results, then commits and pushes them only if
# something actually changed (i.e. only when a new parkrun has appeared).
#
# Usage:  ./run_weekly.sh [athlete_id]

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATHLETE_ID="${1:-448437}"
PYTHON="$REPO_DIR/.venv/bin/python"
LOCK_FILE="$REPO_DIR/.run_weekly.lock"

cd "$REPO_DIR"

# Don't let a slow run overlap with the next scheduled one.
# (flock is standard on the Pi; absent on macOS, where we just skip the lock.)
if command -v flock >/dev/null 2>&1; then
    exec 9>"$LOCK_FILE"
    if ! flock -n 9; then
        echo "$(date '+%Y-%m-%dT%H:%M:%S') another run_weekly.sh is already running; exiting" >&2
        exit 0
    fi
fi

if [[ ! -x "$PYTHON" ]]; then
    echo "$(date '+%Y-%m-%dT%H:%M:%S') no virtualenv at $PYTHON — run the setup steps in SETUP.md" >&2
    exit 1
fi

"$PYTHON" parkrun_athlete.py --athlete-id "$ATHLETE_ID"

# Commit only the text data files; the .xlsx is gitignored because its bytes
# change on every run even when the results don't.
git add -A data/

if git diff --cached --quiet; then
    echo "$(date '+%Y-%m-%dT%H:%M:%S') no new parkrun data — nothing to commit"
    exit 0
fi

LATEST=$("$PYTHON" -c "
import json, sys
d = json.load(open('data/athlete_${ATHLETE_ID}.json'))
r = d['latest_run']
print(f\"{d['total_parkruns']} total — {r['event']} {r['date']} {r['time']}\")
")

git commit -q -m "parkrun data: ${LATEST}"
git push -q
echo "$(date '+%Y-%m-%dT%H:%M:%S') committed and pushed: ${LATEST}"
