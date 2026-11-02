"""Camoufox + Playwright Browser Lifecycle Manager.

Launches Camoufox in headed mode bound to the virtual X11 display, manages browser
contexts, handles timeouts, captures diagnostics, and ensures clean resource release.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import os
import time

try:
    from camoufox.sync_api import Camoufox
except ImportError:
    Camoufox = None

try:
    from playwright.sync_api import (
        Browser,
        BrowserContext,
        Page,
        TimeoutError as PlaywrightTimeoutError,
    )
except ImportError:
    Browser = Any  # type: ignore
    BrowserContext = Any  # type: ignore
    Page = Any  # type: ignore
    PlaywrightTimeoutError = Exception  # type: ignore

from src.config import Settings, settings
from src.logger import logger


class BrowserManager:
    """Orchestrates Camoufox (Playwright Firefox engine) on the virtual display."""

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or settings
        self.browser_cm: Optional[Camoufox] = None
        self.browser: Optional[Browser] = None
        self.active_contexts: list[BrowserContext] = []

    def _setup_display_environment(self) -> None:
        """Sets the DISPLAY environment variable to route browser windows to Xvfb."""
        # Check if an active display is recorded by start_display.sh
        active_disp_file = self.config.log_dir / "active_display.txt"
        if active_disp_file.exists():
            try:
                active_num = active_disp_file.read_text(encoding="utf-8").strip()
                if active_num:
                    target_disp = f":{active_num}"
                    os.environ["DISPLAY"] = target_disp
                    logger.debug(f"Assigned DISPLAY={target_disp} from active display file")
                    return
            except Exception:
                pass

        if "DISPLAY" not in os.environ or not os.environ["DISPLAY"]:
            target_disp = self.config.display_str
            os.environ["DISPLAY"] = target_disp
            logger.info(f"Exported virtual DISPLAY={target_disp}")

    def start_browser(self, headless: bool = False) -> Browser:
        """Launches the Camoufox browser instance in headed mode for X11/VNC."""
        self._setup_display_environment()
        current_disp = os.environ.get("DISPLAY", "Not set")
        logger.info(
            f"Launching Camoufox (Playwright Firefox) | Headless: {headless} | Display: {current_disp}"
        )

        try:
            # Camoufox context manager provides standard Playwright Browser instance
            self.browser_cm = Camoufox(
                headless=headless,
                screen={
                    "width": self.config.screen_width,
                    "height": self.config.screen_height,
                },
            )
            self.browser = self.browser_cm.__enter__()
            logger.info("Camoufox browser initialized successfully")
            return self.browser
        except Exception as e:
            logger.error(f"Failed to launch Camoufox browser: {e}", exc_info=True)
            self.teardown()
            raise

    def create_context(
        self,
        storage_state: Optional[Dict[str, Any]] = None,
        context_name: str = "default_context",
    ) -> BrowserContext:
        """Creates an isolated browser context with optional session state restoration."""
        if not self.browser:
            raise RuntimeError("Browser is not running. Call start_browser() first.")

        context_kwargs: Dict[str, Any] = {
            "viewport": {
                "width": self.config.screen_width,
                "height": self.config.screen_height,
            },
            "ignore_https_errors": False,
        }

        if storage_state:
            context_kwargs["storage_state"] = storage_state
            logger.info(
                f"Context '{context_name}': Restoring session state with {len(storage_state.get('cookies', []))} cookies"
            )

        context = self.browser.new_context(**context_kwargs)
        context.set_default_timeout(self.config.page_timeout_ms)
        self.active_contexts.append(context)
        return context

    def new_page(self, context: Optional[BrowserContext] = None) -> Page:
        """Opens a new page within the provided or a freshly created context."""
        ctx = context or self.create_context()
        page = ctx.new_page()
        page.set_default_timeout(self.config.page_timeout_ms)
        return page

    def capture_screenshot(self, page: Page, name_prefix: str = "diagnostic") -> Path:
        """Saves a timestamped diagnostic screenshot to the configured screenshot directory."""
        self.config.screenshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_prefix = "".join(c for c in name_prefix if c.isalnum() or c in ("-", "_"))
        target_path = self.config.screenshot_dir / f"{safe_prefix}_{timestamp}.png"

        try:
            page.screenshot(path=str(target_path), full_page=True)
            logger.info(f"Captured screenshot: {target_path.name}")
            return target_path
        except Exception as e:
            logger.warning(f"Failed to capture screenshot '{name_prefix}': {e}")
            return target_path

    def teardown(self) -> None:
        """Gracefully closes all contexts, pages, and terminates the browser process."""
        logger.info("Tearing down browser resources...")
        for ctx in self.active_contexts:
            try:
                ctx.close()
            except Exception as e:
                logger.debug(f"Context close error: {e}")
        self.active_contexts.clear()

        if self.browser:
            try:
                self.browser.close()
            except Exception as e:
                logger.debug(f"Browser close error: {e}")
            self.browser = None

        if self.browser_cm:
            try:
                self.browser_cm.__exit__(None, None, None)
            except Exception as e:
                logger.debug(f"Camoufox context manager exit error: {e}")
            self.browser_cm = None

        logger.info("Browser resources cleanly terminated.")
