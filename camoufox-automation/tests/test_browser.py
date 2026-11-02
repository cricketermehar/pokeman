"""Unit tests for BrowserManager and Display configuration."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.browser_manager import BrowserManager
from src.config import Settings


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        display_num=99,
        screen_width=1280,
        screen_height=720,
        session_dir=tmp_path / "sessions",
        screenshot_dir=tmp_path / "screenshots",
        log_dir=tmp_path / "logs",
    )


def test_display_environment_setup(mock_settings: Settings):
    bm = BrowserManager(config=mock_settings)
    with patch.dict(os.environ, {}, clear=True):
        bm._setup_display_environment()
        assert os.environ.get("DISPLAY") == ":99"


def test_active_display_file_override(mock_settings: Settings):
    mock_settings.log_dir.mkdir(parents=True, exist_ok=True)
    active_file = mock_settings.log_dir / "active_display.txt"
    active_file.write_text("105", encoding="utf-8")

    bm = BrowserManager(config=mock_settings)
    with patch.dict(os.environ, {}, clear=True):
        bm._setup_display_environment()
        assert os.environ.get("DISPLAY") == ":105"


def test_browser_teardown_cleans_resources(mock_settings: Settings):
    bm = BrowserManager(config=mock_settings)
    mock_browser = MagicMock()
    mock_ctx = MagicMock()
    mock_cm = MagicMock()

    bm.browser = mock_browser
    bm.browser_cm = mock_cm
    bm.active_contexts = [mock_ctx]

    bm.teardown()

    mock_ctx.close.assert_called_once()
    mock_browser.close.assert_called_once()
    mock_cm.__exit__.assert_called_once()
    assert bm.browser is None
    assert bm.browser_cm is None
    assert len(bm.active_contexts) == 0


def test_screenshot_capture(mock_settings: Settings):
    bm = BrowserManager(config=mock_settings)
    mock_page = MagicMock()

    path = bm.capture_screenshot(mock_page, "test_evidence")
    mock_page.screenshot.assert_called_once()
    assert "test_evidence" in path.name
    assert path.suffix == ".png"
