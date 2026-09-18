"""Command line entry point: python3 -m restock_watch"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from . import __version__
from .config import ConfigError, load
from .notify import Alert, dispatch
from .state import State
from .watcher import NotificationDeliveryError, run_once

# Exit codes, chosen so a cron wrapper or monitor can act on them.
EXIT_IDLE = 0
EXIT_ALERTED = 2
#: An alert was due but no channel delivered it. State was not advanced, so
#: the next cycle retries — this is worth surfacing, not worth panicking over.
EXIT_DELIVERY_FAILED = 3
EXIT_CONFIG_ERROR = 42


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="restock-watch",
        description="Watch product pages and alert once when something becomes buyable.",
    )
    parser.add_argument(
        "-c", "--config", default="config.toml", help="path to config file (default: config.toml)"
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="keep running, sleeping interval_seconds between cycles "
        "(otherwise run one cycle and exit, for cron or a systemd timer)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="check and report, but send nothing and do not write state",
    )
    parser.add_argument(
        "--test-notify",
        action="store_true",
        help="send a test message on every enabled channel, then exit",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--version", action="version", version=f"restock-watch {__version__}")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        config = load(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    if args.test_notify:
        alert = Alert(
            title="restock-watch test",
            body="If you are reading this, this channel works.",
            changes=[],
            actionable=False,
        )
        results = dispatch(config.get("notify", {}), alert)
        if not results:
            print("no channels are enabled — check [notify] in your config", file=sys.stderr)
            return EXIT_CONFIG_ERROR
        for name, ok in sorted(results.items()):
            print(f"{name}: {'ok' if ok else 'FAILED'}")
        return EXIT_IDLE if all(results.values()) else 1

    general = config.get("general", {})
    state = State(Path(general.get("state_file", "data/state.json")))
    interval = int(general.get("interval_seconds", 300))

    if not args.loop:
        try:
            alerted = run_once(config, state, dry_run=args.dry_run)
        except NotificationDeliveryError as exc:
            # Expected operational failure, not a crash: report it the way a
            # cron or systemd wrapper can act on, without a stack trace.
            print(f"alert not delivered: {exc}", file=sys.stderr)
            return EXIT_DELIVERY_FAILED
        return EXIT_ALERTED if alerted else EXIT_IDLE

    logging.info("watching every %ss — Ctrl-C to stop", interval)
    while True:
        try:
            run_once(config, state, dry_run=args.dry_run)
        except KeyboardInterrupt:
            raise
        except NotificationDeliveryError as exc:
            # State was preserved, so the next cycle retries the alert.
            logging.error("%s — will retry next cycle", exc)
        except Exception:
            # A crash in one cycle must not end the watch.
            logging.exception("cycle failed, continuing")
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            logging.info("stopped")
            return EXIT_IDLE


if __name__ == "__main__":
    sys.exit(main())
