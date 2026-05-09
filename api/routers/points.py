from datetime import datetime

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


class PointsLedgerEntryResponse(BaseModel):
    id: str
    amount: int
    entry_type: str
    source_type: str
    reference_id: str
    expires_at: datetime | None = None
    created_at: datetime


class PointsLedgerResponse(BaseModel):
    user_id: str
    entries: list[PointsLedgerEntryResponse]


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


@router.get(
    "/ledger",
    response_model=PointsLedgerResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def list_points_ledger(
    user_id: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    entries = await PointsService(db).list_entries(user_id, limit)
    return PointsLedgerResponse(
        user_id=user_id,
        entries=[
            PointsLedgerEntryResponse(
                id=entry.id,
                amount=entry.amount,
                entry_type=entry.entry_type,
                source_type=entry.source_type,
                reference_id=entry.reference_id,
                expires_at=entry.expires_at,
                created_at=entry.created_at,
            )
            for entry in entries
        ],
    )
