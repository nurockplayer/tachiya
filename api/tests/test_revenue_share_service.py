import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.streamer import StreamerProfile, StreamerRevenueShareRecord
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
            RevenueShareLine(saleor_product_id="missing-product", gross_amount=400),
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


def test_record_order_share_rejects_conflict_without_partial_new_records():
    session = build_session()
    create_streamer_with_assignment(
        session,
        slug="streamer-one",
        saleor_product_id="product-1",
        commission_bps=1000,
    )
    create_streamer_with_assignment(
        session,
        slug="streamer-two",
        saleor_product_id="product-2",
        commission_bps=1000,
    )
    streamer_two = (
        session.query(StreamerProfile)
        .filter(StreamerProfile.slug == "streamer-two")
        .one()
    )
    existing_conflict = StreamerRevenueShareRecord(
        order_id="order-1",
        streamer_profile_id=streamer_two.id,
        streamer_slug="streamer-two",
        gross_amount=999,
        commission_bps=1000,
        share_amount=99,
        status="pending",
    )
    session.add(existing_conflict)
    session.commit()

    with pytest.raises(ValueError, match="revenue share record conflict"):
        RevenueShareService(session).record_order_share(
            order_id="order-1",
            lines=[
                RevenueShareLine(saleor_product_id="product-1", gross_amount=1200),
                RevenueShareLine(saleor_product_id="product-2", gross_amount=2400),
            ],
        )

    records = session.query(StreamerRevenueShareRecord).all()
    assert [(record.streamer_slug, record.gross_amount) for record in records] == [
        ("streamer-two", 999),
    ]


def test_list_records_filters_and_sorts_payout_queue():
    session = build_session()
    create_streamer_with_assignment(session, slug="streamer-one", saleor_product_id="product-1")
    create_streamer_with_assignment(session, slug="streamer-two", saleor_product_id="product-2")
    service = RevenueShareService(session)
    paid_result = service.record_order_share(
        order_id="order-1",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=1200)],
    )
    paid_result.records[0].status = "paid"
    session.commit()
    pending_result = service.record_order_share(
        order_id="order-2",
        lines=[RevenueShareLine(saleor_product_id="product-2", gross_amount=2400)],
    )

    pending_records = service.list_records(status=" pending ", limit=10)
    paid_records = service.list_records(status=" Paid ", limit=10)
    streamer_records = service.list_records(streamer_slug=" Streamer-One ", limit=10)
    order_records = service.list_records(order_id=" order-2 ", limit=10)

    assert [record.id for record in pending_records] == [pending_result.records[0].id]
    assert [record.id for record in paid_records] == [paid_result.records[0].id]
    assert [record.id for record in streamer_records] == [paid_result.records[0].id]
    assert [record.id for record in order_records] == [pending_result.records[0].id]


def test_list_records_filters_created_range_inclusively():
    session = build_session()
    create_streamer_with_assignment(session, slug="streamer-one", saleor_product_id="product-1")
    service = RevenueShareService(session)
    before = service.record_order_share(
        order_id="order-before",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=100)],
    )
    range_start = service.record_order_share(
        order_id="order-start",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=200)],
    )
    range_end = service.record_order_share(
        order_id="order-end",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=300)],
    )
    after = service.record_order_share(
        order_id="order-after",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=400)],
    )
    before.records[0].created_at = datetime(2026, 1, 1, 23, 59, 59)
    range_start.records[0].created_at = datetime(2026, 1, 2, 0, 0, 0)
    range_end.records[0].created_at = datetime(2026, 1, 3, 0, 0, 0)
    after.records[0].created_at = datetime(2026, 1, 3, 0, 0, 1)
    session.commit()

    records = service.list_records(
        created_from=datetime(2026, 1, 2, 0, 0, 0),
        created_to=datetime(2026, 1, 3, 0, 0, 0),
        limit=10,
    )

    assert [record.order_id for record in records] == ["order-end", "order-start"]


def test_list_records_rejects_invalid_created_range():
    session = build_session()

    with pytest.raises(ValueError, match="invalid created_at range"):
        RevenueShareService(session).list_records(
            created_from=datetime(2026, 1, 3, 0, 0, 0),
            created_to=datetime(2026, 1, 2, 0, 0, 0),
        )


def test_list_records_applies_limit():
    session = build_session()
    create_streamer_with_assignment(session)
    service = RevenueShareService(session)
    service.record_order_share(
        order_id="order-1",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=1200)],
    )
    service.record_order_share(
        order_id="order-2",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=1300)],
    )

    records = service.list_records(limit=1)

    assert len(records) == 1


@pytest.mark.parametrize("limit", [0, 101, True])
def test_list_records_rejects_invalid_limit(limit):
    session = build_session()

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        RevenueShareService(session).list_records(limit=limit)


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        ("status", {"status": " "}),
        ("streamer_slug", {"streamer_slug": " "}),
        ("order_id", {"order_id": " "}),
    ],
)
def test_list_records_rejects_blank_filters(field, kwargs):
    session = build_session()

    with pytest.raises(ValueError, match=f"{field} is required"):
        RevenueShareService(session).list_records(**kwargs)


def test_list_records_rejects_invalid_status_filter():
    session = build_session()

    with pytest.raises(ValueError, match="status must be pending, paid, or void"):
        RevenueShareService(session).list_records(status="settled")


