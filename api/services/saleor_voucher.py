import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from _saleor_common import execute_graphql, get_admin_token  # noqa: E402

SALEOR_URL = os.getenv(
    "SALEOR_GRAPHQL_URL", os.getenv("SALEOR_URL", "http://localhost:8000/graphql/")
)
ADMIN_EMAIL = os.getenv("SALEOR_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("SALEOR_ADMIN_PASSWORD", "admin")

COUPON_CONFIG = {
    "tachiya-95": {
        "coupon_type": "PERCENT_5",
        "tcg_cost": 18,
        "type": "ENTIRE_ORDER",
        "value_type": "PERCENTAGE",
        "value": 5,
    },
    "free-ship": {
        "coupon_type": "FREE_SHIPPING",
        "tcg_cost": 30,
        "type": "SHIPPING",
        "value_type": "PERCENTAGE",
        "value": 100,
    },
    "bundle-120": {
        "coupon_type": "CREATOR_120",
        "tcg_cost": 120,
        "type": "ENTIRE_ORDER",
        "value_type": "FIXED",
        "value": 120,
    },
}

SALEOR_CHANNEL_ID = os.getenv("SALEOR_CHANNEL_ID", "Q2hhbm5lbDox")  # Default Channel

VOUCHER_CREATE = """
mutation VoucherCreate($input: VoucherInput!) {
  voucherCreate(input: $input) {
    voucher {
      id
      code
    }
    errors {
      field
      message
      code
    }
  }
}
"""

VOUCHER_CHANNEL_LISTING_UPDATE = """
mutation VoucherChannelListingUpdate($id: ID!, $input: VoucherChannelListingInput!) {
  voucherChannelListingUpdate(id: $id, input: $input) {
    voucher {
      id
      code
    }
    errors {
      field
      message
      code
    }
  }
}
"""


def _get_session_and_token():
    import _saleor_common as sc

    sc.ENDPOINT = SALEOR_URL
    sc.ADMIN_EMAIL = ADMIN_EMAIL
    sc.ADMIN_PASSWORD = ADMIN_PASSWORD
    session = requests.Session()
    token = get_admin_token(session)
    return session, token


def create_voucher(coupon_id: str, code: str) -> dict:
    normalized_coupon_id = _normalize_coupon_id(coupon_id)
    normalized_code = _normalize_required(code, "voucher code is required")
    cfg = COUPON_CONFIG[normalized_coupon_id]
    session, token = _get_session_and_token()

    # Step 1: create voucher (no discountValue in this Saleor version)
    payload = execute_graphql(
        session,
        VOUCHER_CREATE,
        {
            "input": {
                "name": normalized_code,
                "code": normalized_code,
                "type": cfg["type"],
                "discountValueType": cfg["value_type"],
                "singleUse": True,
            }
        },
        token,
    )
    result = payload["data"]["voucherCreate"]
    errors = result.get("errors") or []
    if errors:
        raise RuntimeError(f"voucherCreate errors: {errors}")
    voucher_id, voucher_code = _require_voucher(result, "voucherCreate missing voucher")

    # Step 2: set discount value via channel listing
    payload2 = execute_graphql(
        session,
        VOUCHER_CHANNEL_LISTING_UPDATE,
        {
            "id": voucher_id,
            "input": {
                "addChannels": [
                    {
                        "channelId": SALEOR_CHANNEL_ID,
                        "discountValue": cfg["value"],
                        "minAmountSpent": 0,
                    }
                ]
            },
        },
        token,
    )
    result2 = payload2["data"]["voucherChannelListingUpdate"]
    errors2 = result2.get("errors") or []
    if errors2:
        raise RuntimeError(f"voucherChannelListingUpdate errors: {errors2}")
    _require_voucher(result2, "voucherChannelListingUpdate missing voucher")

    return {"voucher_id": voucher_id, "code": voucher_code}


def _normalize_coupon_id(coupon_id: str) -> str:
    normalized = _normalize_required(coupon_id, "coupon_id is required")
    if normalized not in COUPON_CONFIG:
        raise ValueError(f"unknown coupon_id: {normalized}")
    return normalized


def _normalize_required(value: str, message: str) -> str:
    if not isinstance(value, str):
        raise ValueError(message)
    normalized = value.strip()
    if not normalized:
        raise ValueError(message)
    return normalized


def _require_voucher(result: dict, message: str) -> tuple[str, str]:
    voucher = result.get("voucher")
    if not isinstance(voucher, dict):
        raise RuntimeError(message)
    voucher_id = voucher.get("id")
    voucher_code = voucher.get("code")
    if not isinstance(voucher_id, str) or not voucher_id:
        raise RuntimeError(message)
    if not isinstance(voucher_code, str) or not voucher_code:
        raise RuntimeError(message)
    return voucher_id, voucher_code
