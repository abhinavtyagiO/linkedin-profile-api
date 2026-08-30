"""FastAPI entry point for the hosted JSON API."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import ConfigurationError
from .errors import ProfileApiError, ServerConfigurationError
from .models import ErrorBody, FetchProfileRequest, ProfileResponse
from .service import ProfileService


def create_app(service: Optional[ProfileService] = None) -> FastAPI:
    app = FastAPI(
        title="LinkedIn Profile API",
        version="0.1.0",
        description=(
            "Reverse-engineered profile normalizer that directly calls LinkedIn's "
            "authenticated Flagship endpoints. No browser automation runs in production."
        ),
    )
    app.state.profile_service = service

    @app.exception_handler(ProfileApiError)
    async def profile_error_handler(_request: Request, exc: ProfileApiError) -> JSONResponse:
        body = ErrorBody(
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
        )
        return JSONResponse(status_code=exc.http_status, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        body = ErrorBody(
            code="invalid_request",
            message="Request body is invalid",
            retryable=False,
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post(
        "/v1/profiles:fetch",
        response_model=ProfileResponse,
        response_model_exclude_none=True,
        response_model_exclude_defaults=True,
        responses={
            500: {"model": ErrorBody},
            404: {"model": ErrorBody},
            422: {"model": ErrorBody},
            502: {"model": ErrorBody},
            503: {"model": ErrorBody},
        },
    )
    async def fetch_profile(payload: FetchProfileRequest) -> ProfileResponse:
        active_service = app.state.profile_service
        if active_service is None:
            try:
                active_service = ProfileService.from_env()
            except ConfigurationError as exc:
                raise ServerConfigurationError(
                    "Server credentials are not configured"
                ) from exc
            app.state.profile_service = active_service
        return await run_in_threadpool(active_service.fetch, payload.profile_url)

    return app


app = create_app()
