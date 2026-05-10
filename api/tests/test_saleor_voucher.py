import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import saleor_voucher


def fail_session_and_token():
    raise AssertionError("Saleor session should not be created")


@pytest.mark.parametrize(
    ("coupon_id", "message"),
    [
        (" ", "coupon_id is required"),
        (None, "coupon_id is required"),
        ("missing-coupon", "unknown coupon_id: missing-coupon"),
    ],
)
def test_create_voucher_rejects_invalid_coupon_id_before_saleor_call(
    monkeypatch, coupon_id, message
):
    monkeypatch.setattr(
        saleor_voucher, "_get_session_and_token", fail_session_and_token
    )

    with pytest.raises(ValueError, match=message):
        saleor_voucher.create_voucher(coupon_id, "TACHIYA-ABC123")


@pytest.mark.parametrize("code", [" ", None])
def test_create_voucher_rejects_blank_code_before_saleor_call(monkeypatch, code):
    monkeypatch.setattr(
        saleor_voucher, "_get_session_and_token", fail_session_and_token
    )

    with pytest.raises(ValueError, match="voucher code is required"):
        saleor_voucher.create_voucher("tachiya-95", code)


def test_create_voucher_normalizes_inputs(monkeypatch):
    calls = []

    def fake_session_and_token():
        return object(), "admin-token"

    def fake_execute_graphql(session, mutation, variables, token):
        calls.append(variables)
        if "voucherCreate" in mutation:
            return {
                "data": {
                    "voucherCreate": {
                        "voucher": {"id": "voucher-1", "code": "TACHIYA-ABC123"},
                        "errors": [],
                    },
                },
            }
        return {
            "data": {
                "voucherChannelListingUpdate": {
                    "voucher": {"id": "voucher-1", "code": "TACHIYA-ABC123"},
                    "errors": [],
                },
            },
        }

    monkeypatch.setattr(
        saleor_voucher, "_get_session_and_token", fake_session_and_token
    )
    monkeypatch.setattr(saleor_voucher, "execute_graphql", fake_execute_graphql)

    result = saleor_voucher.create_voucher(" tachiya-95 ", " TACHIYA-ABC123 ")

    assert result == {"voucher_id": "voucher-1", "code": "TACHIYA-ABC123"}
    assert calls[0]["input"]["code"] == "TACHIYA-ABC123"
    assert calls[0]["input"]["name"] == "TACHIYA-ABC123"


@pytest.mark.parametrize(
    "voucher_payload",
    [
        None,
        {},
        {"id": "voucher-1"},
        {"code": "TACHIYA-ABC123"},
    ],
)
def test_create_voucher_rejects_malformed_create_response(monkeypatch, voucher_payload):
    def fake_session_and_token():
        return object(), "admin-token"

    def fake_execute_graphql(session, mutation, variables, token):
        return {
            "data": {
                "voucherCreate": {
                    "voucher": voucher_payload,
                    "errors": [],
                },
            },
        }

    monkeypatch.setattr(
        saleor_voucher, "_get_session_and_token", fake_session_and_token
    )
    monkeypatch.setattr(saleor_voucher, "execute_graphql", fake_execute_graphql)

    with pytest.raises(RuntimeError, match="voucherCreate missing voucher"):
        saleor_voucher.create_voucher("tachiya-95", "TACHIYA-ABC123")


@pytest.mark.parametrize(
    "voucher_payload",
    [
        None,
        {},
        {"id": "voucher-1"},
        {"code": "TACHIYA-ABC123"},
    ],
)
def test_create_voucher_rejects_malformed_channel_listing_response(
    monkeypatch,
    voucher_payload,
):
    calls = []

    def fake_session_and_token():
        return object(), "admin-token"

    def fake_execute_graphql(session, mutation, variables, token):
        calls.append(mutation)
        if "voucherCreate" in mutation:
            return {
                "data": {
                    "voucherCreate": {
                        "voucher": {"id": "voucher-1", "code": "TACHIYA-ABC123"},
                        "errors": [],
                    },
                },
            }
        return {
            "data": {
                "voucherChannelListingUpdate": {
                    "voucher": voucher_payload,
                    "errors": [],
                },
            },
        }

    monkeypatch.setattr(
        saleor_voucher, "_get_session_and_token", fake_session_and_token
    )
    monkeypatch.setattr(saleor_voucher, "execute_graphql", fake_execute_graphql)

    with pytest.raises(
        RuntimeError, match="voucherChannelListingUpdate missing voucher"
    ):
        saleor_voucher.create_voucher("tachiya-95", "TACHIYA-ABC123")

    assert len(calls) == 2
