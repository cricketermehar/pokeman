"""
mail_watcher.py
===============
Python bridge between KinanCity-mail.jar and the account queue.

How it works:
  1. kinancity-mail.jar runs in 'log' mode and writes activation links
     to links.log (one per line, tab-separated: <email>\t<link>).
  2. mail_watcher.py polls links.log for new entries.
  3. When a new link is found, it matches the email back to an AccountRecord.
  4. Updates that record's state → ACTIVATION_COMPLETE.

Usage:
    watcher = MailWatcher(queue, links_log_path="links.log")
    watcher.start()        # starts background polling thread
    ...
    watcher.stop()         # graceful shutdown

Or as a one-shot check:
    found = watcher.check_once(username="TrainerJason01")
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

from account_queue import AccountQueue
from account_record import AccountState
from run_logger import get_logger

logger = get_logger("mail_watcher")

DEFAULT_LINKS_LOG = "links.log"
DEFAULT_POLL_INTERVAL_S = 10.0   # check every 10 seconds


class MailWatcher:
    """
    Watches links.log produced by kinancity-mail.jar and updates the
    account queue when activation links are received.

    links.log format (produced by KinanCity-mail in 'log' mode):
        <recipient-email>TAB<activation-link>
    Example:
        counterass100+trainer01@proton.me    https://trainer.pokemon.com/activate/...
    """

    def __init__(
        self,
        queue: AccountQueue,
        links_log: str | Path = DEFAULT_LINKS_LOG,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    ):
        self._queue = queue
        self._links_log = Path(links_log)
        self._poll_interval = poll_interval_s
        self._last_position = 0      # byte offset — only reads new lines
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ─────────────────────────────────────────────────────────────────────────
    # Thread control
    # ─────────────────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="mail-watcher",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "MailWatcher started — polling %s every %.0fs",
            self._links_log,
            self._poll_interval,
        )

    def stop(self) -> None:
        """Signal the polling thread to stop and wait for it."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._poll_interval + 2)
        logger.info("MailWatcher stopped")

    # ─────────────────────────────────────────────────────────────────────────
    # Polling
    # ─────────────────────────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        while self._running:
            try:
                self._read_new_links()
            except Exception as e:
                logger.error("MailWatcher poll error: %s", e)
            time.sleep(self._poll_interval)

    def _read_new_links(self) -> None:
        """Read any new lines from links.log since last check."""
        if not self._links_log.exists():
            return

        with self._links_log.open("r", encoding="utf-8", errors="replace") as f:
            f.seek(self._last_position)
            new_lines = f.readlines()
            self._last_position = f.tell()

        for line in new_lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            self._process_link_line(line)

    def _process_link_line(self, line: str) -> None:
        """
        Parse one line from links.log and update the matching account.

        Expected format:  <email>\t<link>
        Falls back to whitespace splitting if tab not present.
        """
        parts = line.split("\t", 1) if "\t" in line else line.split(None, 1)

        if len(parts) != 2:
            logger.warning("MailWatcher: unrecognised links.log line: %s", line[:80])
            return

        email, link = parts[0].strip(), parts[1].strip()
        logger.info("Activation link received for email: %s", email)

        # Match email back to an account record
        # Strategy: username is typically the local-part prefix before + or @
        matched = self._find_account_by_email(email)

        if matched:
            try:
                matched.activation_link = link
                matched.transition(AccountState.ACTIVATION_COMPLETE)
                self._queue.save()
                logger.info(
                    "[%s] Activation link matched and state → ACTIVATION_COMPLETE",
                    matched.username,
                )
            except ValueError as e:
                logger.warning(
                    "[%s] Could not apply activation — already in terminal state: %s",
                    matched.username,
                    e,
                )
        else:
            logger.warning(
                "Could not match activation email '%s' to any queued account. "
                "Link: %s",
                email,
                link[:60],
            )

    def _find_account_by_email(self, email: str):
        """
        Try to match an email address to an AccountRecord.

        Matching strategy (in order):
          1. Exact username match within the email local-part.
          2. Username appears in the email address (plus-trick pattern).

        Returns the first matching AccountRecord in AWAITING_ACTIVATION state,
        or None if no match found.
        """
        email_lower = email.lower()

        for record in self._queue.all_records():
            if record.state != AccountState.AWAITING_ACTIVATION:
                continue
            username_lower = record.username.lower()
            # Match if username is the local-part or the plus-trick sub-address
            if username_lower in email_lower:
                return record

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # One-shot check (synchronous)
    # ─────────────────────────────────────────────────────────────────────────

    def check_once(self, username: str) -> Optional[str]:
        """
        Synchronously scan the full links.log for an activation link
        matching the given username. Returns the link or None.
        """
        if not self._links_log.exists():
            return None

        with self._links_log.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t", 1) if "\t" in line else line.split(None, 1)
                if len(parts) == 2:
                    email, link = parts[0].strip(), parts[1].strip()
                    if username.lower() in email.lower():
                        return link
        return None
