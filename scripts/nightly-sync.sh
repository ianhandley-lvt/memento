#!/bin/sh
# Nightly Memento sync: pulls new Claude/Cursor sessions and new RAW/Wiki
# knowledge-base content into the shared artifact store + index. Idempotent —
# every step dedups by content hash, so a re-run over unchanged content costs
# nothing (no Cursor calls, no index churn).
#
# Not Slack-integrated on purpose: an unattended cron job must never
# auto-send a message on Ian's behalf. Problems surface as a local macOS
# notification plus a full log, for him to read and act on himself.

set -u

MEMENTO="$HOME/.local/bin/memento"
LOG_DIR="$HOME/.local/share/memento/logs"
LOG_FILE="$LOG_DIR/nightly-sync-$(date +%Y-%m-%d).log"
mkdir -p "$LOG_DIR"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOG_FILE"
}

run_step() {
  description="$1"
  shift
  log "START: $description"
  output=$("$@" 2>&1)
  status=$?
  printf '%s\n' "$output" >> "$LOG_FILE"
  log "END ($status): $description"
  printf '%s' "$output"
  return "$status"
}

notify() {
  osascript -e "display notification \"$1\" with title \"Memento nightly sync\"" >/dev/null 2>&1 || true
}

log "=== nightly sync starting ==="

run_step "import Claude sessions (all projects)" "$MEMENTO" import-sessions --source claude --all-projects >/dev/null
run_step "import Cursor conversations" "$MEMENTO" import-sessions --source cursor >/dev/null

# Wiki import (free, deterministic) — kept for continuity with any hand-edited
# Wiki content. Add a line here if another KB's Wiki should also sync.
run_step "import lvcore Wiki" "$MEMENTO" import-markdown-kb \
  "$HOME/src/personal/second-brain/lvcore_kb/Wiki" \
  --knowledge-base-id lvcore --project-id lvcore --temporal-scope durable >/dev/null
run_step "import beacon Wiki" "$MEMENTO" import-markdown-kb \
  "$HOME/src/personal/second-brain/beacon_kb/Wiki" \
  --knowledge-base-id beacon --project-id beacon --temporal-scope durable >/dev/null

# RAW import (spends Cursor quota, but only for genuinely new/changed files —
# unchanged sources are skipped by content hash before any call is made).
raw_lvcore=$(run_step "import lvcore RAW sources" "$MEMENTO" import-raw-sources \
  "$HOME/src/personal/second-brain/lvcore_kb/RAW" \
  --knowledge-base-id lvcore-raw --project-id lvcore)
raw_beacon=$(run_step "import beacon RAW sources" "$MEMENTO" import-raw-sources \
  "$HOME/src/personal/second-brain/beacon_kb/RAW" \
  --knowledge-base-id beacon-raw --project-id beacon)

# Surface anything that needs a human: real failures immediately, and
# pending_retry only once it's stale (younger than 48h self-heals on its own
# on tomorrow's run — see run_extraction's hash-based re-candidacy, no code
# needed for that case).
problems=""
for batch_output in "$raw_lvcore" "$raw_beacon"; do
  blocked=$(printf '%s' "$batch_output" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('blocked',0)+d.get('failed',0))" 2>/dev/null || echo 0)
  if [ "${blocked:-0}" != "0" ] && [ "${blocked:-0}" != "" ]; then
    problems="${problems}${blocked} blocked/failed source(s); "
  fi
done

stale_pending=$(find "$HOME/.local/share/memento/artifacts" -name job_status.json -mtime +2 2>/dev/null | wc -l | tr -d ' ')
if [ "$stale_pending" != "0" ]; then
  problems="${problems}${stale_pending} source(s) stuck pending_retry/blocked for 48h+; "
fi

if [ -n "$problems" ]; then
  log "PROBLEMS: $problems"
  notify "$problems See $LOG_FILE"
else
  log "no problems"
fi

log "=== nightly sync finished ==="
