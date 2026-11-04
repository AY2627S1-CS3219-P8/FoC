# AI Assistance Disclosure:
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-03
# Scope: Writing implementation code; Debugging assistance — write the FastAPI factory with startup configuration validation, a database-independent /health, and a /ready probe; after a frozen-database hang was observed, add a single-flight readiness probe with a hard deadline.
# Author review: Keith confirmed review of all affected changes.
# Details: notification-service/ai/usage-log.md; ai-20261103-001

"""FastAPI application factory for the Notification Service."""

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import Settings, configure_logging
from app.db import make_engine, make_session_factory

logger = logging.getLogger(__name__)

# Upper bound on how long GET /ready may take. Connect timeouts do not cover a
# pooled connection waiting on a server that stopped responding, so the probe
# itself runs under this deadline.
READY_TIMEOUT_SECONDS = 3.0


class ReadinessProbe:
    """Run database probes on one background thread with a hard deadline.

    At most one probe is in flight. If a previous probe is still blocked, the
    service is reported not ready without starting another one.
    """

    def __init__(self, engine: Engine, timeout_seconds: float) -> None:
        self._engine = engine
        self._timeout_seconds = timeout_seconds
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="readiness"
        )
        self._lock = threading.Lock()
        self._in_flight: Future | None = None

    def _ping(self) -> None:
        with self._engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def check(self) -> bool:
        with self._lock:
            if self._in_flight is not None and not self._in_flight.done():
                return False
            self._in_flight = self._executor.submit(self._ping)
            future = self._in_flight
        try:
            # Raises TimeoutError on deadline, or the probe's own error.
            future.result(timeout=self._timeout_seconds)
        except Exception:
            return False
        return True

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active_settings = settings or Settings.from_env()
        configure_logging(active_settings.log_level)
        app.state.settings = active_settings
        app.state.engine = make_engine(active_settings.database_url)
        app.state.session_factory = make_session_factory(app.state.engine)
        app.state.readiness = ReadinessProbe(
            app.state.engine, READY_TIMEOUT_SECONDS
        )
        try:
            yield
        finally:
            app.state.readiness.close()
            app.state.engine.dispose()

    app = FastAPI(
        title="FoC Notification Service", version="0.1.0", lifespan=lifespan
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/ready", response_model=None)
    def ready(request: Request) -> JSONResponse | dict[str, str]:
        if request.app.state.readiness.check():
            return {"status": "ready"}
        # Never expose database URLs, credentials, or driver diagnostics.
        logger.warning("Notification Service readiness check failed")
        return JSONResponse(status_code=503, content={"status": "not_ready"})

    return app


app = create_app()
