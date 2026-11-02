"""
main.py
=======
KinanCity Python Automation — entry point.

Usage:
    python main.py                   # process all QUEUED accounts
    python main.py --dry-run         # simulate without real HTTP calls
    python main.py --investigate     # run PTC investigator only
    python main.py --status          # show current queue state and exit
    python main.py --reset <user>    # reset one account to QUEUED
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from account_queue import AccountQueue
from account_record import AccountState
from mail_watcher import MailWatcher
from retry_handler import RetryHandler
from run_logger import RunLogger, get_logger
from state_machine import StateMachine, StubPtcHandler

CONFIG_FILE = "config.ini"
logger = get_logger("main")


def load_config() -> dict:
    """Load config.ini. Falls back to defaults if file missing."""
    import configparser
    config = configparser.ConfigParser()
    defaults = {
        "accounts_file": "accounts.txt",
        "state_file": "queue_state.json",
        "links_log": "links.log",
        "max_retries": "3",
        "base_delay_s": "60",
        "activation_timeout_s": "600",
        "email": "",
        "dry_run": "false",
    }
    config.read_dict({"kinancity": defaults})
    if Path(CONFIG_FILE).exists():
        config.read(CONFIG_FILE)
    return dict(config["kinancity"])


def cmd_status(queue: AccountQueue) -> None:
    """Print current queue state and exit."""
    queue.load()
    queue.print_summary()
    stats = queue.stats()
    pending = stats.get(AccountState.QUEUED.value, 0)
    manual = stats.get(AccountState.MANUAL_REQUIRED.value, 0)
    if manual > 0:
        print(f"\n⚠️  {manual} account(s) need manual attention — check queue_state.json")
    if pending == 0:
        print("✅ All accounts are in a terminal state")


def cmd_reset(queue: AccountQueue, username: str) -> None:
    """Reset one account back to QUEUED."""
    queue.load()
    record = queue.get(username)
    if not record:
        print(f"❌ Account '{username}' not found in accounts.txt")
        sys.exit(1)
    record.state = AccountState.QUEUED
    record.retries = 0
    record.last_error = None
    record.notes = "manually reset"
    queue.save()
    print(f"✅ Account '{username}' reset to QUEUED")


def cmd_investigate(cfg: dict) -> None:
    """Run PTC registration investigator and write report."""
    from ptc_investigator import PtcInvestigator
    output = Path("../Documentation/PTC_REGISTRATION_INVESTIGATION.md")
    investigator = PtcInvestigator(output_file=output)
    report = investigator.run()
    print(f"✅ Investigation report: {report.resolve()}")


def cmd_run(cfg: dict, dry_run: bool = False, ugphone: bool = False) -> None:
    """Main processing loop — drive every QUEUED account to terminal state."""
    # ── Setup logging ────────────────────────────────────────────────────────
    run_logger = RunLogger()
    run_logger.start()

    # ── Load queue ───────────────────────────────────────────────────────────
    queue = AccountQueue(
        accounts_file=cfg["accounts_file"],
        state_file=cfg["state_file"],
        max_retries=int(cfg["max_retries"]),
    )
    queue.load()

    if len(queue) == 0:
        logger.warning("No accounts found in %s — exiting", cfg["accounts_file"])
        run_logger.finish()
        return

    # ── Start mail watcher ───────────────────────────────────────────────────
    mail_watcher = MailWatcher(queue, links_log=cfg["links_log"])
    mail_watcher.start()

    # ── Build state machine & adapters ───────────────────────────────────────
    retry_handler = RetryHandler(
        max_retries=int(cfg["max_retries"]),
        base_delay_s=float(cfg["base_delay_s"]),
    )

    ugphone_handler = None
    if ugphone:
        from adapters.ugphone_adapter import UGPhoneAdapter
        ugphone_handler = UGPhoneAdapter(use_simulator=dry_run)
        logger.info("UGPhone / PGTools automation enabled (simulator=%s)", dry_run)

    machine = StateMachine(
        ptc_handler=StubPtcHandler() if dry_run else StubPtcHandler(),
        ugphone_handler=ugphone_handler,
        retry_handler=retry_handler,
        account_email=cfg["email"],
        activation_timeout_s=float(cfg["activation_timeout_s"]),
        dry_run=dry_run,
    )

    if dry_run:
        logger.info("DRY-RUN mode — simulation active")

    # ── Main loop ────────────────────────────────────────────────────────────
    completed = failed = manual = 0
    total = len(queue)

    while not queue.is_complete():
        record = queue.next()
        if record is None:
            break  # all terminal

        logger.info(
            "Processing [%s] (%d/%d)",
            record.username,
            completed + failed + manual + 1,
            total,
        )

        machine.run(record)
        queue.save()

        run_logger.log_account_event(
            username=record.username,
            event="FINISHED",
            state=record.state.value,
            detail=record.last_error or "",
        )

        if record.state == AccountState.COMPLETED:
            completed += 1
        elif record.state == AccountState.MANUAL_REQUIRED:
            manual += 1
        else:
            failed += 1

    # ── Shutdown ─────────────────────────────────────────────────────────────
    mail_watcher.stop()
    queue.print_summary()
    run_logger.finish(completed=completed, failed=failed, manual_required=manual, total=total)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="KinanCity Python Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                   Process all queued accounts
  python main.py --dry-run         Simulate without real HTTP calls
  python main.py --investigate     Run PTC flow investigator only
  python main.py --status          Show queue status and exit
  python main.py --reset trainer1  Reset trainer1 back to QUEUED
        """,
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulate without real HTTP calls")
    parser.add_argument("--ugphone", action="store_true", help="Enable UGPhone / PGTools automation flow")
    parser.add_argument("--investigate", action="store_true", help="Run PTC investigator and exit")
    parser.add_argument("--status", action="store_true", help="Show queue status and exit")
    parser.add_argument("--reset", metavar="USERNAME", help="Reset one account to QUEUED")

    args = parser.parse_args()
    cfg = load_config()

    if args.status:
        queue = AccountQueue(accounts_file=cfg["accounts_file"], state_file=cfg["state_file"])
        cmd_status(queue)
    elif args.reset:
        queue = AccountQueue(accounts_file=cfg["accounts_file"], state_file=cfg["state_file"])
        cmd_reset(queue, args.reset)
    elif args.investigate:
        cmd_investigate(cfg)
    else:
        cmd_run(cfg, dry_run=args.dry_run, ugphone=args.ugphone)


if __name__ == "__main__":
    main()
