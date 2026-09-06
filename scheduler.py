"""Long-running scheduler: runs the job digest every day at 08:00 IST.

Uses zoneinfo("Asia/Kolkata") explicitly rather than the machine's local
timezone/clock settings, so behavior is correct even if the OS timezone is
ever changed or the process runs somewhere other than India.

Meant to be started once (e.g. at Windows logon, see README.md) and left
running in the background; it sleeps between runs and wakes daily at 08:00
IST. If the machine was off/asleep at 08:00, it catches up by running as
soon as the process is next alive that day, tracked via
data/last_run_date.txt (kept separate from the per-job seen_jobs.json
dedup history).
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from soc_job_agent.config import ConfigError, load_config
from soc_job_agent.logging_setup import setup_logging
from soc_job_agent.pipeline import run

IST = ZoneInfo("Asia/Kolkata")
TARGET_HOUR = 8
TARGET_MINUTE = 0
STATE_FILE = Path(__file__).resolve().parent / "data" / "last_run_date.txt"
MAX_SLEEP_CHUNK_SECONDS = 3600  # wake at least hourly so shutdown/Ctrl+C is responsive


def _read_last_run_date() -> str | None:
    if not STATE_FILE.exists():
        return None
    return STATE_FILE.read_text(encoding="utf-8").strip() or None


def _write_last_run_date(date_str: str) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(date_str, encoding="utf-8")


def _next_target(now: datetime) -> datetime:
    target_today = now.replace(hour=TARGET_HOUR, minute=TARGET_MINUTE, second=0, microsecond=0)
    if now < target_today:
        return target_today
    return target_today + timedelta(days=1)


def _sleep_until(target: datetime, logger) -> None:
    while True:
        now = datetime.now(IST)
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        chunk = min(remaining, MAX_SLEEP_CHUNK_SECONDS)
        logger.debug("Sleeping %.0fs (next run at %s IST)", chunk, target.isoformat())
        time.sleep(chunk)


def _run_once(logger) -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("Configuration error, skipping this run: %s", exc)
        return

    try:
        run(config)
    except Exception:
        logger.exception("Scheduled pipeline run failed")


def main() -> int:
    logger = setup_logging()
    logger.info("Scheduler started. Target: %02d:%02d IST daily.", TARGET_HOUR, TARGET_MINUTE)

    now = datetime.now(IST)
    today_str = now.date().isoformat()
    target_today = now.replace(hour=TARGET_HOUR, minute=TARGET_MINUTE, second=0, microsecond=0)

    if now >= target_today and _read_last_run_date() != today_str:
        logger.info("Catch-up run: today's %02d:%02d IST slot already passed and no run recorded yet.",
                    TARGET_HOUR, TARGET_MINUTE)
        _run_once(logger)
        _write_last_run_date(today_str)

    try:
        while True:
            now = datetime.now(IST)
            target = _next_target(now)
            _sleep_until(target, logger)

            run_date_str = target.date().isoformat()
            logger.info("Reached scheduled time %s IST -- running pipeline.", target.isoformat())
            _run_once(logger)
            _write_last_run_date(run_date_str)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
