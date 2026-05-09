import hashlib
import hmac
import sys
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import security
from security import verify_internal_secret, verify_webhook_signature


def build_client() -> TestClient:
    app = FastAPI()

    @app.get("/internal", dependencies=[Depends(verify_internal_secret)])
    def internal_route():
        return {"ok": True}

    @app.post("/webhook")
    async def webhook_route(_=Depends(verify_webhook_signature)):
        return {"ok": True}

    return TestClient(app)


def signed_webhook_headers(
    *,
    body: bytes,
    secret: str = "shared-secret",
    timestamp: int = 1_700_000_000,
) -> dict[str, str]:
    signed_payload = f"{timestamp}.".encode() + body
    signature = hmac.new(
        secret.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    return {
        "x-tachiya-webhook-event-id": "evt-test-1",
        "x-tachiya-webhook-timestamp": str(timestamp),
        "x-tachiya-webhook-signature": signature,
    }


def test_internal_secret_fails_closed_when_not_configured(monkeypatch):
    monkeypatch.delenv("TACHIYA_INTERNAL_SHARED_SECRET", raising=False)
    client = build_client()

    response = client.get("/internal")

    assert response.status_code == 500
    assert response.json()["detail"] == "internal shared secret is not configured"


def test_webhook_signature_fails_closed_when_secret_not_configured(monkeypatch):
    monkeypatch.delenv("TACHIYA_INTERNAL_SHARED_SECRET", raising=False)
    client = build_client()

    response = client.post("/webhook", json={"ok": True})

    assert response.status_code == 500
    assert response.json()["detail"] == "internal shared secret is not configured"


def test_internal_secret_still_rejects_missing_header_when_configured(monkeypatch):
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    client = build_client()

    response = client.get("/internal")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid internal secret"


def test_webhook_signature_uses_default_tolerance_when_not_configured(monkeypatch):
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    monkeypatch.delenv("TACHIYA_WEBHOOK_TOLERANCE_SECONDS", raising=False)
    monkeypatch.setattr(security.time, "time", lambda: 1_700_000_000)
    client = build_client()
    body = b'{"ok":true}'

    response = client.post(
        "/webhook",
        content=body,
        headers=signed_webhook_headers(body=body, timestamp=1_699_999_760),
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_webhook_signature_uses_configured_tolerance(monkeypatch):
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    monkeypatch.setenv("TACHIYA_WEBHOOK_TOLERANCE_SECONDS", "10")
    monkeypatch.setattr(security.time, "time", lambda: 1_700_000_000)
    client = build_client()
    body = b'{"ok":true}'

    response = client.post(
        "/webhook",
        content=body,
        headers=signed_webhook_headers(body=body, timestamp=1_699_999_989),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "stale webhook timestamp"


@pytest.mark.parametrize("raw_tolerance", ["abc", "0", "-1"])
def test_webhook_signature_fails_closed_when_tolerance_is_invalid(
    monkeypatch,
    raw_tolerance,
):
    monkeypatch.setenv("TACHIYA_INTERNAL_SHARED_SECRET", "shared-secret")
    monkeypatch.setenv("TACHIYA_WEBHOOK_TOLERANCE_SECONDS", raw_tolerance)
    monkeypatch.setattr(security.time, "time", lambda: 1_700_000_000)
    client = build_client()
    body = b'{"ok":true}'

    response = client.post(
        "/webhook",
        content=body,
        headers=signed_webhook_headers(body=body),
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "webhook tolerance is not configured correctly"
