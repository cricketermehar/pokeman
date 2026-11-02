"""
retry_handler.py
================
Exponential-backoff retry logic for KinanCity Python automation.

Configuration (from config.ini):
  max_retries   = 3       (attempts before MANUAL_REQUIRED)
  base_delay_s  = 60      (seconds — doubles each retry: 60, 120, 240)
  max_delay_s   = 300     (hard ceiling regardless of backoff)

Design:
  - Each AccountRecord tracks its own retry counter.
  - RetryHandler decides whether to retry or escalate to MANUAL_REQUIRED.
  - Delays are applied with sleep() so the queue blocks for this account only.
  - Errors logged here never contain passwords.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from account_record import AccountRecord, AccountState
from run_logger import get_logger

logger = get_logger("retry_handler")


class RetryHandler:
    """
    Evaluates whether an account should be retried after a failure,
    and handles the wait delay before the next attempt.

    Usage:
        handler = RetryHandler(max_retries=3, base_delay_s=60)
        should_retry = handler.handle_failure(record, error_msg="Login timeout")
        if should_retry:
            # re-queue or loop
        else:
            # record is now MANUAL_REQUIRED — move on
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay_s: float = 60.0,
        max_delay_s: float = 300.0,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ):
        """
        Args:
            max_retries:   Max number of retry attempts (default 3).
            base_delay_s:  Base backoff delay in seconds (default 60).
            max_delay_s:   Hard ceiling on delay regardless of backoff.
            sleep_fn:      Override for testing (defaults to time.sleep).
        """
        self.max_retries = max_retries
        self.base_delay_s = base_delay_s
        self.max_delay_s = max_delay_s
        self._sleep = sleep_fn or time.sleep

    def handle_failure(
        self,
        record: AccountRecord,
        error_msg: str,
        force_manual: bool = False,
    ) -> bool:
        """
        Handle a failure for the given account.

        Steps:
          1. Increment retry counter on the record.
          2. If retries exhausted (or force_manual), transition → MANUAL_REQUIRED.
          3. If retries remain, log and sleep for the backoff duration.

        Args:
            record:       The AccountRecord that failed.
            error_msg:    Description of the error (MUST NOT contain passwords).
            force_manual: Skip all retries and go straight to MANUAL_REQUIRED.

        Returns:
            True  — retry should be attempted (caller re-queues / re-runs).
            False — max retries hit; record is now MANUAL_REQUIRED.
        """
        can_retry = record.mark_retry(error_msg, max_retries=self.max_retries)

        if force_manual or not can_retry:
            logger.warning(
                "[%s] Max retries (%d) reached — marking MANUAL_REQUIRED. "
                "Last error: %s",
                record.username,
                self.max_retries,
                error_msg,
            )
            record.transition(
                AccountState.MANUAL_REQUIRED,
                note=f"Max retries reached. Last error: {error_msg}",
            )
            return False

        delay = self._backoff_delay(record.retries)
        logger.info(
            "[%s] Retry %d/%d after %.0fs delay. Reason: %s",
            record.username,
            record.retries,
            self.max_retries,
            delay,
            error_msg,
        )
        self._sleep(delay)
        return True

    def _backoff_delay(self, attempt: int) -> float:
        """
        Exponential backoff: base * 2^(attempt-1), capped at max_delay_s.

        attempt=1 → base_delay_s * 1  (e.g. 60s)
        attempt=2 → base_delay_s * 2  (e.g. 120s)
        attempt=3 → base_delay_s * 4  (e.g. 240s)
        """
        multiplier = 2 ** (attempt - 1)
        delay = self.base_delay_s * multiplier
        return min(delay, self.max_delay_s)
