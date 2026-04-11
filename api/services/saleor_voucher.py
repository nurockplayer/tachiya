import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from _saleor_common import execute_graphql, get_admin_token  # noqa: E402

SALEOR_URL = os.getenv("SALEOR_URL", "http://localhost:8000/graphql/")
ADMIN_EMAIL = os.getenv("SALEOR_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("SALEOR_ADMIN_PASSWORD", "admin")

COUPON_CONFIG = {
    "tachiya-95": {
        "coupon_type": "PERCENT_5",
        "type": "ENTIRE_ORDER",
        "value_type": "PERCENTAGE",
        "value": 5,
    },
    "free-ship": {
        "coupon_type": "FREE_SHIPPING",
        "type": "SHIPPING",
        "value_type": "PERCENTAGE",
        "value": 100,
    },
    "bundle-120": {
        "coupon_type": "CREATOR_120",
        "type": "ENTIRE_ORDER",
        "value_type": "FIXED",
        "value": 120,
    },
}

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


def create_voucher(coupon_id: str, code: str) -> dict:
    cfg = COUPON_CONFIG[coupon_id]
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # Override endpoint for this session
    import _saleor_common as sc

    original = sc.ENDPOINT
    sc.ENDPOINT = SALEOR_URL

    try:
        token = get_admin_token(session)
        payload = execute_graphql(
            session,
            VOUCHER_CREATE,
            {
                "input": {
                    "name": code,
                    "code": code,
                    "type": cfg["type"],
                    "discountValueType": cfg["value_type"],
                    "discountValue": cfg["value"],
                    "usageLimit": 1,
                }
            },
            token,
        )
    finally:
        sc.ENDPOINT = original

    result = payload["data"]["voucherCreate"]
    errors = result.get("errors") or []
    if errors:
        raise RuntimeError(f"voucherCreate errors: {errors}")

    voucher = result["voucher"]
    return {"voucher_id": voucher["id"], "code": voucher["code"]}
