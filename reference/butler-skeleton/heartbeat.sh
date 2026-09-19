#!/bin/bash
# heartbeat.sh — minimal butler heartbeat (reference implementation).
#
# What it does:
#   1. validates the receipt ledger (fail-closed: invalid ledger -> exit 1)
#   2. appends one heartbeat receipt (single-line append)
#   3. prints a one-line summary (open todos, due hooks in next 7 days)
#
# Contract: non-zero exit code means failure and must be surfaced, never swallowed.
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="${BUTLER_ROOT:-$SCRIPT_DIR}"
VALIDATOR="$SCRIPT_DIR/receipt-validator.py"
TODO="$ROOT/todo.md"
HOOKS="$ROOT/hooks.md"
RECEIPTS="$ROOT/receipts.jsonl"
# Alert marker lives OUTSIDE the ops root so a read-only ledger dir does not kill the alarm.
ALERT="${BUTLER_ALERT_FILE:-$HOME/.butler-heartbeat-failures.log}"
STAMP=$(date '+%Y-%m-%dT%H:%M:%S%z')

fail_closed() {
  local msg="$1"
  printf '%s heartbeat failed: %s\n' "$STAMP" "$msg" >> "$ALERT" 2>/dev/null
  echo "[heartbeat] $msg -> fail-closed (alert: $ALERT)" >&2
  exit 1
}

python3 "$VALIDATOR" "$RECEIPTS" >/dev/null 2>&1 || fail_closed "ledger invalid"

# input gates: never claim "todo+hooks read" unless both files exist AND are readable
[ -r "$TODO" ] || fail_closed "todo.md missing or unreadable"
[ -r "$HOOKS" ] || fail_closed "hooks.md missing or unreadable"

# single-line append; hash-chain the previous LOGICAL line (last non-empty, whitespace-stripped; first entry carries no prev_hash)
PREV_HASH=""
PREV_LINE=$(awk 'NF { last=$0; sub(/^[[:space:]]+/, "", last); sub(/[[:space:]]+$/, "", last) } END { print last }' "$RECEIPTS")
if [ -n "$PREV_LINE" ]; then
  # 2026-09-20: portable SHA-256. `shasum` is a Perl script and is not guaranteed
  # on every Linux image; `sha256sum` is coreutils. Same digest either way, so the
  # existing hash chain is unaffected — only the choice of tool changed.
  if command -v sha256sum >/dev/null 2>&1; then
    PREV_HASH=$(printf '%s' "$PREV_LINE" | sha256sum | cut -d' ' -f1)
  else
    PREV_HASH=$(printf '%s' "$PREV_LINE" | shasum -a 256 | cut -d' ' -f1)
  fi
fi
BASE="{\"ts\":\"$STAMP\",\"event_id\":\"heartbeat-$(date +%s)\",\"action\":\"heartbeat\",\"scope\":\"$ROOT\",\"status\":\"done\",\"input_evidence\":\"ledger validated;todo+hooks read\",\"exit_code\":0,\"validator\":\"operator-next-run\",\"validation_result\":\"[ok] ledger valid\",\"cannot_claim\":\"this heartbeat does not prove any other job ran\""
if [ -n "$PREV_HASH" ]; then
  LINE="${BASE},\"prev_hash\":\"$PREV_HASH\"}"
else
  LINE="${BASE}}"
fi
printf '%s\n' "$LINE" >> "$RECEIPTS" || fail_closed "ledger unwritable"

OPEN_TODOS=$(grep -c '^- \[ \]' "$TODO")

# due hooks: ISO-date rows within the next 7 days (inclusive), status not done
TODAY=$(date '+%Y-%m-%d')
# 2026-09-20: `date -v+7d` is BSD/macOS-only and fails outright on GNU date, which
# made the whole heartbeat unusable on Linux. Probe once and fall back to `-d`.
if date -v+7d '+%Y-%m-%d' >/dev/null 2>&1; then
  PLUS7=$(date -v+7d '+%Y-%m-%d')
else
  PLUS7=$(date -d '+7 days' '+%Y-%m-%d')
fi
DUE=$(awk -F'|' -v t="$TODAY" -v p="$PLUS7" '
  NR<=2 { next }
  { d=$2; gsub(/[[:space:]]/,"",d); s=$5; gsub(/[[:space:]]/,"",s) }
  d ~ /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/ && d >= t && d <= p && s !~ /done|已办/ { print $2" |"$3" |"$4 }
' "$HOOKS" | head -3)
DUE_COUNT=0
[ -n "$DUE" ] && DUE_COUNT=$(printf '%s\n' "$DUE" | wc -l | tr -d ' ')

echo "[heartbeat] ok | open todos: $OPEN_TODOS | due hooks: $DUE_COUNT | ledger receipts: $(awk 'NF { n++ } END { print n+0 }' "$RECEIPTS")"
if [ -n "$DUE" ]; then
  printf '%s\n' "$DUE" | sed 's/^/  due: /'
fi
