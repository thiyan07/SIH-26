#!/usr/bin/env bash
# Chained background runner: wait for index -> discovery -> geoapify -> reports.
# All steps read state files under data/erode/cache/ so each is resumable.
set -u
cd "$(dirname "$0")/../.."   # apps/api
PY=./.venv/bin/python
INDEX=data/erode/erode_index.json
LOG=/tmp/erode_chain.log

echo "[chain] $(date +%T) start; waiting for $INDEX" > "$LOG"

for i in $(seq 1 600); do
  if [[ -f "$INDEX" ]]; then
    echo "[chain] $(date +%T) index ready ($i*10s)" >> "$LOG"
    break
  fi
  sleep 10
done

if [[ ! -f "$INDEX" ]]; then
  echo "[chain] $(date +%T) TIMEOUT waiting for index" >> "$LOG"
  exit 1
fi

echo "[chain] $(date +%T) running discovery" >> "$LOG"
$PY -m scripts.erode.run_pipeline --discovery >> "$LOG" 2>&1
echo "[chain] $(date +%T) discovery done" >> "$LOG"

echo "[chain] $(date +%T) running geoapify" >> "$LOG"
$PY -m scripts.erode.run_pipeline --geoapify >> "$LOG" 2>&1
echo "[chain] $(date +%T) geoapify done" >> "$LOG"

echo "[chain] $(date +%T) running reports" >> "$LOG"
$PY -m scripts.erode.run_pipeline --reports >> "$LOG" 2>&1
echo "[chain] $(date +%T) reports done" >> "$LOG"

echo "[chain] $(date +%T) ALL DONE" >> "$LOG"