# AI Assistance Disclosure:
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-03
# Scope: Writing implementation code — write a test that the worker idles until its stop event is set.
# Author review: Keith confirmed review of all affected changes.
# Details: notification-service/ai/usage-log.md; ai-20261103-001

import threading

from app.config import Settings
from app.worker import run


def test_worker_idles_until_stopped() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://notification@db:5432/foc_notifications"
    )
    stop = threading.Event()
    thread = threading.Thread(target=run, args=(settings, stop), daemon=True)
    thread.start()

    thread.join(timeout=0.2)
    assert thread.is_alive()

    stop.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
