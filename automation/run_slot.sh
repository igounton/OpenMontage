#!/bin/bash
# One Mind-Blaining automation slot. Loaded by launchd at 09:00 and 17:00 local.
# Owns: kill-switch, single-instance lock, env, logging. Brain is run_slot.py.
set -uo pipefail

ROOT="/Users/isaacgounton/Desktop/DEV/Videos/OpenMontage"
cd "$ROOT" || exit 1

# launchd gives a bare PATH — add Homebrew (ffmpeg) and the user bin (claude, node).
export PATH="/opt/homebrew/bin:/usr/local/bin:/Users/isaacgounton/.local/bin:$HOME/bin:$PATH"

mkdir -p automation/logs
TS="$(date +%Y%m%d-%H%M%S)"
LOG="automation/logs/slot-$TS.log"
exec >>"$LOG" 2>&1
echo "==== slot start $(date) ===="

# --- kill switch -----------------------------------------------------------
if [[ -f automation/DISABLE ]]; then
  echo "automation/DISABLE present — skipping."; exit 0
fi

# --- single-instance lock (atomic mkdir; stale after 2h) -------------------
LOCK="automation/.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [[ -n "$(find "$LOCK" -maxdepth 0 -mmin +120 2>/dev/null)" ]]; then
    echo "stale lock (>2h) — reclaiming."; rmdir "$LOCK" 2>/dev/null; mkdir "$LOCK" || exit 0
  else
    echo "another slot is running — skipping."; exit 0
  fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# --- env (secrets never echoed) -------------------------------------------
set -a; source .env; set +a

# --- go --------------------------------------------------------------------
.venv/bin/python automation/run_slot.py "$@"
rc=$?
echo "==== slot end rc=$rc $(date) ===="
exit $rc
