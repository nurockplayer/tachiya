from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from security import verify_internal_secret
from services.points_service import PointsService

router = APIRouter(prefix="/points", tags=["points"])


class PointsBalanceResponse(BaseModel):
    user_id: str
    balance: int


@router.get(
    "/balance",
    response_model=PointsBalanceResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def get_points_balance(
    user_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    balance = await PointsService(db).get_balance(user_id)
    return PointsBalanceResponse(user_id=user_id, balance=balance)
