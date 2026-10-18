# AI Assistance Disclosure:
# Tool: Codex (model: GPT-6), date: 2026-09-30
# Scope: Writing implementation code — register shared-domain and FastAPI request-validation exception handlers in the existing application factory, returning HTTP 422 through the shared formatter.
# Author review: Keith confirmed review of all affected HTTP validation changes.
# Details: ../ai/usage-log.md; ai-20260930-003

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.db import create_db_engine, create_session_factory
from app.config import Settings
from app.routes.health import router as health_router
from app.validation.errors import DomainValidationError, request_validation_issues


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

    @app.exception_handler(DomainValidationError)
    async def domain_validation_handler(
        request: Request, error: DomainValidationError,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content=error.to_dict())

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, error: RequestValidationError,
    ) -> JSONResponse:
        validation = DomainValidationError(request_validation_issues(error.errors()))
        return JSONResponse(status_code=422, content=validation.to_dict())

    # Register health_router with this application
    app.include_router(health_router)

    return app

app = create_app()
