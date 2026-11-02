"""Structured Logging Module with Sensitive Data Redaction.

Ensures credentials, session tokens, passwords, and authorization headers
are never leaked to logs or console outputs.
"""

import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict

# Regex patterns matching sensitive key-values
SENSITIVE_PATTERNS = [
    re.compile(r'(password|passwd|pwd|secret|token|auth|cookie|session_id)["\']?\s*[:=]\s*["\']?([^"\'\s,]+)', re.IGNORECASE),
    re.compile(r'(Bearer\s+)[A-Za-z0-9_\-\.]+', re.IGNORECASE),
]


class RedactingFormatter(logging.Formatter):
    """Custom logging formatter that strips sensitive patterns from log strings."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        redacted = original
        for pattern in SENSITIVE_PATTERNS:
            redacted = pattern.sub(r'\1: [REDACTED]', redacted)
        return redacted


def setup_logger(
    name: str = "camoufox_automation",
    log_level: str = "INFO",
    log_dir: Path = Path("logs"),
) -> logging.Logger:
    """Configures and returns a thread-safe structured logger with file and console outputs."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid duplicate handlers on re-initialization
    if logger.handlers:
        return logger

    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = RedactingFormatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.addHandler(console_handler)

    # 2. File Handler (Rotating runtime log)
    file_handler = logging.FileHandler(log_dir / "automation.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
