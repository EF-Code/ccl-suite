"""Run periodic, retry-safe task deadline reminder evaluations."""

from __future__ import annotations

import argparse
import logging
import os
import time
from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from database import SessionLocal
from task_reminders import evaluate_task_deadline_reminders

DEFAULT_INTERVAL_SECONDS = 900
MIN_INTERVAL_SECONDS = 30
MAX_INTERVAL_SECONDS = 86_400
DEFAULT_TIMEZONE = "UTC"

logger = logging.getLogger("ccl.task_reminder_worker")


def configured_interval_seconds() -> int:
    """Read and validate the polling interval without exposing environment data."""

    raw_interval = os.getenv("CCL_TASK_REMINDER_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS))
    try:
        interval = int(raw_interval)
    except ValueError as exc:
        raise ValueError("CCL_TASK_REMINDER_INTERVAL_SECONDS must be an integer.") from exc
    if not MIN_INTERVAL_SECONDS <= interval <= MAX_INTERVAL_SECONDS:
        raise ValueError(
            "CCL_TASK_REMINDER_INTERVAL_SECONDS must be between 30 and 86400."
        )
    return interval


def configured_timezone() -> ZoneInfo:
    """Read the IANA timezone used to interpret date-only task deadlines."""

    timezone_name = os.getenv("CCL_TASK_REMINDER_TIMEZONE", DEFAULT_TIMEZONE)
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("CCL_TASK_REMINDER_TIMEZONE must be a valid IANA timezone.") from exc


def run_once(
    session_factory: Callable = SessionLocal,
    *,
    today: date | None = None,
) -> int:
    """Evaluate reminders once using the configured local calendar date."""

    reminder_date = today or datetime.now(configured_timezone()).date()
    with session_factory() as db:
        return evaluate_task_deadline_reminders(db, today=reminder_date)


def run_forever(
    *,
    interval_seconds: int | None = None,
    session_factory: Callable = SessionLocal,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Run immediately, then repeat; recover from transient database errors."""

    interval = interval_seconds if interval_seconds is not None else configured_interval_seconds()
    if not MIN_INTERVAL_SECONDS <= interval <= MAX_INTERVAL_SECONDS:
        raise ValueError("Reminder interval is outside the supported range.")
    configured_timezone()

    while True:
        try:
            created = run_once(session_factory)
        except Exception as exc:
            logger.error("Task reminder evaluation failed (%s).", type(exc).__name__)
        else:
            logger.info("Task reminder evaluation completed; new reminders=%d.", created)
        sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate task deadline reminders.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="evaluate reminders once and exit",
    )
    arguments = parser.parse_args()
    if arguments.once:
        logger.info("Task reminder evaluation completed; new reminders=%d.", run_once())
        return
    run_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
