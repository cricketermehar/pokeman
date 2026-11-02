"""
state_machine.py
================
Per-account lifecycle driver for KinanCity Python automation.

The StateMachine drives one AccountRecord through its lifecycle states.
It is intentionally thin — it delegates actual PTC/UGPhone work to
pluggable handler callbacks so the queue logic stays reusable.

Architecture:
    StateMachine.run(record)
        └── _handle_login()
        └── _handle_registration()   ← new-account path
        └── _handle_pgtools()        ← existing-account path (Phase 2 stub)

Phase 2 hook:
    Swap in a real UGPhoneAdapter implementation via the ugphone_adapter param.
    The stub adapter is wired in by default and raises NotImplementedError
    so it is obvious when Phase 2 work is needed.
"""

from __future__ import annotations

import time
from typing import Optional, Protocol

from account_record import AccountRecord, AccountState
from retry_handler import RetryHandler
from run_logger import get_logger

logger = get_logger("state_machine")

# Activation email timeout — how long to wait before → ACTIVATION_TIMEOUT
DEFAULT_ACTIVATION_TIMEOUT_S = 600   # 10 minutes
DEFAULT_ACTIVATION_POLL_S = 30       # check every 30 seconds


# ─────────────────────────────────────────────────────────────────────────────
# Protocol interfaces — allows dependency injection and testing
# ─────────────────────────────────────────────────────────────────────────────

class PtcHandler(Protocol):
    """
    Protocol for the PTC registration handler.
    Implement this to plug in real HTTP registration logic.
    """

    def validate_credentials(self, username: str, password: str) -> bool:
        """Return True if credentials pass local format validation."""
        ...

    def submit_registration(self, username: str, password: str, email: str) -> bool:
        """
        Submit the registration form.
        Returns True if the POST succeeded without network error.
        Raises RuntimeError with a safe (no-password) message on failure.
        """
        ...

    def check_activation_link(self, username: str) -> Optional[str]:
        """
        Poll for the activation link for this username from links.log.
        Returns the link string if found, None if not yet received.
        """
        ...


class UGPhoneHandler(Protocol):
    """
    Protocol for Phase 2 UGPhone/PGTools automation.
    The stub adapter raises NotImplementedError — implement for Phase 2.
    """

    def start_pgtools(self, username: str, password: str) -> bool: ...
    def get_candy_count(self) -> int: ...
    def sort_pokemon_by_cp(self) -> bool: ...
    def power_up_lowest_cp(self) -> bool: ...
    def check_quest_complete(self) -> bool: ...
    def claim_reward(self) -> bool: ...


# ─────────────────────────────────────────────────────────────────────────────
# Default stub implementations
# ─────────────────────────────────────────────────────────────────────────────

class StubPtcHandler:
    """
    Stub PTC handler — simulates a dry-run without real HTTP calls.
    Used when no real handler is wired in (safe default for testing).
    """

    def validate_credentials(self, username: str, password: str) -> bool:
        import re
        username_ok = bool(re.match(r"^[a-zA-Z0-9]{6,16}$", username))
        password_ok = len(password) >= 8
        if not username_ok:
            logger.warning("[STUB] Username '%s' fails local format check", username)
        if not password_ok:
            logger.warning("[STUB] Password for '%s' is too short", username)
        return username_ok and password_ok

    def submit_registration(self, username: str, password: str, email: str) -> bool:
        logger.info("[STUB] Registration POST simulated for '%s' (dry-run)", username)
        return True   # pretend success

    def check_activation_link(self, username: str) -> Optional[str]:
        logger.debug("[STUB] No activation link check — dry-run mode")
        return f"https://stub-activation.example.com/activate/{username}"


class StubUGPhoneHandler:
    """Stub that raises NotImplementedError — Phase 2 not yet implemented."""

    def start_pgtools(self, username: str, password: str) -> bool:
        raise NotImplementedError("UGPhone/PGTools automation is Phase 2 — not yet implemented")

    def get_candy_count(self) -> int:
        raise NotImplementedError("UGPhone/PGTools automation is Phase 2")

    def sort_pokemon_by_cp(self) -> bool:
        raise NotImplementedError("UGPhone/PGTools automation is Phase 2")

    def power_up_lowest_cp(self) -> bool:
        raise NotImplementedError("UGPhone/PGTools automation is Phase 2")

    def check_quest_complete(self) -> bool:
        raise NotImplementedError("UGPhone/PGTools automation is Phase 2")

    def claim_reward(self) -> bool:
        raise NotImplementedError("UGPhone/PGTools automation is Phase 2")


# ─────────────────────────────────────────────────────────────────────────────
# State machine
# ─────────────────────────────────────────────────────────────────────────────

