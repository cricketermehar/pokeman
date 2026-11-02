"""
run_logger.py
=============
Structured per-run logger for KinanCity Python automation.

Behaviour:
  - Each run gets its own log file: logs/kinancity_run_YYYYMMDD_HHMMSS.log
  - A machine-readable JSON summary is written at run end: logs/kinancity_summary_YYYYMMDD_HHMMSS.json
  - Passwords are NEVER written to any output by this module.
  - Usernames appear in logs only for status tracking.
  - Console output mirrors the log file (INFO level by default).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


LOG_DIR = Path("logs")
_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
_LOG_LINE_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class RunLogger:
    """
    Sets up the Python logging framework for a single KinanCity run.

    Usage:
        run_logger = RunLogger()
        run_logger.start()
        ...
        run_logger.finish(completed=5, failed=1, manual=0)
    """

    def __init__(self, log_dir: str | Path = LOG_DIR):
        self._log_dir = Path(log_dir)
        self._timestamp = datetime.now().strftime(_TIMESTAMP_FORMAT)
        self._log_file = self._log_dir / f"kinancity_run_{self._timestamp}.log"
        self._summary_file = self._log_dir / f"kinancity_summary_{self._timestamp}.json"
        self._start_time: Optional[float] = None
        self._events: List[dict] = []

        # Root logger for the automation package
        self._logger = logging.getLogger("kinancity")

    def start(self, level: int = logging.INFO) -> None:
        """Configure handlers and mark run start. Call once at startup."""
        self._log_dir.mkdir(parents=True, exist_ok=True)

        self._logger.setLevel(level)
        self._logger.handlers.clear()

        # File handler — full detail
        file_handler = logging.FileHandler(self._log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(_LOG_LINE_FORMAT, datefmt=_DATE_FORMAT))

        # Console handler — INFO and above
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(_LOG_LINE_FORMAT, datefmt=_DATE_FORMAT))

        self._logger.addHandler(file_handler)
        self._logger.addHandler(console_handler)

        self._start_time = time.time()
        self._logger.info("═" * 60)
        self._logger.info("KinanCity Automation — Run started")
        self._logger.info("Log file : %s", self._log_file)
        self._logger.info("═" * 60)

    def log_account_event(
        self,
        username: str,
        event: str,
        state: str,
        detail: str = "",
    ) -> None:
        """
        Record a per-account lifecycle event.
        username and state are logged. Passwords must never be passed here.
        """
        self._logger.info("[%s] %s → %s  %s", username, event, state, detail)
        self._events.append(
            {
                "t": time.time(),
                "username": username,
                "event": event,
                "state": state,
                "detail": detail,
            }
        )

    def log_warning(self, msg: str, *args) -> None:
        self._logger.warning(msg, *args)

    def log_error(self, msg: str, *args) -> None:
        self._logger.error(msg, *args)

    def finish(
        self,
        completed: int = 0,
        failed: int = 0,
        manual_required: int = 0,
        total: int = 0,
    ) -> None:
        """Write the JSON summary and log the final run stats."""
        elapsed = time.time() - (self._start_time or time.time())

        summary: Dict = {
            "run_timestamp": self._timestamp,
            "elapsed_seconds": round(elapsed, 1),
            "total_accounts": total,
            "completed": completed,
            "failed": failed,
            "manual_required": manual_required,
            "log_file": str(self._log_file),
            "events": self._events,
            # No passwords in summary
        }

        with self._summary_file.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        self._logger.info("═" * 60)
        self._logger.info("Run complete in %.1fs", elapsed)
        self._logger.info(
            "Results — Total: %d | Completed: %d | Failed: %d | Manual: %d",
            total,
            completed,
            failed,
            manual_required,
        )
        self._logger.info("Summary saved → %s", self._summary_file)
        self._logger.info("═" * 60)

    @property
    def log_file_path(self) -> Path:
        return self._log_file

    @property
    def summary_file_path(self) -> Path:
        return self._summary_file


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger under the 'kinancity' namespace.
    Use this in every module instead of logging.getLogger(__name__).

    Example:
        logger = get_logger("account_queue")
    """
    return logging.getLogger(f"kinancity.{name}")
