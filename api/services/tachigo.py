import os
from dataclasses import dataclass

import httpx

from config import Settings


@dataclass(frozen=True)
class TachigoPoints:
    email: str
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
    close_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=5)

    try:
        response = await client.get(
            f"{settings.tachigo_api_url.rstrip('/')}/internal/users/points",
            params={"email": email},
            headers=_internal_headers(),
        )
    except httpx.HTTPError as exc:
        raise TachigoUpstreamError("tachigo upstream request failed") from exc
    finally:
        if close_client:
            await client.aclose()

    if response.status_code != 200:
        raise TachigoUpstreamError(f"tachigo upstream returned {response.status_code}")

    payload = response.json()
    try:
        return TachigoPoints(
            email=str(payload["email"]),
            spendable_balance=int(payload["spendable_balance"]),
            cumulative_total=int(payload["cumulative_total"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TachigoUpstreamError("tachigo upstream returned invalid points payload") from exc


def _internal_headers() -> dict[str, str]:
    secret = os.getenv("TACHIYA_INTERNAL_SHARED_SECRET", "")
    if not secret:
        return {}
    return {"X-Tachiya-Internal-Secret": secret}
