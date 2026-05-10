import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.streamer import StreamerProductAssignment
from services.streamer_product_assignment_service import StreamerProductAssignmentService
from services.streamer_service import StreamerService


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def create_streamer(session, slug="streamer-one"):
    return StreamerService(session).create_profile(slug=slug, display_name=slug.title())


def test_assign_product_to_streamer():
    session = build_session()
    streamer = create_streamer(session)

    assignment = StreamerProductAssignmentService(session).assign_product(
        saleor_product_id=" product-1 ",
        streamer_slug=" Streamer-One ",
        source=" saleor-metadata ",
    )

    assert assignment.saleor_product_id == "product-1"
    assert assignment.streamer_profile_id == streamer.id
    assert assignment.streamer_slug == "streamer-one"
    assert assignment.source == "saleor-metadata"


def test_assign_product_is_idempotent_for_same_streamer():
    session = build_session()
    create_streamer(session)
    service = StreamerProductAssignmentService(session)

    first_assignment = service.assign_product(
        saleor_product_id="product-1",
        streamer_slug="streamer-one",
    )
    second_assignment = service.assign_product(
        saleor_product_id="product-1",
        streamer_slug="streamer-one",
    )

    assert second_assignment.id == first_assignment.id
    assert session.query(StreamerProductAssignment).count() == 1


def test_assign_product_updates_existing_assignment():
    session = build_session()
    first_streamer = create_streamer(session, slug="streamer-one")
    second_streamer = create_streamer(session, slug="streamer-two")
    service = StreamerProductAssignmentService(session)

    first_assignment = service.assign_product(
        saleor_product_id="product-1",
        streamer_slug=first_streamer.slug,
    )
    updated_assignment = service.assign_product(
        saleor_product_id="product-1",
        streamer_slug=second_streamer.slug,
        source="manual-correction",
    )

    assert updated_assignment.id == first_assignment.id
    assert updated_assignment.streamer_profile_id == second_streamer.id
    assert updated_assignment.streamer_slug == "streamer-two"
    assert updated_assignment.source == "manual-correction"
    assert session.query(StreamerProductAssignment).count() == 1


def test_get_by_product_id_normalizes_lookup():
    session = build_session()
    create_streamer(session)
    service = StreamerProductAssignmentService(session)
    service.assign_product(saleor_product_id="product-1", streamer_slug="streamer-one")

    assignment = service.get_by_product_id(" product-1 ")

    assert assignment is not None
    assert assignment.saleor_product_id == "product-1"


def test_list_product_ids_for_streamer_catalog():
    session = build_session()
    create_streamer(session)
    create_streamer(session, slug="streamer-two")
    service = StreamerProductAssignmentService(session)
    service.assign_product(saleor_product_id="product-2", streamer_slug="streamer-one")
    service.assign_product(saleor_product_id="product-1", streamer_slug="streamer-one")
    service.assign_product(saleor_product_id="other-product", streamer_slug="streamer-two")

    product_ids = service.list_product_ids_for_streamer(" Streamer-One ")

    assert product_ids == ["product-2", "product-1"]


def test_list_assignments_filters_for_operational_audit():
    session = build_session()
    create_streamer(session)
    create_streamer(session, slug="streamer-two")
    service = StreamerProductAssignmentService(session)
    service.assign_product(
        saleor_product_id="product-1",
        streamer_slug="streamer-one",
        source="saleor-metadata",
    )
    service.assign_product(
        saleor_product_id="product-2",
        streamer_slug="streamer-one",
        source="manual",
    )
    service.assign_product(
        saleor_product_id="product-3",
        streamer_slug="streamer-two",
        source="saleor-metadata",
    )

    assignments = service.list_assignments(
        streamer_slug=" Streamer-One ",
        source=" saleor-metadata ",
        limit=10,
    )

    assert len(assignments) == 1
    assert assignments[0].saleor_product_id == "product-1"
    assert assignments[0].streamer_slug == "streamer-one"
    assert assignments[0].source == "saleor-metadata"


def test_list_assignments_filters_created_range_inclusively():
    session = build_session()
    create_streamer(session)
    service = StreamerProductAssignmentService(session)
    before = service.assign_product(
        saleor_product_id="product-before",
        streamer_slug="streamer-one",
    )
    range_start = service.assign_product(
        saleor_product_id="product-start",
        streamer_slug="streamer-one",
    )
    range_end = service.assign_product(
        saleor_product_id="product-end",
        streamer_slug="streamer-one",
    )
    after = service.assign_product(
        saleor_product_id="product-after",
        streamer_slug="streamer-one",
    )
    before.created_at = datetime(2026, 1, 1, 23, 59, 59)
    range_start.created_at = datetime(2026, 1, 2, 0, 0, 0)
    range_end.created_at = datetime(2026, 1, 3, 0, 0, 0)
    after.created_at = datetime(2026, 1, 3, 0, 0, 1)
    session.commit()

    assignments = service.list_assignments(
        created_from=datetime(2026, 1, 2, 0, 0, 0),
        created_to=datetime(2026, 1, 3, 0, 0, 0),
        limit=10,
    )

    assert [assignment.saleor_product_id for assignment in assignments] == [
        "product-end",
        "product-start",
    ]


def test_list_assignments_rejects_invalid_created_range():
    session = build_session()

    with pytest.raises(ValueError, match="invalid created_at range"):
        StreamerProductAssignmentService(session).list_assignments(
            created_from=datetime(2026, 1, 3, 0, 0, 0),
            created_to=datetime(2026, 1, 2, 0, 0, 0),
        )


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        ("streamer_slug", {"streamer_slug": " "}),
        ("source", {"source": " "}),
    ],
)
def test_list_assignments_rejects_blank_filters(field, kwargs):
    session = build_session()

    with pytest.raises(ValueError, match=f"{field} is required"):
        StreamerProductAssignmentService(session).list_assignments(**kwargs)


@pytest.mark.parametrize("limit", [0, 101, True])
def test_list_assignments_rejects_invalid_limit(limit):
    session = build_session()

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        StreamerProductAssignmentService(session).list_assignments(limit=limit)


def test_remove_product_assignment():
    session = build_session()
    create_streamer(session)
    service = StreamerProductAssignmentService(session)
    service.assign_product(saleor_product_id="product-1", streamer_slug="streamer-one")

    removed_assignment = service.remove_product(" product-1 ")

    assert removed_assignment.saleor_product_id == "product-1"
    assert service.get_by_product_id("product-1") is None
    assert session.query(StreamerProductAssignment).count() == 0


def test_remove_product_assignment_returns_none_for_missing_product():
    session = build_session()

    removed_assignment = StreamerProductAssignmentService(session).remove_product("missing-product")

    assert removed_assignment is None


def test_assign_product_rejects_missing_streamer():
    session = build_session()

    with pytest.raises(ValueError, match="streamer profile not found"):
        StreamerProductAssignmentService(session).assign_product(
            saleor_product_id="product-1",
            streamer_slug="missing-streamer",
        )

    assert session.query(StreamerProductAssignment).count() == 0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("saleor_product_id", " ", "saleor_product_id is required"),
        ("source", " ", "source is required"),
    ],
)
def test_assign_product_rejects_blank_required_fields(field, value, message):
    session = build_session()
    create_streamer(session)
    payload = {
        "saleor_product_id": "product-1",
        "streamer_slug": "streamer-one",
        "source": "manual",
    } | {field: value}

    with pytest.raises(ValueError, match=message):
        StreamerProductAssignmentService(session).assign_product(**payload)

    assert session.query(StreamerProductAssignment).count() == 0
