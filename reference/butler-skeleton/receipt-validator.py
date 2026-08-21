#!/usr/bin/env python3
"""receipt-validator.py — minimal receipt ledger validator (stdlib only).

Checks every line of a receipts.jsonl:
  1. valid JSON object
  2. required keys present: ts, event_id, action, status
  3. status is one of: done | failed | skipped
  4. optional fields have the right types (exit_code int, artifact_hash str)
  5. prev_hash chain: when present, it must equal sha256 of the previous
     logical line (whitespace-stripped); first entry must not carry prev_hash

Exit 0 = valid; exit 1 = invalid (message on stderr).
Usage: python3 receipt-validator.py <receipts.jsonl>
"""
import hashlib
import json
import sys

REQUIRED = ("ts", "event_id", "action", "status")
STATUSES = {"done", "failed", "skipped"}


def validate(path: str) -> list:
    errors = []
    prev_raw = None
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {lineno}: invalid JSON: {exc}")
                prev_raw = None
                continue
            if not isinstance(obj, dict):
                errors.append(f"line {lineno}: not a JSON object")
                prev_raw = None
                continue
            missing = [k for k in REQUIRED if k not in obj]
            if missing:
                errors.append(f"line {lineno}: missing keys {missing}")
            if obj.get("status") not in STATUSES:
                errors.append(f"line {lineno}: status {obj.get('status')!r} not in {sorted(STATUSES)}")
            if "exit_code" in obj and not isinstance(obj.get("exit_code"), int):
                errors.append(f"line {lineno}: exit_code must be int")
            if "prev_hash" in obj:
                if prev_raw is None:
                    errors.append(f"line {lineno}: first entry must not carry prev_hash")
                else:
                    want = hashlib.sha256(prev_raw.encode("utf-8")).hexdigest()
                    if obj["prev_hash"] != want:
                        errors.append(f"line {lineno}: prev_hash mismatch (got {obj['prev_hash'][:12]}…, want {want[:12]}…)")
            elif prev_raw is not None:
                errors.append(f"line {lineno}: missing prev_hash (chain required from the second entry onward)")
            prev_raw = line
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: receipt-validator.py <receipts.jsonl>", file=sys.stderr)
        return 2
    errors = validate(sys.argv[1])
    if errors:
        for e in errors:
            print(f"[invalid] {e}", file=sys.stderr)
        return 1
    print("[ok] ledger valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
