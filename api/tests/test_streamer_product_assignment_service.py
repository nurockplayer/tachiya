import sys
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
