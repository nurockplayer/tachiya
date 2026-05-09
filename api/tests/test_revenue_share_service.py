import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.streamer import StreamerRevenueShareRecord
from services.revenue_share_service import RevenueShareLine, RevenueShareService
from services.streamer_product_assignment_service import StreamerProductAssignmentService
from services.streamer_service import StreamerService


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def create_streamer_with_assignment(
    session,
    *,
    slug="streamer-one",
    saleor_product_id="product-1",
    commission_bps=1000,
    active=True,
):
    StreamerService(session).create_profile(
        slug=slug,
        display_name=slug.title(),
        commission_bps=commission_bps,
        active=active,
    )
    StreamerProductAssignmentService(session).assign_product(
        saleor_product_id=saleor_product_id,
        streamer_slug=slug,
    )


def test_preview_order_share_calculates_streamer_share():
    session = build_session()
    create_streamer_with_assignment(session, commission_bps=1250)

    preview = RevenueShareService(session).preview_order_share(
        order_id=" saleor-order-1 ",
        lines=[RevenueShareLine(saleor_product_id=" product-1 ", gross_amount=1200)],
    )

    assert preview.order_id == "saleor-order-1"
    assert preview.unassigned_product_ids == []
    assert preview.shares[0].streamer_slug == "streamer-one"
    assert preview.shares[0].gross_amount == 1200
    assert preview.shares[0].commission_bps == 1250
    assert preview.shares[0].share_amount == 150


def test_preview_order_share_aggregates_same_streamer_lines():
    session = build_session()
    create_streamer_with_assignment(session, saleor_product_id="product-1", commission_bps=1000)
    StreamerProductAssignmentService(session).assign_product(
        saleor_product_id="product-2",
        streamer_slug="streamer-one",
    )

    preview = RevenueShareService(session).preview_order_share(
        order_id="order-1",
        lines=[
            RevenueShareLine(saleor_product_id="product-1", gross_amount=1200),
            RevenueShareLine(saleor_product_id="product-2", gross_amount=300),
        ],
    )

    assert len(preview.shares) == 1
    assert preview.shares[0].gross_amount == 1500
    assert preview.shares[0].share_amount == 150


def test_preview_order_share_tracks_unassigned_and_inactive_products():
    session = build_session()
    create_streamer_with_assignment(
        session,
        slug="inactive-streamer",
        saleor_product_id="inactive-product",
        active=False,
    )

    preview = RevenueShareService(session).preview_order_share(
        order_id="order-1",
        lines=[
            RevenueShareLine(saleor_product_id="missing-product", gross_amount=1200),
            RevenueShareLine(saleor_product_id="inactive-product", gross_amount=300),
        ],
    )

    assert preview.shares == []
    assert preview.unassigned_product_ids == ["missing-product", "inactive-product"]


@pytest.mark.parametrize(
    ("order_id", "line", "message"),
    [
        (" ", RevenueShareLine(saleor_product_id="product-1", gross_amount=1200), "order_id is required"),
        ("order-1", RevenueShareLine(saleor_product_id=" ", gross_amount=1200), "saleor_product_id is required"),
        ("order-1", RevenueShareLine(saleor_product_id="product-1", gross_amount=0), "gross_amount must be positive"),
    ],
)
def test_preview_order_share_rejects_invalid_input(order_id, line, message):
    session = build_session()

    with pytest.raises(ValueError, match=message):
        RevenueShareService(session).preview_order_share(order_id=order_id, lines=[line])


def test_record_order_share_persists_pending_records():
    session = build_session()
    create_streamer_with_assignment(session, commission_bps=1250)

    result = RevenueShareService(session).record_order_share(
        order_id=" saleor-order-1 ",
        lines=[
            RevenueShareLine(saleor_product_id=" product-1 ", gross_amount=1200),
            RevenueShareLine(saleor_product_id="missing-product", gross_amount=300),
        ],
    )

    assert result.order_id == "saleor-order-1"
    assert result.unassigned_product_ids == ["missing-product"]
    assert len(result.records) == 1
    record = result.records[0]
    assert record.streamer_slug == "streamer-one"
    assert record.gross_amount == 1200
    assert record.commission_bps == 1250
    assert record.share_amount == 150
    assert record.status == "pending"
    assert session.query(StreamerRevenueShareRecord).count() == 1


def test_record_order_share_is_idempotent_for_same_result():
    session = build_session()
    create_streamer_with_assignment(session, commission_bps=1000)
    service = RevenueShareService(session)

    first_result = service.record_order_share(
        order_id="order-1",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=1200)],
    )
    second_result = service.record_order_share(
        order_id="order-1",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=1200)],
    )

    assert second_result.records[0].id == first_result.records[0].id
    assert session.query(StreamerRevenueShareRecord).count() == 1


def test_record_order_share_rejects_conflicting_replay():
    session = build_session()
    create_streamer_with_assignment(session, commission_bps=1000)
    service = RevenueShareService(session)
    service.record_order_share(
        order_id="order-1",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=1200)],
    )

    with pytest.raises(ValueError, match="revenue share record conflict"):
        service.record_order_share(
            order_id="order-1",
            lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=1300)],
        )

    assert session.query(StreamerRevenueShareRecord).count() == 1
