import json
import sys
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from observability import log_structured_error_event


TEST_ROUTE_PREFIX = "/__test_observability"


def _ensure_test_routes() -> None:
    existing_paths = {route.path for route in main.app.routes}
    http_exception_path = f"{TEST_ROUTE_PREFIX}/http-exception"

    if http_exception_path not in existing_paths:

        @main.app.get(http_exception_path)
        def raise_http_exception() -> None:
            raise HTTPException(status_code=418, detail="teapot detail")


def _build_app_client(*, raise_server_exceptions: bool = True) -> TestClient:
    _ensure_test_routes()
    return TestClient(main.app, raise_server_exceptions=raise_server_exceptions)


def _record_payload(record: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    structured_event = getattr(record, "structured_event", None)
    if isinstance(structured_event, dict):
        payload.update(structured_event)

    message = record.msg
    if isinstance(message, dict):
        payload.update(message)
    elif isinstance(message, str):
        try:
            decoded = json.loads(record.getMessage())
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            payload.update(decoded)

    extra = getattr(record, "__dict__", {})
    payload.update(
        {
            key: extra[key]
            for key in (
                "event_name",
                "error_code",
                "request_id",
                "outcome",
                "severity",
                "status_code",
                "path",
                "method",
            )
            if key in extra
        }
    )
    return payload


def test_response_echoes_request_id_header():
    client = _build_app_client()

    response = client.get("/health", headers={"X-Request-ID": "req-from-client"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-from-client"


def test_response_generates_request_id_when_header_missing():
    client = _build_app_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_http_exception_preserves_detail_contract():
    client = _build_app_client()

    response = client.get(f"{TEST_ROUTE_PREFIX}/http-exception")

    assert response.status_code == 418
    assert response.json() == {"detail": "teapot detail"}


def test_structured_error_log_includes_required_fields(caplog):
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"{TEST_ROUTE_PREFIX}/http-exception",
            "headers": [(b"x-request-id", b"req-structured-log")],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )

    with caplog.at_level("WARNING", logger="tachiya.observability"):
        log_structured_error_event(request=request, status_code=418)

    matching_payload = None
    for record in caplog.records:
        payload = _record_payload(record)
        if {
            "event_name",
            "error_code",
            "request_id",
            "outcome",
            "severity",
            "status_code",
            "path",
            "method",
        }.issubset(payload):
            matching_payload = payload
            break

    assert matching_payload is not None
    assert matching_payload["request_id"] == "req-structured-log"
    assert matching_payload["status_code"] == 418
    assert matching_payload["path"] == f"{TEST_ROUTE_PREFIX}/http-exception"
    assert matching_payload["method"] == "GET"
