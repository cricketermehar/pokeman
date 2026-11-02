"""Main Automation Workflow Orchestrator.

Combines BrowserManager, SessionManager, and InteractiveAuthHandler into a robust,
re-usable execution flow.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
import time

try:
    from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
except ImportError:
    Page = Any  # type: ignore
    PlaywrightTimeoutError = Exception  # type: ignore

from src.authentication import InteractiveAuthHandler
from src.browser_manager import BrowserManager
from src.config import Settings, settings
from src.logger import logger
from src.session_manager import SessionManager


@dataclass
class WorkflowExecutionReport:
    success: bool
    initial_authenticated: bool
    manual_login_performed: bool
    final_url: str
    duration_sec: float
    error_message: Optional[str] = None
    diagnostic_screenshot: Optional[str] = None


class AutomationWorkflow:
    """End-to-end workflow runner for Camoufox + Playwright + Xvfb."""

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self.config.ensure_directories()
        self.session_manager = SessionManager(self.config.session_dir)
        self.auth_handler = InteractiveAuthHandler(self.config, self.session_manager)
        self.browser_manager = BrowserManager(self.config)

    def execute(
        self,
        target_url: Optional[str] = None,
        task_action: Optional[Callable[[Page], None]] = None,
        session_name: str = "authorized_session",
        headless: bool = False,
    ) -> WorkflowExecutionReport:
        """Executes the complete workflow: launch -> authenticate -> run task -> teardown."""
        start_time = time.time()
        url = target_url or self.config.target_url
        manual_login_done = False
        initial_auth = False
        screenshot_path: Optional[str] = None

        logger.info(f"▶ Starting automation workflow for target: {url}")

        try:
            # 1. Start browser
            self.browser_manager.start_browser(headless=headless)

            # 2. Check if an existing valid session is available
            saved_session = self.session_manager.load_session(session_name)
            context = self.browser_manager.create_context(
                storage_state=saved_session,
                context_name=session_name,
            )
            page = self.browser_manager.new_page(context)

            # 3. Navigate to target
            logger.info(f"Navigating to {url}...")
            page.goto(url, wait_until="domcontentloaded")

            # 4. Assess authentication
            auth_state = self.auth_handler.assess_authentication_state(page)
            if auth_state.is_authenticated:
                initial_auth = True
                logger.info("Session state restored and verified active.")
            else:
                logger.info(f"Authentication needed: {auth_state.details}")
                manual_login_done = True
                login_success = self.auth_handler.handle_interactive_login(
                    page=page,
                    browser_manager=self.browser_manager,
                    session_name=session_name,
                )
                if not login_success:
                    raise RuntimeError("Interactive authentication failed or timed out.")

            # 5. Execute authorized task
            if task_action:
                logger.info("Executing custom authorized browser task...")
                task_action(page)
            else:
                logger.info("Default task: verifying active page stability and capturing state.")
                page.wait_for_timeout(1000)

            # Capture completion screenshot
            final_screenshot = self.browser_manager.capture_screenshot(page, "workflow_completed")
            screenshot_path = str(final_screenshot)

            duration = round(time.time() - start_time, 2)
            logger.info(f"✅ Workflow completed successfully in {duration}s")

            return WorkflowExecutionReport(
                success=True,
                initial_authenticated=initial_auth,
                manual_login_performed=manual_login_done,
                final_url=page.url,
                duration_sec=duration,
                diagnostic_screenshot=screenshot_path,
            )

        except Exception as e:
            duration = round(time.time() - start_time, 2)
            err_msg = str(e)
            logger.error(f"❌ Workflow failed after {duration}s: {err_msg}", exc_info=True)
            
            # Try capturing failure diagnostic screenshot if page is alive
            try:
                for ctx in self.browser_manager.active_contexts:
                    if ctx.pages:
                        fail_shot = self.browser_manager.capture_screenshot(ctx.pages[0], "workflow_failure")
                        screenshot_path = str(fail_shot)
                        break
            except Exception:
                pass

            return WorkflowExecutionReport(
                success=False,
                initial_authenticated=initial_auth,
                manual_login_performed=manual_login_done,
                final_url=url,
                duration_sec=duration,
                error_message=err_msg,
                diagnostic_screenshot=screenshot_path,
            )

        finally:
            self.browser_manager.teardown()
