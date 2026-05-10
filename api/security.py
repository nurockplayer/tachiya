import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Header, HTTPException, Request


@dataclass(frozen=True)
class VerifiedWebhookRequest:
    event_id: str
    occurred_at: datetime


def verify_internal_secret(
    x_tachiya_internal_secret: str | None = Header(default=None),
):
    expected = _get_required_internal_secret()
    if not x_tachiya_internal_secret or not hmac.compare_digest(
        x_tachiya_internal_secret,
        expected,
    ):
        raise HTTPException(status_code=401, detail="invalid internal secret")


async def verify_webhook_signature(
    request: Request,
    x_tachiya_webhook_event_id: str | None = Header(default=None),
    x_tachiya_webhook_timestamp: str | None = Header(default=None),
    x_tachiya_webhook_signature: str | None = Header(default=None),
) -> VerifiedWebhookRequest | None:
    secret = _get_required_internal_secret()

    if (
        not x_tachiya_webhook_event_id
        or not x_tachiya_webhook_timestamp
        or not x_tachiya_webhook_signature
    ):
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    if not x_tachiya_webhook_event_id.strip():
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    try:
        timestamp = int(x_tachiya_webhook_timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid webhook signature") from exc

    tolerance_seconds = _get_webhook_tolerance_seconds()
    if abs(int(time.time()) - timestamp) > tolerance_seconds:
        raise HTTPException(status_code=401, detail="stale webhook timestamp")

    body = await request.body()
    signed_payload = f"{timestamp}.{x_tachiya_webhook_event_id}.".encode() + body
    expected_signature = hmac.new(
        secret.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(x_tachiya_webhook_signature, expected_signature):
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    return VerifiedWebhookRequest(
        event_id=x_tachiya_webhook_event_id,
        occurred_at=datetime.fromtimestamp(timestamp, UTC).replace(tzinfo=None),
    )


def _get_required_internal_secret() -> str:
    secret = os.getenv("TACHIYA_INTERNAL_SHARED_SECRET", "")
    if not secret:
        raise HTTPException(
            status_code=500,
            detail="internal shared secret is not configured",
        )
    return secret


def _get_webhook_tolerance_seconds() -> int:
    raw_tolerance = os.getenv("TACHIYA_WEBHOOK_TOLERANCE_SECONDS", "300")
    try:
        tolerance_seconds = int(raw_tolerance)
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail="webhook tolerance is not configured correctly",
        ) from exc

    if tolerance_seconds <= 0:
        raise HTTPException(
            status_code=500,
            detail="webhook tolerance is not configured correctly",
        )

    return tolerance_seconds
