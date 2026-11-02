"""
account_queue.py
================
Ordered, resumable account queue for KinanCity Python automation.

Responsibilities:
  - Load accounts.txt → AccountRecord list (via credential_store).
  - Merge with existing queue_state.json (resume interrupted runs).
  - Provide next() to get the next QUEUED account.
  - Persist state after every transition via save().
  - Track overall run statistics.

Security contract:
  - Passwords are read from accounts.txt and held in memory only.
  - Passwords are NEVER written to queue_state.json or any log.
  - queue_state.json stores username + state only.
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from account_record import AccountRecord, AccountState
from credential_store import load_credentials
from run_logger import get_logger

logger = get_logger("account_queue")

DEFAULT_ACCOUNTS_FILE = "accounts.txt"
DEFAULT_STATE_FILE = "queue_state.json"


class AccountQueue:
    """
    Manages the full ordered list of AccountRecords for one automation run.

    Usage:
        queue = AccountQueue()
        queue.load()                   # reads accounts.txt + queue_state.json
        while (record := queue.next()) is not None:
            process(record)
            queue.save()               # persist after each state change
        queue.print_summary()
    """

    def __init__(
        self,
        accounts_file: str | Path = DEFAULT_ACCOUNTS_FILE,
        state_file: str | Path = DEFAULT_STATE_FILE,
        max_retries: int = 3,
    ):
        self._accounts_file = Path(accounts_file)
        self._state_file = Path(state_file)
        self._max_retries = max_retries
        # Ordered dict: username → AccountRecord (preserves file order)
        self._records: OrderedDict[str, AccountRecord] = OrderedDict()

    # ─────────────────────────────────────────────────────────────────────────
    # Loading
    # ─────────────────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Load accounts from accounts.txt. Merge with queue_state.json if it
        exists (so interrupted runs resume correctly).

        Order of precedence:
          1. File order from accounts.txt is preserved.
          2. State from queue_state.json overwrites default QUEUED state.
          3. Accounts in queue_state.json but NOT in accounts.txt are ignored.
        """
        # Step 1 — read credentials
        raw_creds = load_credentials(self._accounts_file)
        cred_map: Dict[str, str] = dict(raw_creds)  # username → password

        # Step 2 — load persisted state if available
        persisted: Dict[str, dict] = {}
        if self._state_file.exists():
            try:
                with self._state_file.open("r", encoding="utf-8") as f:
                    saved_list = json.load(f)
                persisted = {item["username"]: item for item in saved_list}
                logger.info(
                    "Resuming: loaded %d persisted states from %s",
                    len(persisted),
                    self._state_file.name,
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(
                    "Could not parse %s (%s) — starting fresh",
                    self._state_file.name,
                    e,
                )

        # Step 3 — build ordered records
        self._records.clear()
        for username, password in raw_creds:
            if username in persisted:
                record = AccountRecord.from_dict(persisted[username], password)
            else:
                record = AccountRecord(
                    username=username,
                    password=password,
                    max_retries=self._max_retries,
                )
            self._records[username] = record

        total = len(self._records)
        already_done = sum(1 for r in self._records.values() if r.state.is_terminal)
        remaining = total - already_done

        logger.info(
            "Queue loaded: %d total | %d already terminal | %d pending",
            total,
            already_done,
            remaining,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Queue operations
    # ─────────────────────────────────────────────────────────────────────────

    def next(self) -> Optional[AccountRecord]:
        """
        Return the next QUEUED account, or None if all are terminal.
        Does not mutate the record — caller must call record.transition().
        """
        for record in self._records.values():
            if record.state == AccountState.QUEUED:
                return record
        return None

    def all_records(self) -> List[AccountRecord]:
        return list(self._records.values())

    def get(self, username: str) -> Optional[AccountRecord]:
        return self._records.get(username)

    def is_complete(self) -> bool:
        """Return True when every account is in a terminal state."""
        return all(r.state.is_terminal for r in self._records.values())

    # ─────────────────────────────────────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────────────────────────────────────

    def save(self) -> None:
        """
        Persist current queue state to queue_state.json.
        Passwords are intentionally excluded (see AccountRecord.to_dict).
        """
        state_list = [r.to_dict() for r in self._records.values()]
        try:
            with self._state_file.open("w", encoding="utf-8") as f:
                json.dump(state_list, f, indent=2)
        except OSError as e:
            logger.error("Failed to save queue state to %s: %s", self._state_file, e)

    # ─────────────────────────────────────────────────────────────────────────
    # Statistics
    # ─────────────────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for record in self._records.values():
            key = record.state.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def print_summary(self) -> None:
        """Log a final summary of account states. No passwords included."""
        stats = self.stats()
        total = len(self._records)
        completed = stats.get(AccountState.COMPLETED.value, 0)
        failed = sum(
            stats.get(s.value, 0)
            for s in [
                AccountState.FAILED_LOGIN,
                AccountState.ACTIVATION_TIMEOUT,
                AccountState.MANUAL_REQUIRED,
            ]
        )

        logger.info("─" * 50)
        logger.info("Queue Summary — %d accounts total", total)
        for state_name, count in sorted(stats.items()):
            logger.info("  %-30s %d", state_name, count)
        logger.info("─" * 50)
        logger.info(
            "Completed: %d | Needs attention: %d | Remaining: %d",
            completed,
            failed,
            stats.get(AccountState.QUEUED.value, 0),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Iteration
    # ─────────────────────────────────────────────────────────────────────────

    def __iter__(self) -> Iterator[AccountRecord]:
        return iter(self._records.values())

    def __len__(self) -> int:
        return len(self._records)
