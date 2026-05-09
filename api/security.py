import hmac
import os

from fastapi import Header, HTTPException


def verify_internal_secret(
    x_tachiya_internal_secret: str | None = Header(default=None),
):
    expected = os.getenv("TACHIYA_INTERNAL_SHARED_SECRET", "")
    if not expected:
        return
    if not x_tachiya_internal_secret or not hmac.compare_digest(
        x_tachiya_internal_secret,
        expected,
    ):
        raise HTTPException(status_code=401, detail="invalid internal secret")
