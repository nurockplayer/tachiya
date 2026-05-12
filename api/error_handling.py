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


def _append_vary_origin(headers: dict[str, str]) -> None:
    existing_vary = headers.get("Vary")
    if not existing_vary:
        headers["Vary"] = "Origin"
        return

    vary_values = [value.strip() for value in existing_vary.split(",") if value.strip()]
    if "Origin" not in vary_values:
        vary_values.append("Origin")
    headers["Vary"] = ", ".join(vary_values)


def _build_internal_error_headers(request: Request) -> dict[str, str]:
    headers = {REQUEST_ID_HEADER: get_or_create_request_id(request)}
    request_origin = request.headers.get("Origin")
    allowed_origins = getattr(request.app.state, "cors_allowed_origins", ())

    if request_origin and request_origin in allowed_origins:
        headers["Access-Control-Allow-Origin"] = request_origin
        headers["Access-Control-Expose-Headers"] = REQUEST_ID_HEADER
        _append_vary_origin(headers)

    return headers


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
            headers=_build_internal_error_headers(request),
        )
