"""
test_account_queue.py
=====================
Unit tests for AccountQueue — loading, state persistence, resume, statistics.
No network calls. No passwords in assertions.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from account_queue import AccountQueue
from account_record import AccountRecord, AccountState


def _write_accounts(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestAccountQueueLoad(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.accounts = Path(self.tmpdir.name) / "accounts.txt"
        self.state   = Path(self.tmpdir.name) / "queue_state.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_load_valid_accounts(self):
        _write_accounts(self.accounts, ["trainer01:P@ssw0rd1", "trainer02:P@ssw0rd2"])
        q = AccountQueue(accounts_file=self.accounts, state_file=self.state)
        q.load()
        self.assertEqual(len(q), 2)

    def test_skips_comments_and_blank_lines(self):
        _write_accounts(self.accounts, [
            "# comment",
            "",
            "trainer01:P@ssw0rd1",
            "# another comment",
            "trainer02:P@ssw0rd2",
        ])
        q = AccountQueue(accounts_file=self.accounts, state_file=self.state)
        q.load()
        self.assertEqual(len(q), 2)

    def test_password_not_in_queue_state_json(self):
        _write_accounts(self.accounts, ["trainer01:SuperSecret99!"])
        q = AccountQueue(accounts_file=self.accounts, state_file=self.state)
        q.load()
        record = q.next()
        record.transition(AccountState.ACTIVE)
        q.save()

        saved = json.loads(self.state.read_text())
        self.assertEqual(len(saved), 1)
        self.assertNotIn("password", saved[0])
        # Also make sure the password value doesn't appear anywhere in the file
        raw = self.state.read_text()
        self.assertNotIn("SuperSecret99!", raw)

    def test_resume_preserves_completed_state(self):
        _write_accounts(self.accounts, ["trainer01:P@ssw0rd1", "trainer02:P@ssw0rd2"])

        # First load — complete trainer01
        q = AccountQueue(accounts_file=self.accounts, state_file=self.state)
        q.load()
        record = q.next()
        record.transition(AccountState.LOGIN_PENDING)
        record.transition(AccountState.ACTIVE)
        record.transition(AccountState.PTC_REGISTRATION)
        record.transition(AccountState.AWAITING_ACTIVATION)
        record.transition(AccountState.ACTIVATION_COMPLETE)
        record.transition(AccountState.COMPLETED)
        q.save()

        # Second load — trainer01 should still be COMPLETED
        q2 = AccountQueue(accounts_file=self.accounts, state_file=self.state)
        q2.load()
        r1 = q2.get("trainer01")
        self.assertEqual(r1.state, AccountState.COMPLETED)

        # trainer02 should still be QUEUED
        r2 = q2.get("trainer02")
        self.assertEqual(r2.state, AccountState.QUEUED)

    def test_is_complete_when_all_terminal(self):
        _write_accounts(self.accounts, ["trainer01:P@ssw0rd1"])
        q = AccountQueue(accounts_file=self.accounts, state_file=self.state)
        q.load()
        self.assertFalse(q.is_complete())
        record = q.next()
        record.transition(AccountState.LOGIN_PENDING)
        record.transition(AccountState.ACTIVE)
        record.transition(AccountState.COMPLETED)
        self.assertTrue(q.is_complete())

    def test_next_returns_none_when_all_complete(self):
        _write_accounts(self.accounts, ["trainer01:P@ssw0rd1"])
        q = AccountQueue(accounts_file=self.accounts, state_file=self.state)
        q.load()
        r = q.next()
        r.transition(AccountState.LOGIN_PENDING)
        r.transition(AccountState.ACTIVE)
        r.transition(AccountState.COMPLETED)
        self.assertIsNone(q.next())

    def test_stats_count_states(self):
        _write_accounts(self.accounts, [
            "trainer01:P@ssw0rd1",
            "trainer02:P@ssw0rd2",
            "trainer03:P@ssw0rd3",
        ])
        q = AccountQueue(accounts_file=self.accounts, state_file=self.state)
        q.load()
        # Mark first as completed
        q.get("trainer01").transition(AccountState.LOGIN_PENDING)
        q.get("trainer01").transition(AccountState.ACTIVE)
        q.get("trainer01").transition(AccountState.COMPLETED)
        stats = q.stats()
        self.assertEqual(stats[AccountState.COMPLETED.value], 1)
        self.assertEqual(stats[AccountState.QUEUED.value], 2)


if __name__ == "__main__":
    unittest.main()
