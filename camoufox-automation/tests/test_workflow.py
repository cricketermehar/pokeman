"""Unit tests for InteractiveAuthHandler and AutomationWorkflow."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.authentication import InteractiveAuthHandler
from src.config import Settings
from src.session_manager import SessionManager
from src.workflow import AutomationWorkflow


@pytest.fixture
def workflow_setup(tmp_path: Path):
    cfg = Settings(
        _env_file=None,
        target_url="http://localhost:8000/dashboard",
        login_url="http://localhost:8000/login",
        session_dir=tmp_path / "sessions",
        screenshot_dir=tmp_path / "screenshots",
        log_dir=tmp_path / "logs",
        operator_timeout_sec=2,
        poll_interval_sec=0.1,
    )
    sm = SessionManager(cfg.session_dir)
    handler = InteractiveAuthHandler(cfg, sm)
    return cfg, sm, handler


def test_auth_assessment_detects_authenticated_element(workflow_setup):
    cfg, sm, handler = workflow_setup
    mock_page = MagicMock()
    mock_page.url = "http://localhost:8000/dashboard"

    # Simulate success selector being visible
    mock_locator = MagicMock()
    mock_locator.is_visible.return_value = True
    mock_page.locator.return_value.first = mock_locator

    result = handler.assess_authentication_state(mock_page)
    assert result.is_authenticated
    assert not result.requires_login


def test_auth_assessment_detects_login_required(workflow_setup):
    cfg, sm, handler = workflow_setup
    mock_page = MagicMock()
    mock_page.url = "http://localhost:8000/login"

    # Simulate success selector false, login form true
    def locator_mock(selector):
        loc = MagicMock()
        if "dashboard" in selector or "profile" in selector:
            loc.first.is_visible.return_value = False
        else:
            loc.first.is_visible.return_value = True
        return loc

    mock_page.locator.side_effect = locator_mock

    result = handler.assess_authentication_state(mock_page)
    assert not result.is_authenticated
    assert result.requires_login


def test_interactive_login_times_out(workflow_setup):
    cfg, sm, handler = workflow_setup
    mock_page = MagicMock()
    mock_page.url = "http://localhost:8000/login"
    mock_bm = MagicMock()

    # Neither indicator becomes visible
    mock_locator = MagicMock()
    mock_locator.is_visible.return_value = False
    mock_page.locator.return_value.first = mock_locator

    clock = [100.0]

    def advancing_time():
        current = clock[0]
        clock[0] += 5.0  # Advances 5 seconds every call, exceeding operator_timeout_sec=2
        return current

    with patch("time.sleep"), patch("time.time", side_effect=advancing_time):
        success = handler.handle_interactive_login(mock_page, mock_bm)

    assert not success
    mock_bm.capture_screenshot.assert_called_with(mock_page, "login_timeout_diagnostic")


def test_workflow_execution_report_structure(tmp_path: Path):
    cfg = Settings(
        _env_file=None,
        session_dir=tmp_path / "sessions",
        screenshot_dir=tmp_path / "screenshots",
        log_dir=tmp_path / "logs",
    )
    workflow = AutomationWorkflow(cfg)

    # Mock browser and auth
    with patch.object(workflow.browser_manager, "start_browser"), \
         patch.object(workflow.browser_manager, "create_context") as mock_ctx, \
         patch.object(workflow.browser_manager, "new_page") as mock_page_factory, \
         patch.object(workflow.auth_handler, "assess_authentication_state") as mock_assess, \
         patch.object(workflow.browser_manager, "teardown"):

        mock_page = MagicMock()
        mock_page.url = "http://localhost:8000/dashboard"
        mock_page_factory.return_value = mock_page

        mock_assess.return_value = MagicMock(is_authenticated=True, details="OK")

        report = workflow.execute(target_url="http://localhost:8000/dashboard")

        assert report.success
        assert report.initial_authenticated
        assert not report.manual_login_performed
        assert report.final_url == "http://localhost:8000/dashboard"
        assert report.duration_sec >= 0
