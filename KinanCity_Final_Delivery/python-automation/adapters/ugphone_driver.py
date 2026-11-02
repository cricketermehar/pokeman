"""
ugphone_driver.py
=================
Low-level device driver interface for UGPhone cloud Android instances.

Provides two driver implementations:
  1. AdbDriver: Communicates with real cloud devices via ADB (TCP/IP).
  2. MockDriver / SimulatedDriver: Deterministic in-memory simulation
     for local unit testing, CI pipelines, and offline dry-runs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from run_logger import get_logger

logger = get_logger("ugphone_driver")


class BaseUGPhoneDriver(ABC):
    """Abstract device driver for UGPhone cloud Android instance."""

    @abstractmethod
    def connect(self, host: str, port: int) -> bool:
        """Establish connection to cloud phone."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection cleanly."""
        pass

    @abstractmethod
    def tap(self, x: int, y: int) -> bool:
        """Tap screen coordinates."""
        pass

    @abstractmethod
    def input_text(self, text: str) -> bool:
        """Input text into focused field (never logs sensitive text)."""
        pass

    @abstractmethod
    def press_key(self, keycode: int) -> bool:
        """Send Android keyevent (e.g. 4 for BACK, 66 for ENTER)."""
        pass

    @abstractmethod
    def launch_app(self, package_name: str, activity_name: Optional[str] = None) -> bool:
        """Launch an Android package."""
        pass

    @abstractmethod
    def capture_screenshot(self, output_path: str) -> bool:
        """Take screenshot and save to disk."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if driver currently has an active connection."""
        pass


class AdbDriver(BaseUGPhoneDriver):
    """
    Real Android device driver via ADB over TCP/IP.
    Uses system 'adb' executable to communicate with cloud phone.
    """

    def __init__(self, adb_path: Optional[str] = None, timeout_s: float = 10.0):
        self._adb = adb_path or shutil.which("adb") or "adb"
        self._timeout_s = timeout_s
        self._target: Optional[str] = None
        self._connected: bool = False

    def is_connected(self) -> bool:
        return self._connected

    def connect(self, host: str, port: int = 5555) -> bool:
        self._target = f"{host}:{port}"
        logger.info("Connecting to cloud phone at %s...", self._target)
        try:
            res = subprocess.run(
                [self._adb, "connect", self._target],
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
            )
            if "connected" in res.stdout.lower() and "unable" not in res.stdout.lower():
                self._connected = True
                logger.info("Successfully connected to %s", self._target)
                return True
            else:
                logger.warning("Failed connecting to %s: %s", self._target, res.stdout.strip())
                self._connected = False
                return False
        except Exception as e:
            logger.error("ADB connection exception: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._target and self._connected:
            try:
                subprocess.run(
                    [self._adb, "disconnect", self._target],
                    capture_output=True,
                    timeout=5.0,
                )
            except Exception:
                pass
        self._connected = False

    def _shell(self, cmd_args: list[str]) -> Tuple[int, str]:
        if not self._connected or not self._target:
            return 1, "Not connected"
        try:
            full_cmd = [self._adb, "-s", self._target, "shell"] + cmd_args
            res = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
            )
            return res.returncode, res.stdout
        except Exception as e:
            return 1, str(e)

    def tap(self, x: int, y: int) -> bool:
        code, _ = self._shell(["input", "tap", str(x), str(y)])
        return code == 0

    def input_text(self, text: str) -> bool:
        # Avoid shell injection by escaping quotes/spaces if needed
        safe_text = text.replace(" ", "%s").replace("'", "\\'")
        code, _ = self._shell(["input", "text", safe_text])
        return code == 0

    def press_key(self, keycode: int) -> bool:
        code, _ = self._shell(["input", "keyevent", str(keycode)])
        return code == 0

    def launch_app(self, package_name: str, activity_name: Optional[str] = None) -> bool:
        if activity_name:
            target = f"{package_name}/{activity_name}"
            code, _ = self._shell(["am", "start", "-n", target])
        else:
            code, _ = self._shell(["monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])
        return code == 0

    def capture_screenshot(self, output_path: str) -> bool:
        if not self._connected or not self._target:
            return False
        remote_tmp = "/sdcard/screen_tmp.png"
        code, _ = self._shell(["screencap", "-p", remote_tmp])
        if code != 0:
            return False
        try:
            pull_res = subprocess.run(
                [self._adb, "-s", self._target, "pull", remote_tmp, output_path],
                capture_output=True,
                timeout=self._timeout_s,
            )
            self._shell(["rm", remote_tmp])
            return pull_res.returncode == 0
        except Exception as e:
            logger.error("Screenshot capture failed: %s", e)
            return False


class SimulatedDriver(BaseUGPhoneDriver):
    """
    In-memory simulated driver for testing and development.
    Models cloud phone lifecycle and in-game PGTools state transitions.
    """

    def __init__(self, initial_candy: int = 15):
        self._connected = False
        self._host: Optional[str] = None
        self._port: Optional[int] = None
        self.active_app: Optional[str] = None
        self.candy_count = initial_candy
        self.cp_sorted: bool = False
        self.powerup_count: int = 0
        self.quest_completed: bool = False
        self.reward_claimed: bool = False
        self.logged_in_user: Optional[str] = None

    def is_connected(self) -> bool:
        return self._connected

    def connect(self, host: str, port: int = 5555) -> bool:
        self._host = host
        self._port = port
        self._connected = True
        logger.info("[SimulatedDriver] Connected to mock device at %s:%d", host, port)
        return True

    def disconnect(self) -> None:
        self._connected = False
        self.active_app = None
        logger.info("[SimulatedDriver] Disconnected mock device")

    def tap(self, x: int, y: int) -> bool:
        if not self._connected:
            return False
        logger.debug("[SimulatedDriver] Tap at (%d, %d)", x, y)
        return True

    def input_text(self, text: str) -> bool:
        if not self._connected:
            return False
        logger.debug("[SimulatedDriver] Text input (length=%d)", len(text))
        return True

    def press_key(self, keycode: int) -> bool:
        if not self._connected:
            return False
        logger.debug("[SimulatedDriver] Keyevent %d", keycode)
        return True

    def launch_app(self, package_name: str, activity_name: Optional[str] = None) -> bool:
        if not self._connected:
            return False
        self.active_app = package_name
        logger.info("[SimulatedDriver] Launched app: %s", package_name)
        return True

    def capture_screenshot(self, output_path: str) -> bool:
        if not self._connected:
            return False
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            # Write a 1x1 dummy PNG
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
        return True
