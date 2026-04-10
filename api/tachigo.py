from fastapi import HTTPException, status
import httpx

from config import Settings


async def get_user_points(email: str, settings: Settings) -> dict:
    url = f"{settings.tachigo_api_url}/api/v1/internal/tachiya/users/points/balance"
    headers = {"X-Tachiya-Internal-Secret": settings.tachiya_internal_shared_secret or ""}

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url, params={"email": email}, headers=headers)

    if resp.status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found in tachigo")
    if resp.status_code == 401:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="tachigo auth failed")
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="tachigo error")

    data = resp.json()
    return {
        "email": email,
        "spendable_balance": data["spendable_balance"],
        "cumulative_total": data["cumulative_total"],
    }
