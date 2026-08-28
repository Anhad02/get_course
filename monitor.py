"""Entry point: periodically checks a UW Waterloo course section for open seats
and sends a notification when one becomes available.

Usage:
    python monitor.py           # run forever, checking on an interval
    python monitor.py --once    # check a single time and exit (good for cron)
    python monitor.py --test-notify   # send a test notification and exit
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

import notifier
import scraper


def _log(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def load_config() -> dict:
    load_dotenv()
    try:
        interval = int(os.environ.get("CHECK_INTERVAL_MINUTES", "10"))
    except ValueError:
        interval = 10
    return {
        "subject": os.environ.get("SUBJECT", "").strip(),
        "course_number": os.environ.get("COURSE_NUMBER", "").strip(),
        "section": os.environ.get("SECTION", "").strip(),
        "level": os.environ.get("LEVEL", "under").strip() or "under",
        "session": os.environ.get("SESSION", "").strip(),
        "interval_minutes": interval,
        "notify_method": os.environ.get("NOTIFY_METHOD", "twilio_sms").strip(),
    }


def validate_config(cfg: dict) -> list[str]:
    errors = []
    for key in ("subject", "course_number", "section", "session"):
        if not cfg[key]:
            errors.append(f"{key.upper()} is not set in .env")
    return errors


def check_once(cfg: dict) -> tuple[bool, list]:
    """Check the target section once.

    Returns (any_open, sections) where any_open is True if at least one matching
    section has an open seat. Logs the status of every matching section.
    """
    sections = scraper.check_availability(
        subject=cfg["subject"],
        course_number=cfg["course_number"],
        section=cfg["section"],
        level=cfg["level"],
        session=cfg["session"],
    )
    any_open = False
    for s in sections:
        status = "OPEN" if s.has_seat else "full"
        _log(
            f"{cfg['subject'].upper()} {cfg['course_number']} "
            f"{s.raw_comp_sec}: {s.enrol_total}/{s.enrol_cap} seats used "
            f"({status})"
        )
        if s.has_seat:
            any_open = True
    return any_open, sections


def build_message(cfg: dict, sections) -> str:
    open_secs = [s for s in sections if s.has_seat]
    details = "; ".join(
        f"{s.raw_comp_sec} {s.seats_open} seat(s) free ({s.enrol_total}/{s.enrol_cap})"
        for s in open_secs
    )
    return (
        f"Seat available in {cfg['subject'].upper()} {cfg['course_number']} "
        f"section {cfg['section']}! {details}. "
        f"Register: https://classes.uwaterloo.ca/"
    )


def notify_safe(cfg: dict, message: str) -> bool:
    try:
        notifier.notify(cfg["notify_method"], "Course seat available", message)
        _log(f"Notification sent via {cfg['notify_method']}.")
        return True
    except notifier.NotifyError as exc:
        _log(f"NOTIFICATION FAILED: {exc}")
        return False


def run_forever(cfg: dict) -> None:
    interval_s = max(cfg["interval_minutes"], 1) * 60
    _log(
        f"Monitoring {cfg['subject'].upper()} {cfg['course_number']} "
        f"section {cfg['section']} (term {cfg['session']}) "
        f"every {cfg['interval_minutes']} min. Notify via {cfg['notify_method']}."
    )
    # Re-arm logic: only notify on a full -> open transition so we don't send a
    # message every interval while the seat stays open.
    was_open = False
    while True:
        try:
            any_open, sections = check_once(cfg)
            if any_open and not was_open:
                notify_safe(cfg, build_message(cfg, sections))
            was_open = any_open
        except scraper.ScrapeError as exc:
            _log(f"Check failed: {exc}")
        except Exception as exc:  # keep the loop alive on unexpected errors
            _log(f"Unexpected error: {exc}")
        time.sleep(interval_s)


def main() -> int:
    parser = argparse.ArgumentParser(description="UW Waterloo course seat monitor")
    parser.add_argument(
        "--once", action="store_true", help="check a single time and exit"
    )
    parser.add_argument(
        "--test-notify",
        action="store_true",
        help="send a test notification and exit",
    )
    args = parser.parse_args()

    cfg = load_config()

    if args.test_notify:
        ok = notify_safe(cfg, "Test notification from the course seat monitor.")
        return 0 if ok else 1

    errors = validate_config(cfg)
    if errors:
        for e in errors:
            _log(f"Config error: {e}")
        _log("Copy .env.example to .env and fill in the values.")
        return 1

    if args.once:
        try:
            any_open, sections = check_once(cfg)
        except scraper.ScrapeError as exc:
            _log(f"Check failed: {exc}")
            return 1
        if any_open:
            notify_safe(cfg, build_message(cfg, sections))
        return 0

    try:
        run_forever(cfg)
    except KeyboardInterrupt:
        _log("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
