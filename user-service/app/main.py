"""FastAPI application entry point for the User Service."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import SESSION_CLEANUP_INTERVAL, cleanup_sessions
from app.db import SessionLocal, get_db
from app.routes.users import router as users_router


logger = logging.getLogger(__name__)


def run_session_cleanup() -> None:
    """Delete unusable sessions in an independent database transaction."""

    with SessionLocal() as db:
        try:
            deleted = cleanup_sessions(db)
            db.commit()
            if deleted:
                logger.info("Removed %d expired or revoked sessions", deleted)
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Periodic session cleanup failed")


async def session_cleanup_loop() -> None:
    """Run session cleanup periodically until the application shuts down."""

    while True:
        run_session_cleanup()
        await asyncio.sleep(SESSION_CLEANUP_INTERVAL.total_seconds())


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run background maintenance while the application is serving requests."""

    cleanup_task = asyncio.create_task(session_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(title="FoC User Service", lifespan=lifespan)


@app.get("/health")
def health_check():
    """Return a simple liveness response for health checks."""

    return {"status": "healthy"}


@app.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """Return ready only when the database can execute a lightweight query."""

    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return {"status": "ready"}


app.include_router(users_router)
