from fastapi import Depends, FastAPI, Query

from config import get_settings
from redemptions import (
    RedemptionRequest,
    RedemptionResponse,
    SqliteRedemptionStore,
    issue_redemption,
    verify_internal_secret,
)
from tachigo import get_user_points

app = FastAPI(title="Tachiya API")
settings = get_settings()
store = SqliteRedemptionStore(settings.tachiya_redemptions_db_path)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/internal/redemptions",
    response_model=RedemptionResponse,
    dependencies=[Depends(verify_internal_secret)],
    tags=["internal"],
)
def create_redemption(payload: RedemptionRequest) -> RedemptionResponse:
    return issue_redemption(payload, store=store, settings=settings)


@app.get(
    "/tachigo/users/points",
    dependencies=[Depends(verify_internal_secret)],
    tags=["tachigo"],
)
async def query_user_points(email: str = Query(..., description="tachigo user email")):
    return await get_user_points(email, settings)
