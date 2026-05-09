import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from _saleor_common import execute_graphql, get_admin_token  # noqa: E402

SALEOR_URL = os.getenv("SALEOR_GRAPHQL_URL", os.getenv("SALEOR_URL", "http://localhost:8000/graphql/"))
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
    cfg = COUPON_CONFIG[coupon_id]
    session, token = _get_session_and_token()

    # Step 1: create voucher (no discountValue in this Saleor version)
    payload = execute_graphql(
        session,
        VOUCHER_CREATE,
        {
            "input": {
                "name": code,
                "code": code,
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
    voucher_id = result["voucher"]["id"]
    voucher_code = result["voucher"]["code"]

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

    return {"voucher_id": voucher_id, "code": voucher_code}
