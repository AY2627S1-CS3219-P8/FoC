# AI Assistance Disclosure:
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-03
# Scope: Writing implementation code — write a worker that validates configuration, logs startup, idles until SIGTERM/SIGINT, and exits non-zero on invalid configuration.
# Author review: Keith confirmed review of all affected changes.
# Details: notification-service/ai/usage-log.md; ai-20261103-001

"""Notification worker process.

For now the worker only validates configuration, logs that it started, and
idles until it is asked to stop. Kafka consumption will be added later.
"""

import logging
import signal
import threading

from app.config import Settings, configure_logging

logger = logging.getLogger(__name__)


def run(settings: Settings, stop: threading.Event) -> None:
    """Idle until ``stop`` is set."""

    logger.info("notification_worker_started")
    stop.wait()
    logger.info("notification_worker_stopped")


def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    stop = threading.Event()

    def request_stop(signum: int, _frame) -> None:
        logger.info("notification_worker_stopping signal=%s", signum)
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    run(settings, stop)


if __name__ == "__main__":
    main()
