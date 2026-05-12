from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from observability import (
    REQUEST_ID_HEADER,
    get_or_create_request_id,
    logger,
    log_structured_error_event,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def structured_http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ):
        log_structured_error_event(request=request, status_code=exc.status_code)
        return await http_exception_handler(request, exc)

    @app.exception_handler(Exception)
    async def structured_internal_error_handler(
        request: Request,
        exc: Exception,
    ):
        log_structured_error_event(request=request, status_code=500)
        logger.exception(
            "Unhandled exception",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
            headers={REQUEST_ID_HEADER: get_or_create_request_id(request)},
        )
