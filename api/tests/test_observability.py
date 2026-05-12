import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from observability import (
    REQUEST_ID_HEADER,
    get_or_create_request_id,
    log_structured_error_event,
)


TEST_ROUTE_PREFIX = "/__test_observability"


def _ensure_test_routes() -> None:
    existing_paths = {route.path for route in main.app.routes}
    http_exception_path = f"{TEST_ROUTE_PREFIX}/http-exception"
    non_http_exception_path = f"{TEST_ROUTE_PREFIX}/server-error"
    identity_points_path = (
        f"{TEST_ROUTE_PREFIX}/identity/{{provider}}/{{external_subject}}/points"
    )

    if http_exception_path not in existing_paths:

        @main.app.get(http_exception_path)
        def raise_http_exception() -> None:
            raise HTTPException(status_code=418, detail="teapot detail")

    if non_http_exception_path not in existing_paths:

        @main.app.get(non_http_exception_path)
        def raise_non_http_exception() -> None:
            raise RuntimeError("unexpected server error")

    if identity_points_path not in existing_paths:

        @main.app.get(identity_points_path)
        def raise_identity_points_http_exception(
            provider: str,
            external_subject: str,
        ) -> None:
            raise HTTPException(
                status_code=404,
                detail=f"{provider}:{external_subject} not found",
            )


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


def test_header_request_id_also_populates_request_state():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [(b"x-request-id", b"req-from-client")],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )

    request_id = get_or_create_request_id(request)

    assert request_id == "req-from-client"
    assert request.state.request_id == "req-from-client"


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


def test_unhandled_server_error_response_still_has_request_id_header():
    client = _build_app_client(raise_server_exceptions=False)

    response = client.get(f"{TEST_ROUTE_PREFIX}/server-error")

    assert response.status_code == 500
    assert response.headers["X-Request-ID"]


def test_allowed_cross_origin_server_error_exposes_request_id_header():
    client = _build_app_client(raise_server_exceptions=False)

    response = client.get(
        f"{TEST_ROUTE_PREFIX}/server-error",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER]
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert REQUEST_ID_HEADER in response.headers["access-control-expose-headers"]


def test_disallowed_cross_origin_server_error_does_not_allow_origin():
    client = _build_app_client(raise_server_exceptions=False)

    response = client.get(
        f"{TEST_ROUTE_PREFIX}/server-error",
        headers={"Origin": "https://evil.example.com"},
    )

    assert response.status_code == 500
    assert "access-control-allow-origin" not in response.headers


def test_unhandled_server_error_logs_exception_context(caplog):
    client = _build_app_client(raise_server_exceptions=False)

    with caplog.at_level("ERROR", logger="tachiya.observability"):
        response = client.get(f"{TEST_ROUTE_PREFIX}/server-error")

    assert response.status_code == 500

    matching_record = None
    for record in caplog.records:
        if "Unhandled exception" in record.getMessage():
            matching_record = record
            break

    assert matching_record is not None
    assert matching_record.exc_info is not None


def test_structured_error_log_includes_required_fields(caplog):
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"{TEST_ROUTE_PREFIX}/http-exception",
            "route": SimpleNamespace(path=f"{TEST_ROUTE_PREFIX}/http-exception"),
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


def test_structured_error_log_uses_route_template_without_raw_path_values(caplog):
    client = _build_app_client()
    raw_subject = "discord-user-raw-secret"
    request_path = f"{TEST_ROUTE_PREFIX}/identity/discord/{raw_subject}/points"

    with caplog.at_level("WARNING", logger="tachiya.observability"):
        response = client.get(
            request_path,
            headers={"X-Request-ID": "req-redacted-path"},
        )

    assert response.status_code == 404

    matching_payload = None
    for record in caplog.records:
        payload = _record_payload(record)
        if payload.get("request_id") == "req-redacted-path":
            matching_payload = payload
            break

    assert matching_payload is not None
    assert (
        matching_payload["path"]
        == f"{TEST_ROUTE_PREFIX}/identity/{{provider}}/{{external_subject}}/points"
    )
    assert raw_subject not in matching_payload["path"]
    assert raw_subject not in json.dumps(matching_payload, ensure_ascii=True)


def test_unmatched_404_structured_log_redacts_raw_path(caplog):
    client = _build_app_client()
    raw_secret = "discord-user-raw-secret"
    request_path = f"/not-found/{raw_secret}/token"

    with caplog.at_level("WARNING", logger="tachiya.observability"):
        response = client.get(
            request_path,
            headers={"X-Request-ID": "req-unmatched-404"},
        )

    assert response.status_code == 404

    matching_payload = None
    for record in caplog.records:
        payload = _record_payload(record)
        if payload.get("request_id") == "req-unmatched-404":
            matching_payload = payload
            break

    assert matching_payload is not None
    assert matching_payload["path"] == "<unmatched>"
    assert raw_secret not in json.dumps(matching_payload, ensure_ascii=True)
