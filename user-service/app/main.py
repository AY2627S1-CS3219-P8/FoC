"""FastAPI application entry point for the User Service."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.routes.users import router as users_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create the database tables when the application starts."""

    Base.metadata.create_all(bind=engine)
    yield


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
