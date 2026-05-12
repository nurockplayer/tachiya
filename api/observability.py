import json
import logging
from uuid import uuid4

from fastapi import Request

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_STATE_KEY = "request_id"
SERVICE_NAME = "tachiya-api"

logger = logging.getLogger("tachiya.observability")

_DOMAIN_BY_PREFIX = {
    "coupons": "coupons",
    "health": "platform",
    "identity-mappings": "identity_mapping",
    "points": "points",
    "ready": "platform",
    "referrals": "referrals",
    "streamers": "streamers",
    "tachigo": "tachigo",
    "webhooks": "webhook",
}

_OUTCOME_BY_STATUS_CODE = {
    400: "rejected",
    401: "rejected",
    403: "rejected",
    404: "failed",
    409: "conflict",
    422: "rejected",
}

_LOG_LEVEL_BY_SEVERITY = {
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def get_or_create_request_id(request: Request) -> str:
    request_id = request.headers.get(REQUEST_ID_HEADER) or getattr(
        request.state,
        REQUEST_ID_STATE_KEY,
        None,
    )
    if not request_id:
        request_id = str(uuid4())

    setattr(request.state, REQUEST_ID_STATE_KEY, request_id)
    return request_id


async def request_id_middleware(request: Request, call_next):
    request_id = get_or_create_request_id(request)
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


def build_structured_error_event(
    *,
    request: Request,
    status_code: int,
) -> dict[str, str | int]:
    domain = infer_domain_from_path(request.url.path)
    severity = infer_severity(status_code)
    return {
        "service": SERVICE_NAME,
        "event_name": f"{domain}.http_exception",
        "domain": domain,
        "outcome": infer_outcome(status_code),
        "severity": severity,
        "error_code": f"{domain}.http_{status_code}",
        "request_id": get_or_create_request_id(request),
        "status_code": status_code,
        "path": request.url.path,
        "method": request.method,
    }


def log_structured_error_event(*, request: Request, status_code: int) -> None:
    event = build_structured_error_event(request=request, status_code=status_code)
    logger.log(
        _LOG_LEVEL_BY_SEVERITY[event["severity"]],
        "structured_error_event %s",
        json.dumps(event, ensure_ascii=True, sort_keys=True),
        extra={"structured_event": event},
    )


def infer_domain_from_path(path: str) -> str:
    normalized_path = path.strip("/")
    if not normalized_path:
        return "platform"

    prefix = normalized_path.split("/", 1)[0]
    return _DOMAIN_BY_PREFIX.get(prefix, "platform")


def infer_outcome(status_code: int) -> str:
    return _OUTCOME_BY_STATUS_CODE.get(
        status_code,
        "failed" if status_code >= 500 else "rejected",
    )


def infer_severity(status_code: int) -> str:
    return "error" if status_code >= 500 else "warning"
