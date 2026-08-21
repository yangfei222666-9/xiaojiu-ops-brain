#!/usr/bin/env python3
"""Contract tests for the butler reference skeleton (stdlib unittest only).

Covers:
  - receipt schema: valid line, missing keys, bad status enum, non-JSON line,
    empty file, first-line prev_hash forbidden
  - prev_hash chain: intact chain passes, broken chain fails
  - heartbeat fail-closed: corrupt ledger -> exit 1 + heartbeat-failures.log
  - heartbeat success path: appends a valid, hash-chained receipt
  - hook 7-day window boundary: +6d due, +8d not due

Run: python3 -m unittest discover -s tests
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATOR = os.path.join(ROOT, "receipt-validator.py")
HEARTBEAT = os.path.join(ROOT, "heartbeat.sh")


def make_line(**overrides):
    obj = {
        "ts": "2026-08-21T12:00:00+0800",
        "event_id": "evt-1",
        "action": "test",
        "status": "done",
    }
    obj.update(overrides)
    return json.dumps(obj, ensure_ascii=False)


class ValidatorTests(unittest.TestCase):
    def _run(self, content):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            fh.write(content)
            path = fh.name
        try:
            proc = subprocess.run(
                [sys.executable, VALIDATOR, path], capture_output=True, text=True
            )
            return proc.returncode, proc.stderr
        finally:
            os.unlink(path)

    def test_empty_file_is_valid(self):
        code, _ = self._run("")
        self.assertEqual(code, 0)

    def test_valid_line_passes(self):
        code, _ = self._run(make_line() + "\n")
        self.assertEqual(code, 0)

    def test_missing_keys_rejected(self):
        code, err = self._run('{"ts": "x"}\n')
        self.assertEqual(code, 1)
        self.assertIn("missing keys", err)

    def test_bad_status_rejected(self):
        code, err = self._run(make_line(status="maybe") + "\n")
        self.assertEqual(code, 1)
        self.assertIn("status", err)

    def test_non_json_line_rejected(self):
        code, err = self._run("not json\n")
        self.assertEqual(code, 1)
        self.assertIn("invalid JSON", err)

    def test_first_line_prev_hash_forbidden(self):
        code, err = self._run(make_line(prev_hash="0" * 64) + "\n")
        self.assertEqual(code, 1)
        self.assertIn("first entry", err)

    def test_intact_chain_passes(self):
        l1 = make_line()
        l2 = make_line(event_id="evt-2", prev_hash=hashlib.sha256(l1.encode()).hexdigest())
        code, _ = self._run(l1 + "\n" + l2 + "\n")
        self.assertEqual(code, 0)

    def test_broken_chain_rejected(self):
        l1 = make_line()
        l2 = make_line(event_id="evt-2", prev_hash="0" * 64)
        code, err = self._run(l1 + "\n" + l2 + "\n")
        self.assertEqual(code, 1)
        self.assertIn("prev_hash mismatch", err)

    def test_missing_mid_chain_prev_hash_rejected(self):
        l1 = make_line()
        l2 = make_line(event_id="evt-2")  # no prev_hash on a second entry
        code, err = self._run(l1 + "\n" + l2 + "\n")
        self.assertEqual(code, 1)
        self.assertIn("missing prev_hash", err)


class HeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for name in ("todo.md", "hooks.md", "receipts.jsonl"):
            shutil.copy(os.path.join(ROOT, name), os.path.join(self.tmp, name))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _heartbeat(self):
        env = dict(
            os.environ,
            BUTLER_ROOT=self.tmp,
            BUTLER_ALERT_FILE=os.path.join(self.tmp, ".alert.log"),
        )
        return subprocess.run(
            ["/bin/bash", HEARTBEAT], cwd=self.tmp, capture_output=True, text=True, env=env
        )

    def test_success_path_appends_chained_receipt(self):
        proc = self._heartbeat()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(os.path.join(self.tmp, "receipts.jsonl"), encoding="utf-8") as fh:
            lines = [l.strip() for l in fh if l.strip()]
        self.assertEqual(len(lines), 2)  # template example + heartbeat line
        last = json.loads(lines[-1])
        self.assertEqual(last["action"], "heartbeat")
        self.assertEqual(last["status"], "done")
        self.assertEqual(last["prev_hash"], hashlib.sha256(lines[-2].encode()).hexdigest())
        code = self._validate()
        self.assertEqual(code, 0)

    def test_fail_closed_on_corrupt_ledger(self):
        with open(os.path.join(self.tmp, "receipts.jsonl"), "w", encoding="utf-8") as fh:
            fh.write("corrupt\n")
        proc = self._heartbeat()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("fail-closed", proc.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, ".alert.log")))

    def test_empty_ledger_first_heartbeat(self):
        with open(os.path.join(self.tmp, "receipts.jsonl"), "w", encoding="utf-8") as fh:
            fh.write("")
        proc = self._heartbeat()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(os.path.join(self.tmp, "receipts.jsonl"), encoding="utf-8") as fh:
            lines = [l.strip() for l in fh if l.strip()]
        self.assertEqual(len(lines), 1)
        first = json.loads(lines[0])
        self.assertNotIn("prev_hash", first)  # first entry must not carry prev_hash
        self.assertIn("ledger receipts: 1", proc.stdout)
        self.assertEqual(self._validate(), 0)

    def test_trailing_blank_line_chain_stays_valid(self):
        # ledger ends with a blank line: heartbeat must hash the last LOGICAL line
        with open(os.path.join(self.tmp, "receipts.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(make_line() + "\n\n")
        proc = self._heartbeat()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ledger receipts: 2", proc.stdout)  # logical count, not physical lines
        self.assertEqual(self._validate(), 0)

    def test_missing_todo_fails_closed(self):
        os.unlink(os.path.join(self.tmp, "todo.md"))
        proc = self._heartbeat()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("todo.md missing", proc.stderr)

    def test_missing_hooks_fails_closed(self):
        os.unlink(os.path.join(self.tmp, "hooks.md"))
        proc = self._heartbeat()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("hooks.md missing", proc.stderr)

    def test_whitespace_only_ledger_first_heartbeat(self):
        # whitespace-only file: no logical lines -> first entry must carry no prev_hash
        with open(os.path.join(self.tmp, "receipts.jsonl"), "w", encoding="utf-8") as fh:
            fh.write("   \n\t\n")
        proc = self._heartbeat()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(os.path.join(self.tmp, "receipts.jsonl"), encoding="utf-8") as fh:
            lines = [l.strip() for l in fh if l.strip()]
        self.assertEqual(len(lines), 1)
        self.assertNotIn("prev_hash", json.loads(lines[0]))
        self.assertIn("ledger receipts: 1", proc.stdout)  # logical count for whitespace-only ledger
        self.assertEqual(self._validate(), 0)

    def test_unreadable_todo_fails_closed(self):
        todo = os.path.join(self.tmp, "todo.md")
        os.chmod(todo, 0o000)
        try:
            proc = self._heartbeat()
            self.assertEqual(proc.returncode, 1)
            self.assertIn("missing or unreadable", proc.stderr)
        finally:
            os.chmod(todo, 0o644)  # restore before tearDown deletes the dir

    @unittest.skipUnless(shutil.which("plutil"), "plutil not available")
    def test_plist_lints(self):
        proc = subprocess.run(
            ["plutil", "-lint", os.path.join(ROOT, "com.example.butler-heartbeat.plist")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_hook_window_boundary(self):
        today = __import__("datetime").date.today()
        iso = today.__str__()
        plus6 = (today + __import__("datetime").timedelta(days=6)).__str__()
        plus8 = (today + __import__("datetime").timedelta(days=8)).__str__()
        with open(os.path.join(self.tmp, "hooks.md"), "w", encoding="utf-8") as fh:
            fh.write("| date | trigger | action | status |\n|---|---|---|---|\n")
            fh.write(f"| {plus6} | boundary-due | act | pending |\n")
            fh.write(f"| {plus8} | boundary-not-due | act | pending |\n")
            fh.write(f"| {iso} | today | act | done |\n")
        proc = self._heartbeat()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("due hooks: 1", proc.stdout)

    def _validate(self):
        return subprocess.run(
            [sys.executable, VALIDATOR, os.path.join(self.tmp, "receipts.jsonl")],
            capture_output=True,
            text=True,
        ).returncode


if __name__ == "__main__":
    unittest.main()
