"""
account_record.py
=================
Core data model for the KinanCity Python automation backend.

AccountState  — all valid lifecycle states for one account.
AccountRecord — immutable identity + mutable runtime state, persisted to queue_state.json.

No passwords are ever written to logs by this module.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AccountState(str, Enum):
    """
    Full lifecycle of one Pokémon Trainer Central account.

    New-account path:
        QUEUED → LOGIN_PENDING → ACTIVE → PTC_REGISTRATION
               → AWAITING_ACTIVATION → ACTIVATION_COMPLETE → COMPLETED

    Existing-account path (Phase 2 — UGPhone):
        QUEUED → LOGIN_PENDING → ACTIVE → PGTOOLS_READY
               → (WAIT_CANDY) → POWERUP → QUEST_CHECK → REWARD → COMPLETED

    Terminal failure states:
        FAILED_LOGIN / ACTIVATION_TIMEOUT / MANUAL_REQUIRED
    """

    # ── Queue states ──────────────────────────────────────────────────────────
    QUEUED = "QUEUED"                           # Loaded from accounts.txt, waiting

    # ── Login ─────────────────────────────────────────────────────────────────
    LOGIN_PENDING = "LOGIN_PENDING"             # Dequeued, attempting credential validation
    ACTIVE = "ACTIVE"                           # Session confirmed / credentials valid

    # ── New account — PTC registration path ───────────────────────────────────
    PTC_REGISTRATION = "PTC_REGISTRATION"       # About to submit registration
    AWAITING_ACTIVATION = "AWAITING_ACTIVATION" # Registration POST sent, waiting for email
    ACTIVATION_COMPLETE = "ACTIVATION_COMPLETE" # Activation link clicked and confirmed

    # ── Existing account — PGTools path (Phase 2) ─────────────────────────────
    PGTOOLS_READY = "PGTOOLS_READY"             # PGTools launched and game loaded
    WAIT_CANDY = "WAIT_CANDY"                   # Not enough candy yet — waiting
    POWERUP = "POWERUP"                         # Performing power-up on lowest-CP Pokémon
    QUEST_CHECK = "QUEST_CHECK"                 # Verifying quest completion state
    REWARD = "REWARD"                           # Claiming / verifying quest reward

    # ── Terminal states ────────────────────────────────────────────────────────
    COMPLETED = "COMPLETED"                     # Account fully processed — success
    FAILED_LOGIN = "FAILED_LOGIN"               # Bad credentials / account locked
    ACTIVATION_TIMEOUT = "ACTIVATION_TIMEOUT"  # No activation email after timeout window
    MANUAL_REQUIRED = "MANUAL_REQUIRED"         # Unexpected state — human intervention needed

    # ── Internal ───────────────────────────────────────────────────────────────
    SKIPPED = "SKIPPED"                         # Comment or blank line in accounts.txt

    @property
    def is_terminal(self) -> bool:
        """Return True if this state ends processing for the account."""
        return self in {
            AccountState.COMPLETED,
            AccountState.FAILED_LOGIN,
            AccountState.ACTIVATION_TIMEOUT,
            AccountState.MANUAL_REQUIRED,
            AccountState.SKIPPED,
        }

    @property
    def is_failure(self) -> bool:
        """Return True if this is a non-success terminal state."""
        return self in {
            AccountState.FAILED_LOGIN,
            AccountState.ACTIVATION_TIMEOUT,
            AccountState.MANUAL_REQUIRED,
        }


@dataclass
class AccountRecord:
    """
    Represents one account entry loaded from accounts.txt.

    Security contract:
    - The `password` field is NEVER written to any log file.
    - Only `username` and `state` appear in log output.
    - `password` is serialised to queue_state.json only as a placeholder
      so the file can be used to resume — the actual password is always
      re-read from accounts.txt at startup.
    """

    # ── Identity (immutable after load) ───────────────────────────────────────
    username: str
    password: str                               # Never logged. See security contract above.

    # ── Lifecycle state ────────────────────────────────────────────────────────
    state: AccountState = AccountState.QUEUED
    retries: int = 0
    max_retries: int = 3

    # ── Timing ────────────────────────────────────────────────────────────────
    queued_at: float = field(default_factory=time.time)
    last_updated_at: Optional[float] = None
    completed_at: Optional[float] = None

    # ── Error tracking ────────────────────────────────────────────────────────
    last_error: Optional[str] = None           # Human-readable, no secrets

    # ── Activation (PTC registration path) ───────────────────────────────────
    activation_link: Optional[str] = None
    activation_waited_s: float = 0.0

    # ── Notes (for manual-required state) ────────────────────────────────────
    notes: str = ""

    # ─────────────────────────────────────────────────────────────────────────

    def transition(self, new_state: AccountState, note: str = "") -> None:
        """
        Move the account to a new state and record the timestamp.
        Raises ValueError if transitioning from a terminal state.
        """
        if self.state == new_state:
            if note:
                self.notes = note
            self.last_updated_at = time.time()
            return

        if self.state.is_terminal:
            if self.state == AccountState.ACTIVATION_TIMEOUT and new_state == AccountState.MANUAL_REQUIRED:
                pass
            else:
                raise ValueError(
                    f"Cannot transition '{self.username}' from terminal state "
                    f"{self.state} → {new_state}"
                )
        self.state = new_state
        self.last_updated_at = time.time()
        if note:
            self.notes = note
        if new_state.is_terminal:
            self.completed_at = time.time()

    def mark_retry(self, error_msg: str, max_retries: Optional[int] = None) -> bool:
        """
        Increment retry counter. Returns True if another retry is allowed,
        False if max_retries has been reached (caller should → MANUAL_REQUIRED).
        The error_msg must NOT contain passwords.
        """
        if max_retries is not None:
            self.max_retries = max_retries
        self.retries += 1
        self.last_error = error_msg
        self.last_updated_at = time.time()
        return self.retries < self.max_retries

    def to_dict(self) -> dict:
        """
        Serialise to a JSON-safe dict for queue_state.json persistence.
        Password is intentionally excluded — always re-read from accounts.txt.
        """
        return {
            "username": self.username,
            "state": self.state.value,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "queued_at": self.queued_at,
            "last_updated_at": self.last_updated_at,
            "completed_at": self.completed_at,
            "last_error": self.last_error,
            "activation_waited_s": self.activation_waited_s,
            "notes": self.notes,
            # password intentionally absent
        }

    @classmethod
    def from_dict(cls, data: dict, password: str) -> "AccountRecord":
        """
        Reconstruct an AccountRecord from queue_state.json.
        Password is passed in separately (always sourced from accounts.txt).
        """
        record = cls(
            username=data["username"],
            password=password,
            state=AccountState(data.get("state", AccountState.QUEUED.value)),
            retries=data.get("retries", 0),
            max_retries=data.get("max_retries", 3),
            queued_at=data.get("queued_at", time.time()),
            last_updated_at=data.get("last_updated_at"),
            completed_at=data.get("completed_at"),
            last_error=data.get("last_error"),
            activation_waited_s=data.get("activation_waited_s", 0.0),
            notes=data.get("notes", ""),
        )
        return record

    def __repr__(self) -> str:
        # Password deliberately excluded from repr
        return (
            f"AccountRecord(username={self.username!r}, "
            f"state={self.state.value}, retries={self.retries})"
        )
