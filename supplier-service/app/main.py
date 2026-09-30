from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import create_db_engine, create_session_factory
from app.config import Settings
from app.routes.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings is None:
            app.state.settings = Settings()
        else:
            app.state.settings = settings

        app.state.engine = create_db_engine(app.state.settings)

        try:
            app.state.session_factory = create_session_factory(app.state.engine)
            yield
        finally:
            app.state.engine.dispose()

    app = FastAPI(
        title="FoC Supplier Service",
        lifespan=lifespan,
    )

    # Register health_router with this application
    app.include_router(health_router)

    return app

app = create_app()
