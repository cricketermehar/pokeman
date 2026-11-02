"""
credential_store.py
===================
Secure credential loader for KinanCity Python automation.

Reads accounts.txt (format: username:password, one per line).
Passwords are NEVER written to any log. Only usernames appear in output.

File format rules:
  - Lines starting with # are treated as comments and skipped.
  - Blank lines are skipped.
  - Each valid line must be exactly: username:password
  - The delimiter is the FIRST colon only (passwords may contain colons).
  - Usernames must be 6–16 alphanumeric characters (PTC rule).

Example accounts.txt:
  # My Pokémon accounts
  TrainerJason01:MyS3cur3P@ss!
  TrainerJason02:An0ther$ecure1
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

# PTC username validation (6–16 alphanumeric characters)
_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9]{6,16}$")

# Minimum password length (PTC requires 8+ with complexity)
_MIN_PASSWORD_LEN = 8


def is_valid_username(username: str) -> bool:
    """Validate username according to PTC rules (6–16 alphanumeric chars)."""
    return bool(_USERNAME_PATTERN.match(username))


def is_valid_password(password: str) -> bool:
    """Validate password according to PTC minimum requirements."""
    return len(password) >= _MIN_PASSWORD_LEN


def load_credentials(accounts_file: str | Path) -> List[Tuple[str, str]]:
    """
    Read accounts.txt and return a list of (username, password) tuples.

    Skips blank lines and lines starting with '#'.
    Logs warnings for malformed lines (without exposing passwords).
    Raises FileNotFoundError if the file does not exist.

    Returns:
        List of (username, password) tuples in file order.
    """
    path = Path(accounts_file)

    if not path.exists():
        raise FileNotFoundError(
            f"accounts.txt not found at: {path.resolve()}\n"
            "Create the file with one username:password per line."
        )

    credentials: List[Tuple[str, str]] = []
    line_number = 0
    skipped = 0
    errors = 0

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line_number += 1
            line = raw_line.strip()

            # Skip blanks and comments
            if not line or line.startswith("#"):
                skipped += 1
                continue

            # Split on first colon only
            if ":" not in line:
                logger.warning(
                    "accounts.txt line %d: missing ':' delimiter — skipped "
                    "(format must be username:password)",
                    line_number,
                )
                errors += 1
                continue

            username, _, password = line.partition(":")

            # Validate username format
            if not _USERNAME_PATTERN.match(username):
                logger.warning(
                    "accounts.txt line %d: invalid username '%s' "
                    "(must be 6–16 alphanumeric chars) — skipped",
                    line_number,
                    username,
                )
                errors += 1
                continue

            # Validate password is not empty
            if len(password) < _MIN_PASSWORD_LEN:
                logger.warning(
                    "accounts.txt line %d: password for '%s' is too short "
                    "(%d chars, minimum %d) — skipped",
                    line_number,
                    username,
                    len(password),
                    _MIN_PASSWORD_LEN,
                )
                errors += 1
                continue

            credentials.append((username, password))

    logger.info(
        "Loaded %d credentials from %s "
        "(%d comments/blanks skipped, %d format errors)",
        len(credentials),
        path.name,
        skipped,
        errors,
    )

    if not credentials:
        logger.warning(
            "No valid credentials found in %s. "
            "Add entries in the format: username:password",
            path.name,
        )

    return credentials


def mask_password(password: str) -> str:
    """
    Return a safe representation of a password for display purposes.
    Shows only the length. Never call str(password) in log messages.

    Example: mask_password("MyS3cur3P@ss!") → "[password:13chars]"
    """
    return f"[password:{len(password)}chars]"


def validate_accounts_file_exists(accounts_file: str | Path) -> bool:
    """
    Returns True if accounts.txt exists and is readable. Does not load contents.
    """
    path = Path(accounts_file)
    return path.exists() and path.is_file()
