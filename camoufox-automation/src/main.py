"""Command Line Interface Entrypoint for Camoufox Automation Framework.

Usage:
  python src/main.py                 # Normal run (headed in Xvfb display)
  python src/main.py --headless      # Run in headless mode
  python src/main.py --check         # Run diagnostic environment health checks
  python src/main.py --clear-session # Remove saved session file and re-authenticate
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings
from src.logger import logger
from src.session_manager import SessionManager
from src.workflow import AutomationWorkflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Camoufox + Playwright + Xvfb + x11vnc Automation Engine"
    )
    parser.add_argument(
        "--url",
        type=str,
        default=settings.target_url,
        help="Target web application URL to navigate and automate",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (default is headed inside Xvfb)",
    )
    parser.add_argument(
        "--session-name",
        type=str,
        default="authorized_session",
        help="Session identifier key for storage state persistence",
    )
    parser.add_argument(
        "--clear-session",
        action="store_true",
        help="Invalidate and purge existing session state before execution",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check virtual display and environment readiness",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.check:
        logger.info("Performing environment health check...")
        import subprocess
        script = Path(__file__).resolve().parent.parent / "scripts" / "health_check.sh"
        if script.exists():
            return subprocess.call(["bash", str(script)])
        else:
            logger.error("health_check.sh not found.")
            return 1

    if args.clear_session:
        sm = SessionManager(settings.session_dir)
        sm.invalidate_session(args.session_name)
        logger.info(f"Purged session state: {args.session_name}")

    workflow = AutomationWorkflow(settings)
    report = workflow.execute(
        target_url=args.url,
        session_name=args.session_name,
        headless=args.headless,
    )

    print("\n══════════════════════════════════════════════════════════════════════")
    print("  AUTOMATION EXECUTION REPORT")
    print(f"  Success               : {'✅ YES' if report.success else '❌ NO'}")
    print(f"  Initial Authenticated : {report.initial_authenticated}")
    print(f"  Manual Login Invoked  : {report.manual_login_performed}")
    print(f"  Final Target URL      : {report.final_url}")
    print(f"  Execution Duration    : {report.duration_sec}s")
    if report.error_message:
        print(f"  Error Details         : {report.error_message}")
    if report.diagnostic_screenshot:
        print(f"  Screenshot Evidence   : {report.diagnostic_screenshot}")
    print("══════════════════════════════════════════════════════════════════════\n")

    return 0 if report.success else 1


if __name__ == "__main__":
    sys.exit(main())
