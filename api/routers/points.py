from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt, StringConstraints
from sqlalchemy.orm import Session

from database import get_db
from security import (
    VerifiedWebhookRequest,
    verify_internal_secret,
    verify_webhook_signature,
)
from services.points_service import PointsService
from services.webhook_event_service import WebhookEventReplayError, WebhookEventService

router = APIRouter(prefix="/points", tags=["points"])

NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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


class PointsLedgerAdminEntryResponse(PointsLedgerEntryResponse):
    user_id: str


class PointsLedgerAdminEntriesResponse(BaseModel):
    entries: list[PointsLedgerAdminEntryResponse]


class PointsExpiredCreditEntryResponse(BaseModel):
    id: str
    user_id: str
    amount: int
    remaining_amount: int
    source_type: str
    reference_id: str
    expires_at: datetime
    created_at: datetime


class PointsExpiredCreditsResponse(BaseModel):
    entries: list[PointsExpiredCreditEntryResponse]


class PointsTransactionRequest(BaseModel):
    user_id: NonBlankStr
    entry_type: Literal["credit", "debit"]
    amount: StrictInt = Field(gt=0)
    reference_id: NonBlankStr
    source_type: NonBlankStr = "manual"
    expires_at: datetime | None = None


class PointsTransactionResponse(BaseModel):
    entry: PointsLedgerEntryResponse
    balance: int


class OrderRewardRequest(BaseModel):
    order_id: NonBlankStr
    user_id: NonBlankStr
    reward_points: StrictInt = Field(gt=0)


class OrderRewardResponse(BaseModel):
    rewarded: bool
    reward_points: int | None = None
    ledger_entry_id: str | None = None


@router.get(
    "/balance",
    response_model=PointsBalanceResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def get_points_balance(
    user_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    normalized_user_id = _normalize_required_query(user_id, "user_id is required")
    balance = await PointsService(db).get_balance(normalized_user_id)
    return PointsBalanceResponse(user_id=normalized_user_id, balance=balance)


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

    balance = await service.get_balance(entry.user_id)
    return PointsTransactionResponse(
        entry=_ledger_entry_response(entry),
        balance=balance,
    )


@router.post(
    "/webhooks/order-rewarded",
    response_model=OrderRewardResponse,
    dependencies=[Depends(verify_internal_secret)],
)
async def order_rewarded_webhook(
    req: OrderRewardRequest,
    webhook: VerifiedWebhookRequest | None = Depends(verify_webhook_signature),
    db: Session = Depends(get_db),
):
    _reject_replayed_webhook_event(db, webhook)
    normalized_order_id = _normalize_required_query(
        req.order_id, "order_id is required"
    )
    service = PointsService(db)
    try:
        entry = await service.credit(
            user_id=req.user_id,
            amount=req.reward_points,
            reference_id=f"order-reward:{normalized_order_id}",
            source_type="order-reward",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _record_webhook_event(db, webhook, event_type="points.order_rewarded")
    return OrderRewardResponse(
        rewarded=True,
        reward_points=req.reward_points,
        ledger_entry_id=entry.id,
    )


@router.get(
    "/ledger/entries",
    response_model=PointsLedgerAdminEntriesResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def list_points_ledger_entries_for_admin(
    user_id: str | None = Query(default=None),
    entry_type: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    reference_id: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        entries = PointsService(db).list_admin_entries(
            user_id=user_id,
            entry_type=entry_type,
            source_type=source_type,
            reference_id=reference_id,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return PointsLedgerAdminEntriesResponse(
        entries=[_ledger_admin_entry_response(entry) for entry in entries],
    )


@router.get(
    "/ledger/expired-credits",
    response_model=PointsExpiredCreditsResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def list_points_expired_credit_exposures_for_admin(
    user_id: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        exposures = PointsService(db).list_expired_credit_exposures(
            user_id=user_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return PointsExpiredCreditsResponse(
        entries=[
            PointsExpiredCreditEntryResponse(
                id=exposure.entry.id,
                user_id=exposure.entry.user_id,
                amount=exposure.entry.amount,
                remaining_amount=exposure.remaining_amount,
                source_type=exposure.entry.source_type,
                reference_id=exposure.entry.reference_id,
                expires_at=exposure.entry.expires_at,
                created_at=exposure.entry.created_at,
            )
            for exposure in exposures
        ],
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
    normalized_user_id = _normalize_required_query(user_id, "user_id is required")
    entries = await PointsService(db).list_entries(normalized_user_id, limit)
    return PointsLedgerResponse(
        user_id=normalized_user_id,
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


def _ledger_admin_entry_response(entry) -> PointsLedgerAdminEntryResponse:
    return PointsLedgerAdminEntryResponse(
        id=entry.id,
        user_id=entry.user_id,
        amount=entry.amount,
        entry_type=entry.entry_type,
        source_type=entry.source_type,
        reference_id=entry.reference_id,
        expires_at=entry.expires_at,
        created_at=entry.created_at,
    )


def _normalize_required_query(value: str, message: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail=message)
    return normalized


def _reject_replayed_webhook_event(
    db: Session,
    webhook: VerifiedWebhookRequest | None,
) -> None:
    try:
        WebhookEventService(db).reject_replayed_event(webhook)
    except WebhookEventReplayError as exc:
        raise HTTPException(
            status_code=409, detail="webhook event already processed"
        ) from exc


def _record_webhook_event(
    db: Session,
    webhook: VerifiedWebhookRequest | None,
    *,
    event_type: str,
) -> None:
    try:
        WebhookEventService(db).record_event(webhook, event_type=event_type)
    except WebhookEventReplayError as exc:
        raise HTTPException(
            status_code=409,
            detail="webhook event already processed",
        ) from exc
