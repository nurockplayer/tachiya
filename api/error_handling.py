from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from observability import log_structured_error_event


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def structured_http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ):
        log_structured_error_event(request=request, status_code=exc.status_code)
        return await http_exception_handler(request, exc)
