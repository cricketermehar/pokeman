"""Interactive Authentication & Operator Human-in-the-Loop Handler.

Detects authentication states, pauses for manual operator login via SSH-tunneled VNC,
and validates reliable post-login application conditions.
"""

from dataclasses import dataclass
from typing import Any, Optional
import time

try:
    from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
except ImportError:
    Page = Any  # type: ignore
    PlaywrightTimeoutError = Exception  # type: ignore

from src.browser_manager import BrowserManager
from src.config import Settings, settings
from src.logger import logger
from src.session_manager import SessionManager


@dataclass
class AuthCheckResult:
    is_authenticated: bool
    requires_login: bool
    current_url: str
    details: Optional[str] = None


class InteractiveAuthHandler:
    """Coordinates manual operator login over secure VNC with rigorous verification."""

    def __init__(
        self,
        config: Optional[Settings] = None,
        session_manager: Optional[SessionManager] = None,
    ):
        self.config = config or settings
        self.session_manager = session_manager or SessionManager(self.config.session_dir)

    def assess_authentication_state(self, page: Page) -> AuthCheckResult:
        """Inspects DOM indicators and URL to determine if authentication is active or required."""
        current_url = page.url

        # 1. Check for authenticated indicator selector
        try:
            auth_locator = page.locator(self.config.auth_success_selector).first
            if auth_locator.is_visible(timeout=2000):
                logger.info("Authentication verified: Success indicator selector detected in DOM.")
                return AuthCheckResult(
                    is_authenticated=True,
                    requires_login=False,
                    current_url=current_url,
                    details="Auth success indicator visible",
                )
        except Exception:
            pass

        # 2. Check for login prompt / login form indicators
        try:
            login_locator = page.locator(self.config.login_indicator_selector).first
            if login_locator.is_visible(timeout=2000):
                logger.info("Authentication required: Login form / input field detected.")
                return AuthCheckResult(
                    is_authenticated=False,
                    requires_login=True,
                    current_url=current_url,
                    details="Login input form visible",
                )
        except Exception:
            pass

        # 3. Fallback URL check
        if "/login" in current_url.lower() or "/signin" in current_url.lower() or "/auth" in current_url.lower():
            return AuthCheckResult(
                is_authenticated=False,
                requires_login=True,
                current_url=current_url,
                details=f"Current URL indicates login portal ({current_url})",
            )

        # Ambiguous state
        return AuthCheckResult(
            is_authenticated=False,
            requires_login=True,
            current_url=current_url,
            details="Neither authenticated dashboard nor explicit login selector confirmed",
        )

    def handle_interactive_login(
        self,
        page: Page,
        browser_manager: BrowserManager,
        session_name: str = "authorized_session",
    ) -> bool:
        """Pauses automation, presents SSH tunnel instructions, and awaits operator completion."""
        state = self.assess_authentication_state(page)
        if state.is_authenticated:
            logger.info("Session already authenticated; bypassing interactive login.")
            return True

        logger.warning(
            "══════════════════════════════════════════════════════════════════════\n"
            "  🔒 MANUAL OPERATOR LOGIN REQUIRED (Human-in-the-Loop)\n"
            "══════════════════════════════════════════════════════════════════════\n"
            f"The application requires authentication at: {page.url}\n\n"
            "Instructions to connect:\n"
            "1. Establish local SSH tunnel:\n"
            f"   ssh -N -L 5900:127.0.0.1:{self.config.vnc_port} user@your-server-ip\n\n"
            "2. Open VNC client (e.g. TigerVNC or Screen Sharing):\n"
            "   Connect to: vnc://localhost:5900\n\n"
            "3. Complete username, password, 2FA/MFA, or security verifications directly.\n"
            f"4. Automation will poll every {self.config.poll_interval_sec}s for up to {self.config.operator_timeout_sec}s.\n"
            "══════════════════════════════════════════════════════════════════════"
        )

        start_time = time.time()
        poll_count = 0

        while time.time() - start_time < self.config.operator_timeout_sec:
            poll_count += 1
            time.sleep(self.config.poll_interval_sec)

            # Re-evaluate verification condition
            # IMPORTANT: We check positive proof of successful login (e.g. dashboard selector)
            # NEVER treat mere disappearance of a CAPTCHA or submit button as proof!
            try:
                success_element = page.locator(self.config.auth_success_selector).first
                if success_element.is_visible(timeout=1000):
                    logger.info("✅ Login successfully verified by operator condition!")
                    
                    # Wait briefly for storage tokens / cookies to settle
                    page.wait_for_timeout(2000)
                    
                    # Capture authenticated session state
                    storage_state = page.context.storage_state()
                    self.session_manager.save_session(storage_state, session_name=session_name)
                    browser_manager.capture_screenshot(page, "login_success")
                    return True
            except Exception:
                pass

            if poll_count % 15 == 0:
                elapsed = int(time.time() - start_time)
                remaining = self.config.operator_timeout_sec - elapsed
                logger.info(f"Still waiting for operator login... ({remaining}s remaining)")

        # Timeout occurred
        logger.error(
            f"Operator login timed out after {self.config.operator_timeout_sec} seconds."
        )
        browser_manager.capture_screenshot(page, "login_timeout_diagnostic")
        return False
