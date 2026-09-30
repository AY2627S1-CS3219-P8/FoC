from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.routes.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Use the supplied settings if present, otherwise create Settings() to read the environment
        # Store the result on app.state.settings
        if settings is None:
            app.state.settings = Settings()
        else:
            app.state.settings = settings
        yield

        # Future cleanup of shared resources belongs here

    app = FastAPI(
        title="FoC Supplier Service",
        lifespan=lifespan,
    )

    # Register health_router with this application
    app.include_router(health_router)

    return app


app = create_app()
