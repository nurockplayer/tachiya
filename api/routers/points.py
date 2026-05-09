from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
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


class PointsTransactionRequest(BaseModel):
    user_id: str
    entry_type: Literal["credit", "debit"]
    amount: int
    reference_id: str
    source_type: str = "manual"
    expires_at: datetime | None = None


class PointsTransactionResponse(BaseModel):
    entry: PointsLedgerEntryResponse
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


@router.post(
    "/transactions",
    response_model=PointsTransactionResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def create_points_transaction(
    req: PointsTransactionRequest,
    db: Session = Depends(get_db),
):
    service = PointsService(db)
    try:
        if req.entry_type == "credit":
            entry = await service.credit(
                user_id=req.user_id,
                amount=req.amount,
                reference_id=req.reference_id,
                source_type=req.source_type,
                expires_at=req.expires_at,
            )
        else:
            entry = await service.debit(
                user_id=req.user_id,
                amount=req.amount,
                reference_id=req.reference_id,
                source_type=req.source_type,
                expires_at=req.expires_at,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    balance = await service.get_balance(req.user_id)
    return PointsTransactionResponse(
        entry=_ledger_entry_response(entry),
        balance=balance,
    )


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
        entries=[_ledger_entry_response(entry) for entry in entries],
    )


def _ledger_entry_response(entry) -> PointsLedgerEntryResponse:
    return PointsLedgerEntryResponse(
        id=entry.id,
        amount=entry.amount,
        entry_type=entry.entry_type,
        source_type=entry.source_type,
        reference_id=entry.reference_id,
        expires_at=entry.expires_at,
        created_at=entry.created_at,
    )
