import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.coupon import UserCoupon
from models.coupon_redemption_audit import CouponRedemptionAuditEvent
from security import verify_internal_secret
from services.saleor_voucher import COUPON_CONFIG, create_voucher

router = APIRouter(prefix="/coupons", tags=["coupons"])

VALID_COUPON_IDS = list(COUPON_CONFIG.keys())


class RedeemRequest(BaseModel):
    coupon_id: str
    tcg_cost: int
    idempotency_key: str | None = None


class RedeemResponse(BaseModel):
    voucher_code: str
    redemption_token: str
    status: str = "ok"


class RedemptionAuditEventResponse(BaseModel):
    coupon_id: str
    idempotency_key: str | None = None
    redemption_token: str | None = None
    status: str
    reason: str | None = None
    created_at: datetime


class RedemptionAuditEventsResponse(BaseModel):
    events: list[RedemptionAuditEventResponse]


@router.post(
    "/redeem",
    response_model=RedeemResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def redeem_coupon(req: RedeemRequest, db: Session = Depends(get_db)):
    if req.coupon_id not in VALID_COUPON_IDS:
        _record_redemption_audit(
            db,
            coupon_id=req.coupon_id,
            idempotency_key=req.idempotency_key,
            redemption_token=None,
            status="failed",
            reason=f"unknown coupon_id: {req.coupon_id}",
        )
        raise HTTPException(status_code=400, detail=f"unknown coupon_id: {req.coupon_id}")

    if req.idempotency_key:
        existing = (
            db.query(UserCoupon)
            .filter(UserCoupon.idempotency_key == req.idempotency_key)
            .first()
        )
        if existing:
            _record_redemption_audit(
                db,
                coupon_id=existing.coupon_id,
                idempotency_key=req.idempotency_key,
                redemption_token=existing.redemption_token,
                status="replayed",
                reason="idempotency key replay",
            )
            return RedeemResponse(
                voucher_code=existing.voucher_code,
                redemption_token=existing.redemption_token,
            )

    code = f"DEMO-{uuid.uuid4().hex[:6].upper()}"
    redemption_token = str(uuid.uuid4())
    try:
        result = create_voucher(req.coupon_id, code)
    except Exception as e:
        _record_redemption_audit(
            db,
            coupon_id=req.coupon_id,
            idempotency_key=req.idempotency_key,
            redemption_token=None,
            status="failed",
            reason=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))

    coupon_type = COUPON_CONFIG[req.coupon_id]["coupon_type"]
    record = UserCoupon(
        coupon_id=req.coupon_id,
        voucher_code=result["code"],
        saleor_voucher_id=result["voucher_id"],
        idempotency_key=req.idempotency_key,
        redemption_token=redemption_token,
        coupon_type=coupon_type,
        tcg_cost=req.tcg_cost,
    )
    db.add(record)
    db.add(
        CouponRedemptionAuditEvent(
            coupon_id=req.coupon_id,
            idempotency_key=req.idempotency_key,
            redemption_token=redemption_token,
            status="succeeded",
            reason=None,
        ),
    )
    db.commit()

    return RedeemResponse(voucher_code=result["code"], redemption_token=redemption_token)


@router.get(
    "/redemption-audit-events",
    response_model=RedemptionAuditEventsResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def list_redemption_audit_events(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    events = (
        db.query(CouponRedemptionAuditEvent)
        .order_by(
            CouponRedemptionAuditEvent.created_at.desc(),
            CouponRedemptionAuditEvent.id.desc(),
        )
        .limit(limit)
        .all()
    )
    return RedemptionAuditEventsResponse(
        events=[
            RedemptionAuditEventResponse(
                coupon_id=event.coupon_id,
                idempotency_key=event.idempotency_key,
                redemption_token=event.redemption_token,
                status=event.status,
                reason=event.reason,
                created_at=event.created_at,
            )
            for event in events
        ],
    )


@router.get("")
@router.get("/")
def list_coupons(
    redemption_token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if redemption_token:
        coupon = (
            db.query(UserCoupon)
            .filter(
                UserCoupon.redemption_token == redemption_token,
                UserCoupon.status == "active",
            )
            .first()
        )
        return [] if coupon is None else [_coupon_response(coupon)]

    coupons = (
        db.query(UserCoupon)
        .filter(UserCoupon.status == "active")
        .order_by(UserCoupon.created_at.desc())
        .all()
    )
    return [_coupon_response(c) for c in coupons]


def _coupon_response(coupon: UserCoupon) -> dict:
    return {
        "voucher_code": coupon.voucher_code,
        "coupon_type": coupon.coupon_type,
        "tcg_cost": coupon.tcg_cost,
        "status": coupon.status,
    }


def _record_redemption_audit(
    db: Session,
    *,
    coupon_id: str,
    idempotency_key: str | None,
    redemption_token: str | None,
    status: str,
    reason: str | None,
) -> None:
    db.add(
        CouponRedemptionAuditEvent(
            coupon_id=coupon_id,
            idempotency_key=idempotency_key,
            redemption_token=redemption_token,
            status=status,
            reason=reason,
        ),
    )
    db.commit()
