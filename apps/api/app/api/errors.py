"""Map internal exceptions to stable public HTTP responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AppServerError,
    ConversationBusyError,
    ConversationNotFoundError,
    DuplicateSubmissionError,
    ProviderConfigurationError,
)


def register_exception_handlers(api: FastAPI) -> None:
    """Keep HTTP status policy at the transport boundary, outside services."""

    @api.exception_handler(ConversationNotFoundError)
    async def not_found(_: Request, exc: ConversationNotFoundError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @api.exception_handler(ConversationBusyError)
    async def conversation_busy(
        _: Request, exc: ConversationBusyError
    ) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @api.exception_handler(DuplicateSubmissionError)
    async def duplicate_submission(
        _: Request, exc: DuplicateSubmissionError
    ) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @api.exception_handler(AppServerError)
    async def app_server_failure(_: Request, exc: AppServerError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=502)

    @api.exception_handler(ProviderConfigurationError)
    async def provider_configuration_failure(
        _: Request, exc: ProviderConfigurationError
    ) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=400)
