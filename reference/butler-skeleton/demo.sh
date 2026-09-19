#!/bin/bash
# demo.sh — one-command, self-contained demo of the "Butler in a Repo" skeleton.
#
# Why this exists: the contract tests and the heartbeat are two commands in a
# subdirectory of a repository whose front page is about something else. That is
# enough friction that most readers never run anything — and a pattern nobody ran
# is a pattern nobody can vouch for. This script is the front door.
#
# What it does, in a THROWAWAY COPY so your checkout is never modified:
#   1. runs the 19 contract tests
#   2. runs one heartbeat (append-only, hash-chained)
#   3. deliberately breaks the ledger and shows the heartbeat failing CLOSED
#   4. prints the resulting ledger tail
#
# Exit code is 0 only if every step behaved as claimed.
#
# Requirements: bash + python3 (standard library only). No install, no network.
set -u

SRC="$(cd "$(dirname "$0")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "demo.sh: python3 is required (standard library only) and was not found on PATH." >&2
  exit 2
fi

TMPROOT="$(mktemp -d 2>/dev/null)" || { echo "demo.sh: could not create a temp dir" >&2; exit 2; }
# Named subdir on purpose: the heartbeat records its root in the receipt's `scope`
# field, so a readable name keeps the demo output legible when quoted in a README.
TMP="$TMPROOT/butler-skeleton-demo"
trap 'rm -rf "$TMPROOT"' EXIT
mkdir -p "$TMP" || exit 2
cp -R "$SRC"/. "$TMP"/ 2>/dev/null || { echo "demo.sh: could not copy the skeleton to $TMP" >&2; exit 2; }
cd "$TMP" || exit 2

FAILED=0
step() { printf '\n=== %s ===\n' "$1"; }
ok()   { printf '  [ok] %s\n' "$1"; }
bad()  { printf '  [FAIL] %s\n' "$1"; FAILED=1; }

step "1/4  contract tests (19 expected)"
if OUT="$(python3 -m unittest discover -s tests 2>&1)"; then
  N="$(printf '%s' "$OUT" | grep -oE 'Ran [0-9]+ test' | grep -oE '[0-9]+' | head -1)"
  ok "all tests passed (Ran ${N:-?} tests)"
else
  printf '%s\n' "$OUT" | tail -5
  bad "contract tests did not pass"
fi

step "2/4  one heartbeat run (append-only, hash-chained)"
if OUT="$(./heartbeat.sh 2>&1)"; then
  printf '%s\n' "$OUT" | sed 's/^/  /'
  ok "heartbeat exited 0"
else
  printf '%s\n' "$OUT" | sed 's/^/  /'
  bad "heartbeat exited non-zero on a valid ledger"
fi

step "3/4  fail-closed proof (corrupt the ledger, heartbeat MUST refuse)"
cp receipts.jsonl receipts.jsonl.bak
printf '%s\n' '{"ts":"2000-01-01T00:00:00+0000","action":"tampered","prev_hash":"deadbeef"}' >> receipts.jsonl
if ./heartbeat.sh >/dev/null 2>&1; then
  bad "heartbeat exited 0 on a CORRUPT ledger — this is the exact failure the pattern exists to prevent"
else
  ok "heartbeat refused the corrupt ledger (non-zero exit, as contracted)"
fi
mv receipts.jsonl.bak receipts.jsonl

step "4/4  ledger tail (append-only evidence)"
tail -3 receipts.jsonl | sed 's/^/  /'

printf '\n'
if [ "$FAILED" -eq 0 ]; then
  echo "DEMO OK — tests pass, heartbeat appends, and a corrupt ledger fails closed."
  exit 0
fi
echo "DEMO FAILED — see the [FAIL] lines above." >&2
exit 1
