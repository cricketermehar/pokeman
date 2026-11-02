"""Session State Manager.

Handles safe persistence, validation, expiration detection, and restoration of
authenticated browser storage states (cookies and local storage).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import os
import time

from src.logger import logger


@dataclass
class SessionValidationResult:
    is_valid: bool
    reason: Optional[str] = None
    cookie_count: int = 0
    expired_cookies: int = 0


class SessionManager:
    """Manages Playwright / Camoufox storage state files with strict security controls."""

    def __init__(self, session_dir: Path = Path("sessions")):
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            self.session_dir.chmod(0o700)

    def get_session_path(self, session_name: str) -> Path:
        """Returns sanitized filesystem path for the requested session identifier."""
        # Sanitize filename against directory traversal
        safe_name = "".join(c for c in session_name if c.isalnum() or c in ("-", "_"))
        if not safe_name:
            safe_name = "default_session"
        return self.session_dir / f"{safe_name}.json"

    def save_session(self, storage_state: Dict[str, Any], session_name: str = "authorized_session") -> Path:
        """Saves storage state dict to disk with 0o600 restricted file permissions."""
        target_path = self.get_session_path(session_name)
        
        # Serialize to formatted JSON
        serialized = json.dumps(storage_state, indent=2)
        
        # Write securely
        target_path.write_text(serialized, encoding="utf-8")
        if os.name == "posix":
            target_path.chmod(0o600)
            
        logger.info(
            f"Saved authenticated session state to {target_path.name} "
            f"(file permission: 0600, cookies: {len(storage_state.get('cookies', []))})"
        )
        return target_path

    def load_session(self, session_name: str = "authorized_session") -> Optional[Dict[str, Any]]:
        """Loads and returns storage state if it exists and passes validation."""
        path = self.get_session_path(session_name)
        if not path.exists():
            logger.debug(f"No existing session file at {path}")
            return None

        validation = self.validate_session_file(session_name)
        if not validation.is_valid:
            logger.warning(f"Session '{session_name}' failed validation: {validation.reason}. Invalidating.")
            self.invalidate_session(session_name)
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data
        except Exception as e:
            logger.error(f"Failed to read session file {path}: {e}")
            self.invalidate_session(session_name)
            return None

    def validate_session_file(self, session_name: str = "authorized_session") -> SessionValidationResult:
        """Inspects saved storage state JSON structure and checks for cookie expiration."""
        path = self.get_session_path(session_name)
        if not path.exists():
            return SessionValidationResult(is_valid=False, reason="File does not exist")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return SessionValidationResult(is_valid=False, reason=f"Malformed JSON: {e}")

        if not isinstance(data, dict):
            return SessionValidationResult(is_valid=False, reason="Root state must be a JSON object")

        cookies = data.get("cookies", [])
        if not isinstance(cookies, list):
            return SessionValidationResult(is_valid=False, reason="'cookies' field must be a list")

        if not cookies:
            return SessionValidationResult(is_valid=False, reason="No cookies stored in session state")

        now = time.time()
        expired_count = 0
        valid_cookie_count = 0

        for cookie in cookies:
            if not isinstance(cookie, dict) or "name" not in cookie or "value" not in cookie:
                return SessionValidationResult(is_valid=False, reason="Invalid cookie format")

            # Check expiration epoch if present (-1 or absent usually indicates session cookies)
            expires = cookie.get("expires")
            if expires is not None and expires != -1:
                if expires < now:
                    expired_count += 1
                else:
                    valid_cookie_count += 1
            else:
                # Session cookie (no fixed expiry)
                valid_cookie_count += 1

        if expired_count > 0 and valid_cookie_count == 0:
            return SessionValidationResult(
                is_valid=False,
                reason="All stored authentication cookies have expired",
                cookie_count=len(cookies),
                expired_cookies=expired_count,
            )

        return SessionValidationResult(
            is_valid=True,
            cookie_count=len(cookies),
            expired_cookies=expired_count,
        )

    def invalidate_session(self, session_name: str = "authorized_session") -> None:
        """Safely removes an expired or invalidated session file."""
        path = self.get_session_path(session_name)
        if path.exists():
            try:
                path.unlink()
                logger.info(f"Invalidated and removed session state: {path.name}")
            except OSError as e:
                logger.error(f"Failed to delete session file {path}: {e}")
