# butler-skeleton — reference implementation

Minimal, dependency-free companion to the "Butler in a Repo" methodology document. Six plain-text templates, one heartbeat script, one validator, one scheduler template, and a contract test suite. Everything is Python 3 / bash standard library only.

## Layout

| file | role |
|---|---|
| `todo.md` | single todo source template |
| `hooks.md` | far-future hook table template (7-day scan window) |
| `receipts.jsonl` | append-only evidence ledger template (one synthetic example) |
| `lessons.jsonl` | lesson template (`candidate` until promoted) |
| `rules.md` | rule block template (precedence + revision history) |
| `MEMORY.md` | session-spine skeleton (identity / scope / gate vocabulary) |
| `heartbeat.sh` | validates the ledger, appends a hash-chained heartbeat receipt, summarizes open todos and due hooks; fail-closed on invalid or unwritable ledger |
| `receipt-validator.py` | schema + status-enum + `prev_hash` chain validation |
| `com.example.butler-heartbeat.plist` | launchd template (systemd / Task Scheduler equivalents are the same shape) |
| `tests/test_contract.py` | 19 contract tests |

## Run

```bash
# 1. contract tests
python3 -m unittest discover -s tests
# -> Ran 19 tests ... OK

# 2. one heartbeat run (append-only, hash-chained)
./heartbeat.sh
# -> [heartbeat] ok | open todos: 1 | due hooks: 0 | ledger receipts: 2

# 3. validate the ledger
python3 receipt-validator.py receipts.jsonl
# -> [ok] ledger valid

# 4. failure drills in an isolated root (never touch the shipped ledger)
D="$(mktemp -d)"; cp receipts.jsonl todo.md hooks.md "$D/"
BUTLER_ROOT="$D" BUTLER_ALERT_FILE="$D.alert" bash heartbeat.sh
# -> [heartbeat] ok ... (isolated copy still works)
printf 'corrupt\n' > "$D/receipts.jsonl"
BUTLER_ROOT="$D" BUTLER_ALERT_FILE="$D.alert" bash heartbeat.sh; echo "exit=$?"
# -> [heartbeat] ledger invalid -> fail-closed (alert: $D.alert)
# -> exit=1  (alert marker written to the path given by BUTLER_ALERT_FILE)
```

## Design notes (honest boundaries)

- **Single-writer assumption**: the ledger assumes one appending process at a time. Multi-process writers need an external lock; the skeleton deliberately omits one.
- **Append semantics**: one-line appends only. Atomicity per line is bounded by the filesystem; durability beyond that follows the backup chain, not this script.
- **Hash chain is tamper *evidence*, not tamper proof**: `prev_hash` detects breaks; an attacker with write access could re-chain. Independent sentinel copies provide the real drift detection.
- **`prev_hash` rule**: sha256 of the previous *logical* line (whitespace-stripped); the first entry carries no `prev_hash`, every later entry must carry the correct one (the validator rejects missing or wrong hashes).
- **Alert marker independence**: failure alerts go to `BUTLER_ALERT_FILE` (default `~/.butler-heartbeat-failures.log`), outside the ops root, so a read-only ledger directory does not kill the alarm — bounded by that path's own writability.
- **Fail-closed scope**: `heartbeat.sh` fails closed on its own ledger checks (invalid or unwritable ledger) and on missing or unreadable `todo.md`/`hooks.md`. It cannot prove other jobs ran — see the `cannot_claim` field on every receipt.
