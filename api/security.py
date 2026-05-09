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
    expected = os.getenv("TACHIYA_INTERNAL_SHARED_SECRET", "")
    if not expected:
        return
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
    secret = os.getenv("TACHIYA_INTERNAL_SHARED_SECRET", "")
    if not secret:
        return None

    if (
        not x_tachiya_webhook_event_id
        or not x_tachiya_webhook_timestamp
        or not x_tachiya_webhook_signature
    ):
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    try:
        timestamp = int(x_tachiya_webhook_timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid webhook signature") from exc

    tolerance_seconds = int(os.getenv("TACHIYA_WEBHOOK_TOLERANCE_SECONDS", "300"))
    if abs(int(time.time()) - timestamp) > tolerance_seconds:
        raise HTTPException(status_code=401, detail="stale webhook timestamp")

    body = await request.body()
    signed_payload = f"{timestamp}.".encode() + body
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
