import sys
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
