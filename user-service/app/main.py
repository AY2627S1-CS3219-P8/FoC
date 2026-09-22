"""FastAPI application entry point for the User Service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import Base, engine
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


app.include_router(users_router)
