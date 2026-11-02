"""
test_state_machine.py
=====================
Unit tests for StateMachine — state transitions, retry handling,
new-account and existing-account paths.
All I/O and sleep calls are mocked.
"""

import sys
import time
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from account_record import AccountRecord, AccountState
from retry_handler import RetryHandler
from state_machine import StateMachine, StubPtcHandler


def _make_record(username="trainer01", password="P@ssw0rd1!") -> AccountRecord:
    return AccountRecord(username=username, password=password)


class MockPtcHandlerSuccess:
    """PTC handler that always succeeds."""
    def validate_credentials(self, u, p): return True
    def submit_registration(self, u, p, e): return True
    def check_activation_link(self, u): return f"https://example.com/activate/{u}"


class MockPtcHandlerFailLogin:
    """PTC handler that fails credential validation."""
    def validate_credentials(self, u, p): return False
    def submit_registration(self, u, p, e): return False
    def check_activation_link(self, u): return None


class TestStateMachineNewAccount(unittest.TestCase):

    def _make_machine(self, handler=None, email="test@example.com",
                      activation_timeout_s=1, activation_poll_s=0.1):
        retry = RetryHandler(max_retries=3, base_delay_s=0.01, sleep_fn=lambda s: None)
        return StateMachine(
            ptc_handler=handler or MockPtcHandlerSuccess(),
            retry_handler=retry,
            account_email=email,
            activation_timeout_s=activation_timeout_s,
            activation_poll_s=activation_poll_s,
        )

    def test_happy_path_new_account(self):
        """QUEUED → LOGIN_PENDING → ACTIVE → PTC_REGISTRATION → AWAITING_ACTIVATION
           → ACTIVATION_COMPLETE → COMPLETED"""
        machine = self._make_machine()
        record = _make_record()
        machine.run(record)
        self.assertEqual(record.state, AccountState.COMPLETED)

    def test_failed_login_becomes_manual_required(self):
        """Failed credential validation with max retries → MANUAL_REQUIRED"""
        machine = self._make_machine(handler=MockPtcHandlerFailLogin())
        record = _make_record(password="bad")  # will fail format check in stub
        machine.run(record)
        self.assertIn(record.state, [AccountState.MANUAL_REQUIRED, AccountState.FAILED_LOGIN])

    def test_no_email_configured_goes_to_manual(self):
        """Empty email address → MANUAL_REQUIRED (cannot register without email)"""
        machine = self._make_machine(email="")
        record = _make_record()
        machine.run(record)
        self.assertEqual(record.state, AccountState.MANUAL_REQUIRED)

    def test_activation_timeout_goes_to_manual(self):
        """No activation link within timeout → ACTIVATION_TIMEOUT → MANUAL_REQUIRED"""

        class NeverActivates:
            def validate_credentials(self, u, p): return True
            def submit_registration(self, u, p, e): return True
            def check_activation_link(self, u): return None  # never arrives

        machine = self._make_machine(
            handler=NeverActivates(),
            activation_timeout_s=0.1,
            activation_poll_s=0.05,
        )
        record = _make_record()
        machine.run(record)
        self.assertEqual(record.state, AccountState.MANUAL_REQUIRED)

    def test_password_not_in_record_notes(self):
        """State transition notes must not contain the account password."""
        machine = self._make_machine(handler=MockPtcHandlerFailLogin())
        record = _make_record(password="SuperSecret99!")
        machine.run(record)
        self.assertNotIn("SuperSecret99!", record.notes)
        self.assertNotIn("SuperSecret99!", str(record.last_error or ""))


class TestStateMachineExistingAccount(unittest.TestCase):

    def test_existing_account_routes_to_pgtools(self):
        """Account with 'existing' in notes routes → PGTOOLS_READY → MANUAL_REQUIRED
           (because stub UGPhone raises NotImplementedError)."""
        retry = RetryHandler(max_retries=1, base_delay_s=0.01, sleep_fn=lambda s: None)
        machine = StateMachine(
            ptc_handler=MockPtcHandlerSuccess(),
            retry_handler=retry,
            account_email="test@example.com",
            activation_timeout_s=1,
            activation_poll_s=0.1,
        )
        record = _make_record()
        record.notes = "existing account"
        machine.run(record)
        # Stub UGPhone raises NotImplementedError → MANUAL_REQUIRED
        self.assertEqual(record.state, AccountState.MANUAL_REQUIRED)


class TestRetryHandler(unittest.TestCase):

    def test_retries_three_times_then_manual(self):
        slept = []
        handler = RetryHandler(max_retries=3, base_delay_s=1.0, sleep_fn=slept.append)
        record = _make_record()

        self.assertTrue(handler.handle_failure(record, "err1"))   # retry 1
        self.assertTrue(handler.handle_failure(record, "err2"))   # retry 2
        self.assertFalse(handler.handle_failure(record, "err3"))  # retry 3 — max hit

        self.assertEqual(record.state, AccountState.MANUAL_REQUIRED)
        self.assertEqual(len(slept), 2)  # slept on retry 1 and 2, not on final

    def test_exponential_backoff_values(self):
        slept = []
        handler = RetryHandler(max_retries=4, base_delay_s=60.0, max_delay_s=300.0,
                               sleep_fn=slept.append)
        record = _make_record()

        handler.handle_failure(record, "e1")  # attempt 1 → sleep 60
        handler.handle_failure(record, "e2")  # attempt 2 → sleep 120
        handler.handle_failure(record, "e3")  # attempt 3 → sleep 240
        handler.handle_failure(record, "e4")  # attempt 4 → MANUAL_REQUIRED (no sleep)

        self.assertAlmostEqual(slept[0], 60.0)
        self.assertAlmostEqual(slept[1], 120.0)
        self.assertAlmostEqual(slept[2], 240.0)
        self.assertEqual(len(slept), 3)

    def test_force_manual_skips_retries(self):
        slept = []
        handler = RetryHandler(max_retries=3, base_delay_s=60.0, sleep_fn=slept.append)
        record = _make_record()
        result = handler.handle_failure(record, "immediate fail", force_manual=True)
        self.assertFalse(result)
        self.assertEqual(record.state, AccountState.MANUAL_REQUIRED)
        self.assertEqual(len(slept), 0)


if __name__ == "__main__":
    unittest.main()
