import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.coupon import UserCoupon
from api.services.saleor_voucher import COUPON_CONFIG, create_voucher

router = APIRouter(prefix="/coupons", tags=["coupons"])

VALID_COUPON_IDS = list(COUPON_CONFIG.keys())


class RedeemRequest(BaseModel):
    coupon_id: str
    tcg_cost: int


class RedeemResponse(BaseModel):
    voucher_code: str
    status: str = "ok"


@router.post("/redeem", response_model=RedeemResponse)
def redeem_coupon(req: RedeemRequest, db: Session = Depends(get_db)):
    if req.coupon_id not in VALID_COUPON_IDS:
        raise HTTPException(status_code=400, detail=f"unknown coupon_id: {req.coupon_id}")

    code = f"DEMO-{uuid.uuid4().hex[:6].upper()}"
    try:
        result = create_voucher(req.coupon_id, code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    coupon_type = COUPON_CONFIG[req.coupon_id]["coupon_type"]
    record = UserCoupon(
        coupon_id=req.coupon_id,
        voucher_code=result["code"],
        saleor_voucher_id=result["voucher_id"],
        coupon_type=coupon_type,
        tcg_cost=req.tcg_cost,
    )
    db.add(record)
    db.commit()

    return RedeemResponse(voucher_code=result["code"])


@router.get("/")
def list_coupons(db: Session = Depends(get_db)):
    coupons = (
        db.query(UserCoupon)
        .filter(UserCoupon.status == "active")
        .order_by(UserCoupon.created_at.desc())
        .all()
    )
    return [
        {
            "voucher_code": c.voucher_code,
            "coupon_type": c.coupon_type,
            "tcg_cost": c.tcg_cost,
            "status": c.status,
        }
        for c in coupons
    ]