def test_summarize_records_groups_totals_by_status_and_filters():
    session = build_session()
    create_streamer_with_assignment(session, slug="streamer-one", saleor_product_id="product-1")
    create_streamer_with_assignment(session, slug="streamer-two", saleor_product_id="product-2")
    service = RevenueShareService(session)
    paid_result = service.record_order_share(
        order_id="order-1",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=1200)],
    )
    service.update_record_status(record_id=paid_result.records[0].id, status="paid")
    service.record_order_share(
        order_id="order-2",
        lines=[RevenueShareLine(saleor_product_id="product-2", gross_amount=2400)],
    )
    service.record_order_share(
        order_id="order-3",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=300)],
    )

    summaries = service.summarize_records()
    streamer_summaries = service.summarize_records(streamer_slug=" Streamer-One ")
    paid_summaries = service.summarize_records(status=" Paid ")
    order_summaries = service.summarize_records(order_id=" order-2 ")

    assert [
        (summary.status, summary.record_count, summary.gross_amount, summary.share_amount)
        for summary in summaries
    ] == [
        ("paid", 1, 1200, 120),
        ("pending", 2, 2700, 270),
    ]
    assert [
        (summary.status, summary.record_count, summary.gross_amount, summary.share_amount)
        for summary in streamer_summaries
    ] == [
        ("paid", 1, 1200, 120),
        ("pending", 1, 300, 30),
    ]
    assert [
        (summary.status, summary.record_count, summary.gross_amount, summary.share_amount)
        for summary in paid_summaries
    ] == [("paid", 1, 1200, 120)]
    assert [
        (summary.status, summary.record_count, summary.gross_amount, summary.share_amount)
        for summary in order_summaries
    ] == [("pending", 1, 2400, 240)]


def test_summarize_records_filters_created_range():
    session = build_session()
    create_streamer_with_assignment(session, slug="streamer-one", saleor_product_id="product-1")
    service = RevenueShareService(session)
    before = service.record_order_share(
        order_id="order-before",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=100)],
    )
    range_record = service.record_order_share(
        order_id="order-in-range",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=200)],
    )
    after = service.record_order_share(
        order_id="order-after",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=300)],
    )
    before.records[0].created_at = datetime(2026, 1, 1, 23, 59, 59)
    range_record.records[0].created_at = datetime(2026, 1, 2, 0, 0, 0)
    after.records[0].created_at = datetime(2026, 1, 3, 0, 0, 1)
    session.commit()

    summaries = service.summarize_records(
        created_from=datetime(2026, 1, 2, 0, 0, 0),
        created_to=datetime(2026, 1, 3, 0, 0, 0),
    )

    assert [
        (summary.status, summary.record_count, summary.gross_amount, summary.share_amount)
        for summary in summaries
    ] == [("pending", 1, 200, 20)]


def test_summarize_records_rejects_invalid_created_range():
    session = build_session()

    with pytest.raises(ValueError, match="invalid created_at range"):
        RevenueShareService(session).summarize_records(
            created_from=datetime(2026, 1, 3, 0, 0, 0),
            created_to=datetime(2026, 1, 2, 0, 0, 0),
        )


def test_summarize_records_rejects_invalid_status_filter():
    session = build_session()

    with pytest.raises(ValueError, match="status must be pending, paid, or void"):
        RevenueShareService(session).summarize_records(status="settled")


def test_update_record_status_marks_pending_record_paid():
    session = build_session()
    create_streamer_with_assignment(session)
    service = RevenueShareService(session)
    result = service.record_order_share(
        order_id="order-1",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=1200)],
    )

    record = service.update_record_status(record_id=result.records[0].id, status=" Paid ")

    assert record.status == "paid"
    assert session.query(StreamerRevenueShareRecord).one().status == "paid"


def test_update_record_status_is_idempotent_for_same_terminal_status():
    session = build_session()
    create_streamer_with_assignment(session)
    service = RevenueShareService(session)
    result = service.record_order_share(
        order_id="order-1",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=1200)],
    )
    first_record = service.update_record_status(record_id=result.records[0].id, status="paid")

    second_record = service.update_record_status(record_id=result.records[0].id, status="paid")

    assert second_record.id == first_record.id
    assert second_record.status == "paid"


def test_update_record_status_rejects_terminal_status_conflict():
    session = build_session()
    create_streamer_with_assignment(session)
    service = RevenueShareService(session)
    result = service.record_order_share(
        order_id="order-1",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=1200)],
    )
    service.update_record_status(record_id=result.records[0].id, status="paid")

    with pytest.raises(ValueError, match="revenue share status conflict"):
        service.update_record_status(record_id=result.records[0].id, status="void")


@pytest.mark.parametrize("status", ["pending", "settled", " "])
def test_update_record_status_rejects_invalid_target_status(status):
    session = build_session()
    create_streamer_with_assignment(session)
    service = RevenueShareService(session)
    result = service.record_order_share(
        order_id="order-1",
        lines=[RevenueShareLine(saleor_product_id="product-1", gross_amount=1200)],
    )

    with pytest.raises(ValueError, match="status must be paid or void"):
        service.update_record_status(record_id=result.records[0].id, status=status)


def test_update_record_status_rejects_missing_record():
    session = build_session()

    with pytest.raises(ValueError, match="revenue share record not found"):
        RevenueShareService(session).update_record_status(record_id="missing-record", status="paid")
