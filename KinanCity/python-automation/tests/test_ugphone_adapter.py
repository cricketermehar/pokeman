"""
test_ugphone_adapter.py
=======================
Unit tests for Phase 2 UGPhone / PGTools adapter & StateMachine integration.
Tests cover device connection, CP sorting, power-ups, quest completion,
and full lifecycle transitions to COMPLETED.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from account_record import AccountRecord, AccountState
from retry_handler import RetryHandler
from state_machine import StateMachine, StubPtcHandler
from adapters.ugphone_adapter import UGPhoneAdapter
from adapters.ugphone_driver import SimulatedDriver


def _make_record(username: str = "trainer01", password: str = "ValidP@ssword123!", notes: str = "") -> AccountRecord:
    return AccountRecord(username=username, password=password, notes=notes)


class TestUGPhoneDriver(unittest.TestCase):

    def test_simulated_driver_lifecycle(self):
        driver = SimulatedDriver(initial_candy=20)
        self.assertFalse(driver.is_connected())

        self.assertTrue(driver.connect("127.0.0.1", 5555))
        self.assertTrue(driver.is_connected())

        self.assertTrue(driver.tap(100, 200))
        self.assertTrue(driver.input_text("secret_test"))
        self.assertTrue(driver.press_key(4))
        self.assertTrue(driver.launch_app("com.nianticlabs.pokemongo"))
        self.assertEqual(driver.active_app, "com.nianticlabs.pokemongo")

        driver.disconnect()
        self.assertFalse(driver.is_connected())


class TestUGPhoneAdapter(unittest.TestCase):

    def setUp(self):
        self.driver = SimulatedDriver(initial_candy=15)
        self.adapter = UGPhoneAdapter(driver=self.driver, use_simulator=True)

    def test_connect_and_disconnect(self):
        self.assertTrue(self.adapter.connect())
        self.assertTrue(self.driver.is_connected())
        self.adapter.disconnect()
        self.assertFalse(self.driver.is_connected())

    def test_login_account(self):
        self.assertTrue(self.adapter.login_account("trainer01", "SecretPass123!"))
        self.assertEqual(self.driver.logged_in_user, "trainer01")
        self.assertEqual(self.driver.active_app, "com.nianticlabs.pokemongo")

    def test_pgtools_start(self):
        self.assertTrue(self.adapter.start_pgtools("trainer01", "SecretPass123!"))
        self.assertEqual(self.driver.active_app, "com.pgtools.pogo")

    def test_candy_and_powerup_loop(self):
        self.assertEqual(self.adapter.get_candy_count(), 15)
        self.assertTrue(self.adapter.sort_pokemon_by_cp())
        self.assertTrue(self.driver.cp_sorted)

        self.assertFalse(self.adapter.check_quest_complete())
        self.assertTrue(self.adapter.power_up_lowest_cp())
        self.assertEqual(self.adapter.get_candy_count(), 14)
        self.assertTrue(self.adapter.check_quest_complete())

        self.assertTrue(self.adapter.claim_reward())
        self.assertTrue(self.driver.reward_claimed)


class TestStateMachinePGToolsIntegration(unittest.TestCase):
    """Verifies that an existing account smoothly reaches COMPLETED via UGPhoneAdapter."""

    def test_existing_account_completes_full_pgtools_flow(self):
        driver = SimulatedDriver(initial_candy=15)
        adapter = UGPhoneAdapter(driver=driver, use_simulator=True)
        retry = RetryHandler(max_retries=1, base_delay_s=0.01, sleep_fn=lambda s: None)

        machine = StateMachine(
            ptc_handler=StubPtcHandler(),
            ugphone_handler=adapter,
            retry_handler=retry,
            account_email="trainer01@example.com",
        )

        record = _make_record(notes="existing account")
        machine.run(record)

        self.assertEqual(record.state, AccountState.COMPLETED)
        self.assertTrue(driver.reward_claimed)
        self.assertTrue(driver.quest_completed)
        self.assertTrue(driver.cp_sorted)


if __name__ == "__main__":
    unittest.main()
