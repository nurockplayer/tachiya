import os
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from config import Settings


@dataclass(frozen=True)
class TachigoPoints:
    email: str
    spendable_balance: int
    cumulative_total: int


@dataclass(frozen=True)
class TachigoIdentityPoints:
    provider: str
    external_subject: str
    spendable_balance: int
    cumulative_total: int


class TachigoUpstreamError(RuntimeError):
    pass


async def get_user_points(
    email: str,
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> TachigoPoints:
    normalized_email = email.strip()
    if not normalized_email:
        raise TachigoUpstreamError("email is required")

    internal_headers = _internal_headers()
    close_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=5)

    try:
        response = await client.get(
            f"{settings.tachigo_api_url.rstrip('/')}/api/v1/internal/tachiya/users/points/balance",
            params={"email": normalized_email},
            headers=internal_headers,
        )
    except httpx.HTTPError as exc:
        raise TachigoUpstreamError("tachigo upstream request failed") from exc
    finally:
        if close_client:
            await client.aclose()

    if response.status_code != 200:
        raise TachigoUpstreamError(f"tachigo upstream returned {response.status_code}")

    payload = _json_payload(response)
    try:
        response_email = payload["email"]
        if not isinstance(response_email, str):
            raise TypeError("email must be a string")
        normalized_response_email = response_email.strip()
        if not normalized_response_email:
            raise ValueError("email is required")
        if normalized_response_email.lower() != normalized_email.lower():
            raise TachigoUpstreamError("tachigo upstream email mismatch")

        return TachigoPoints(
            email=normalized_response_email,
            spendable_balance=_required_int(payload["spendable_balance"]),
            cumulative_total=_required_int(payload["cumulative_total"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TachigoUpstreamError(
            "tachigo upstream returned invalid points payload"
        ) from exc


async def get_identity_points(
    provider: str,
    external_subject: str,
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> TachigoIdentityPoints:
    requested_provider = provider.strip().lower()
    if not requested_provider:
        raise TachigoUpstreamError("provider is required")
    requested_external_subject = external_subject.strip()
    if not requested_external_subject:
        raise TachigoUpstreamError("external_subject is required")

    internal_headers = _internal_headers()
    close_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=5)

    provider_path = quote(requested_provider, safe="")
    subject_path = quote(requested_external_subject, safe="")
    try:
        response = await client.get(
            f"{settings.tachigo_api_url.rstrip('/')}/internal/identity/"
            f"{provider_path}/{subject_path}/points",
            headers=internal_headers,
        )
    except httpx.HTTPError as exc:
        raise TachigoUpstreamError("tachigo upstream request failed") from exc
    finally:
        if close_client:
            await client.aclose()

    if response.status_code != 200:
        raise TachigoUpstreamError(f"tachigo upstream returned {response.status_code}")

    payload = _json_payload(response)
    try:
        response_provider = (
            str(payload.get("provider", requested_provider)).strip().lower()
        )
        response_external_subject = str(
            payload.get("external_subject", requested_external_subject),
        ).strip()
        if (
            response_provider != requested_provider
            or response_external_subject != requested_external_subject
        ):
            raise TachigoUpstreamError("tachigo upstream identity mismatch")

        return TachigoIdentityPoints(
            provider=response_provider,
            external_subject=response_external_subject,
            spendable_balance=_required_int(payload["spendable_balance"]),
            cumulative_total=_required_int(payload["cumulative_total"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TachigoUpstreamError(
            "tachigo upstream returned invalid points payload"
        ) from exc


def _internal_headers() -> dict[str, str]:
    secret = os.getenv("TACHIYA_INTERNAL_SHARED_SECRET", "").strip()
    if not secret:
        raise TachigoUpstreamError("tachigo internal secret is not configured")
    return {"X-Tachiya-Internal-Secret": secret}


def _json_payload(response: httpx.Response):
    try:
        return response.json()
    except ValueError as exc:
        raise TachigoUpstreamError(
            "tachigo upstream returned invalid points payload",
        ) from exc


def _required_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("value must be an integer")
    if value < 0:
        raise ValueError("value must be non-negative")
    return value
