import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.streamer import StreamerProfile
from services.streamer_service import StreamerService


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_create_profile_normalizes_fields():
    session = build_session()
    profile = StreamerService(session).create_profile(
        slug=" Streamer-One ",
        display_name=" Streamer One ",
        saleor_collection_id=" collection-1 ",
        commission_bps=1250,
    )

    assert profile.slug == "streamer-one"
    assert profile.display_name == "Streamer One"
    assert profile.saleor_collection_id == "collection-1"
    assert profile.commission_bps == 1250
    assert profile.active is True


def test_create_profile_treats_blank_collection_as_unset():
    session = build_session()
    profile = StreamerService(session).create_profile(
        slug="streamer-one",
        display_name="Streamer One",
        saleor_collection_id=" ",
    )

    assert profile.saleor_collection_id is None


def test_get_by_slug_normalizes_lookup():
    session = build_session()
    StreamerService(session).create_profile(slug="streamer-one", display_name="Streamer One")

    profile = StreamerService(session).get_by_slug(" Streamer-One ")

    assert profile is not None
    assert profile.slug == "streamer-one"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("slug", " ", "slug is required"),
        ("display_name", " ", "display_name is required"),
    ],
)
def test_create_profile_rejects_blank_required_fields(field, value, message):
    session = build_session()
    payload = {
        "slug": "streamer-one",
        "display_name": "Streamer One",
    } | {field: value}

    with pytest.raises(ValueError, match=message):
        StreamerService(session).create_profile(**payload)

    assert session.query(StreamerProfile).count() == 0


@pytest.mark.parametrize("commission_bps", [-1, 10001])
def test_create_profile_rejects_invalid_commission(commission_bps):
    session = build_session()

    with pytest.raises(ValueError, match="commission_bps must be between 0 and 10000"):
        StreamerService(session).create_profile(
            slug="streamer-one",
            display_name="Streamer One",
            commission_bps=commission_bps,
        )

    assert session.query(StreamerProfile).count() == 0


def test_create_profile_rejects_duplicate_slug():
    session = build_session()
    service = StreamerService(session)
    service.create_profile(slug="streamer-one", display_name="Streamer One")

    with pytest.raises(ValueError, match="streamer profile already exists"):
        service.create_profile(slug="Streamer-One", display_name="Streamer Duplicate")

    assert session.query(StreamerProfile).count() == 1


def test_create_profile_rejects_duplicate_saleor_collection_id():
    session = build_session()
    service = StreamerService(session)
    service.create_profile(
        slug="streamer-one",
        display_name="Streamer One",
        saleor_collection_id="collection-1",
    )

    with pytest.raises(ValueError, match="streamer profile already exists"):
        service.create_profile(
            slug="streamer-two",
            display_name="Streamer Two",
            saleor_collection_id="collection-1",
        )

    assert session.query(StreamerProfile).count() == 1