class StateMachine:
    """
    Drives one AccountRecord through its full lifecycle.

    Instantiate once and call run(record) for each account.
    Thread-safety: one StateMachine per thread (no shared state between calls).
    """

    def __init__(
        self,
        ptc_handler: Optional[PtcHandler] = None,
        ugphone_handler: Optional[UGPhoneHandler] = None,
        retry_handler: Optional[RetryHandler] = None,
        account_email: str = "",
        activation_timeout_s: float = DEFAULT_ACTIVATION_TIMEOUT_S,
        activation_poll_s: float = DEFAULT_ACTIVATION_POLL_S,
        dry_run: bool = False,
    ):
        self._ptc = ptc_handler or StubPtcHandler()
        self._ugphone = ugphone_handler or StubUGPhoneHandler()
        self._retry = retry_handler or RetryHandler()
        self._email = account_email
        self._activation_timeout_s = activation_timeout_s
        self._activation_poll_s = activation_poll_s
        self._dry_run = dry_run

    def run(self, record: AccountRecord) -> None:
        """
        Drive the account through its lifecycle until a terminal state.
        Blocks until the account reaches COMPLETED or a failure terminal.
        """
        logger.info("[%s] Starting — state: %s", record.username, record.state.value)

        while not record.state.is_terminal:
            try:
                self._step(record)
            except Exception as e:
                # Catch unexpected errors and treat as retryable failure
                safe_msg = f"Unexpected error in state {record.state.value}: {type(e).__name__}: {e}"
                logger.error("[%s] %s", record.username, safe_msg)
                can_retry = self._retry.handle_failure(record, safe_msg)
                if can_retry:
                    record.transition(AccountState.QUEUED)
                # if not can_retry, record is already MANUAL_REQUIRED

        logger.info(
            "[%s] Terminal state reached: %s",
            record.username,
            record.state.value,
        )

    def _step(self, record: AccountRecord) -> None:
        """Execute one state transition."""
        state = record.state

        if state == AccountState.QUEUED:
            self._handle_queued(record)

        elif state == AccountState.LOGIN_PENDING:
            self._handle_login(record)

        elif state == AccountState.ACTIVE:
            self._handle_active(record)

        elif state == AccountState.PTC_REGISTRATION:
            self._handle_ptc_registration(record)

        elif state == AccountState.AWAITING_ACTIVATION:
            self._handle_awaiting_activation(record)

        elif state == AccountState.ACTIVATION_COMPLETE:
            record.transition(AccountState.COMPLETED)

        elif state == AccountState.PGTOOLS_READY:
            self._handle_pgtools_ready(record)

        elif state == AccountState.WAIT_CANDY:
            self._handle_wait_candy(record)

        elif state == AccountState.POWERUP:
            self._handle_powerup(record)

        elif state == AccountState.QUEST_CHECK:
            self._handle_quest_check(record)

        elif state == AccountState.REWARD:
            self._handle_reward(record)

        elif state == AccountState.FAILED_LOGIN:
            # Failed login with retries already exhausted → MANUAL_REQUIRED
            self._retry.handle_failure(record, "Login failed", force_manual=True)

    # ── State handlers ────────────────────────────────────────────────────────

    def _handle_queued(self, record: AccountRecord) -> None:
        record.transition(AccountState.LOGIN_PENDING)

    def _handle_login(self, record: AccountRecord) -> None:
        """Validate credentials locally then mark ACTIVE."""
        valid = self._ptc.validate_credentials(record.username, record.password)
        if valid:
            logger.info("[%s] Credentials valid → ACTIVE", record.username)
            record.transition(AccountState.ACTIVE)
        else:
            logger.warning("[%s] Credential validation failed", record.username)
            can_retry = self._retry.handle_failure(
                record, "Credential format validation failed"
            )
            if can_retry:
                record.transition(AccountState.LOGIN_PENDING)
            # else record → MANUAL_REQUIRED (done inside retry_handler)

    def _handle_active(self, record: AccountRecord) -> None:
        """
        Decide which path to take:
          - new account → PTC_REGISTRATION
          - existing account or UGPhone mode → PGTOOLS_READY (Phase 2)
        """
        if "existing" in record.notes.lower() or not isinstance(self._ugphone, StubUGPhoneHandler):
            logger.info("[%s] PGTools account path → PGTOOLS_READY", record.username)
            record.transition(AccountState.PGTOOLS_READY)
        else:
            logger.info("[%s] New account path → PTC_REGISTRATION", record.username)
            record.transition(AccountState.PTC_REGISTRATION)

    def _handle_ptc_registration(self, record: AccountRecord) -> None:
        """Submit the PTC registration POST."""
        if not self._email:
            logger.error(
                "[%s] No email configured for registration — MANUAL_REQUIRED",
                record.username,
            )
            record.transition(AccountState.MANUAL_REQUIRED, note="No email configured")
            return

        try:
            success = self._ptc.submit_registration(
                record.username, record.password, self._email
            )
            if success:
                logger.info("[%s] Registration submitted → AWAITING_ACTIVATION", record.username)
                record.transition(AccountState.AWAITING_ACTIVATION)
            else:
                can_retry = self._retry.handle_failure(record, "Registration POST returned failure")
                if can_retry:
                    record.transition(AccountState.PTC_REGISTRATION)
        except RuntimeError as e:
            can_retry = self._retry.handle_failure(record, str(e))
            if can_retry:
                record.transition(AccountState.PTC_REGISTRATION)

    def _handle_awaiting_activation(self, record: AccountRecord) -> None:
        """Poll for the activation link until timeout or found."""
        poll_start = time.time()

        while True:
            elapsed = time.time() - poll_start
            if elapsed >= self._activation_timeout_s:
                logger.warning(
                    "[%s] Activation timeout after %.0fs → ACTIVATION_TIMEOUT",
                    record.username,
                    elapsed,
                )
                record.transition(AccountState.ACTIVATION_TIMEOUT)
                self._retry.handle_failure(
                    record,
                    f"No activation email after {self._activation_timeout_s}s",
                    force_manual=True,
                )
                return

            link = self._ptc.check_activation_link(record.username)
            if link:
                logger.info("[%s] Activation link found after %.0fs", record.username, elapsed)
                record.activation_link = link
                record.transition(AccountState.ACTIVATION_COMPLETE)
                return

            record.activation_waited_s = elapsed
            logger.debug(
                "[%s] Waiting for activation email... (%.0fs / %.0fs)",
                record.username,
                elapsed,
                self._activation_timeout_s,
            )
            time.sleep(self._activation_poll_s)

    # ── Phase 2 stubs (UGPhone/PGTools) ───────────────────────────────────────

    def _handle_pgtools_ready(self, record: AccountRecord) -> None:
        """Phase 2: Start PGTools and check candy."""
        try:
            self._ugphone.start_pgtools(record.username, record.password)
            candy = self._ugphone.get_candy_count()
            if candy >= 10:   # threshold TBD with client
                logger.info("[%s] Candy OK (%d) → POWERUP", record.username, candy)
                record.transition(AccountState.POWERUP)
            else:
                logger.info("[%s] Not enough candy (%d) → WAIT_CANDY", record.username, candy)
                record.transition(AccountState.WAIT_CANDY)
        except NotImplementedError:
            logger.warning(
                "[%s] UGPhone handler not implemented — Phase 2 required → MANUAL_REQUIRED",
                record.username,
            )
            record.transition(AccountState.MANUAL_REQUIRED, note="Phase 2 UGPhone not implemented")

    def _handle_wait_candy(self, record: AccountRecord) -> None:
        """Phase 2: Wait until enough candy accumulates."""
        try:
            candy = self._ugphone.get_candy_count()
            if candy >= 10:
                record.transition(AccountState.POWERUP)
            else:
                logger.info("[%s] Still waiting for candy (%d/10)", record.username, candy)
                time.sleep(60)
        except NotImplementedError:
            record.transition(AccountState.MANUAL_REQUIRED, note="Phase 2 UGPhone not implemented")

    def _handle_powerup(self, record: AccountRecord) -> None:
        """Phase 2: Sort by CP and power up lowest-CP Pokémon."""
        try:
            self._ugphone.sort_pokemon_by_cp()
            success = self._ugphone.power_up_lowest_cp()
            if success:
                record.transition(AccountState.QUEST_CHECK)
            else:
                can_retry = self._retry.handle_failure(record, "Power-up action failed")
                if can_retry:
                    record.transition(AccountState.POWERUP)
        except NotImplementedError:
            record.transition(AccountState.MANUAL_REQUIRED, note="Phase 2 UGPhone not implemented")

    def _handle_quest_check(self, record: AccountRecord) -> None:
        """Phase 2: Verify quest completion."""
        try:
            complete = self._ugphone.check_quest_complete()
            if complete:
                record.transition(AccountState.REWARD)
            else:
                logger.info("[%s] Quest not yet complete — waiting", record.username)
                time.sleep(30)
        except NotImplementedError:
            record.transition(AccountState.MANUAL_REQUIRED, note="Phase 2 UGPhone not implemented")

    def _handle_reward(self, record: AccountRecord) -> None:
        """Phase 2: Claim quest reward."""
        try:
            claimed = self._ugphone.claim_reward()
            if claimed:
                record.transition(AccountState.COMPLETED)
            else:
                can_retry = self._retry.handle_failure(record, "Reward claim failed")
                if can_retry:
                    record.transition(AccountState.REWARD)
        except NotImplementedError:
            record.transition(AccountState.MANUAL_REQUIRED, note="Phase 2 UGPhone not implemented")
