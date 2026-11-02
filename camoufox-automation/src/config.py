"""Configuration Management for Camoufox + Playwright Automation.

Loads environment variables with robust validation and sensible defaults.
"""

from pathlib import Path
from typing import List, Optional
import os
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application and environment configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Virtual X11 Display
    display_num: int = Field(default=99, validation_alias="DISPLAY_NUM")
    screen_width: int = Field(default=1920, validation_alias="SCREEN_WIDTH")
    screen_height: int = Field(default=1080, validation_alias="SCREEN_HEIGHT")
    screen_depth: int = Field(default=24, validation_alias="SCREEN_DEPTH")

    # Remote Desktop / VNC
    vnc_port: int = Field(default=5900, validation_alias="VNC_PORT")
    vnc_passwd_file: str = Field(default="~/.vnc/passwd", validation_alias="VNC_PASSWD_FILE")
    vnc_localhost_only: bool = Field(default=True, validation_alias="VNC_LOCALHOST_ONLY")

    # Target Web Application
    target_url: str = Field(
        default="http://localhost:8000/dashboard", validation_alias="TARGET_URL"
    )
    login_url: str = Field(
        default="http://localhost:8000/login", validation_alias="LOGIN_URL"
    )
    login_indicator_selector: str = Field(
        default="#login-form, input[name='username'], input[name='email'], #id_username",
        validation_alias="LOGIN_INDICATOR_SELECTOR",
    )
    auth_success_selector: str = Field(
        default="#dashboard, #user-profile, .authenticated, a[href*='logout']",
        validation_alias="AUTH_SUCCESS_SELECTOR",
    )

    # Human-in-the-Loop Operator Timeouts
    operator_timeout_sec: int = Field(default=300, validation_alias="OPERATOR_TIMEOUT_SEC")
    poll_interval_sec: float = Field(default=2.0, validation_alias="POLL_INTERVAL_SEC")
    page_timeout_ms: int = Field(default=30000, validation_alias="PAGE_TIMEOUT_MS")

    # Directory Paths
    session_dir: Path = Field(default=Path("sessions"), validation_alias="SESSION_DIR")
    screenshot_dir: Path = Field(
        default=Path("screenshots"), validation_alias="SCREENSHOT_DIR"
    )
    log_dir: Path = Field(default=Path("logs"), validation_alias="LOG_DIR")
    session_file: Path = Field(
        default=Path("sessions/authorized_session.json"), validation_alias="SESSION_FILE"
    )

    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    structured_logging: bool = Field(default=True, validation_alias="STRUCTURED_LOGGING")

    @field_validator("operator_timeout_sec")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("operator_timeout_sec must be positive")
        return v

    @property
    def display_str(self) -> str:
        """Formatted display string for X11 environment (e.g. ':99')."""
        return f":{self.display_num}"

    def ensure_directories(self) -> None:
        """Ensures that required local runtime directories exist with restricted permissions."""
        for path in (self.session_dir, self.screenshot_dir, self.log_dir):
            path.mkdir(parents=True, exist_ok=True)
            # Enforce 0700 on sessions directory for security
            if path == self.session_dir and os.name == "posix":
                path.chmod(0o700)


# Singleton settings instance
settings = Settings()
