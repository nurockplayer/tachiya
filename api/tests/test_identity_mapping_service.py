import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.identity_audit_event import IdentityAuditEvent
from services.identity_mapping_service import IdentityMappingService


def build_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_link_identity_creates_and_resolves_active_mapping():
    session = build_session()
    service = IdentityMappingService(session)

    mapping = service.link_identity(
        saleor_customer_id="saleor-user-1",
        provider="tachigo",
        external_subject="tachigo-user-1",
    )

    resolved = service.resolve_customer_id("tachigo", "tachigo-user-1")

    assert mapping.saleor_customer_id == "saleor-user-1"
    assert mapping.provider == "tachigo"
    assert mapping.external_subject == "tachigo-user-1"
    assert mapping.verified_at is not None
    assert mapping.unlinked_at is None
    assert resolved == "saleor-user-1"


def test_link_identity_records_audit_event():
    session = build_session()
    service = IdentityMappingService(session)

    service.link_identity(
        "saleor-user-1",
        "tachigo",
        "tachigo-user-1",
        actor="ops-user-1",
        reason="initial link",
    )

    event = session.query(IdentityAuditEvent).one()
    assert event.action == "identity.linked"
    assert event.actor == "ops-user-1"
    assert event.source == "tachigo:tachigo-user-1"
    assert event.target == "saleor:saleor-user-1"
    assert event.reason == "initial link"


def test_link_identity_rejects_duplicate_external_subject():
    session = build_session()
    service = IdentityMappingService(session)
    service.link_identity("saleor-user-1", "tachigo", "tachigo-user-1")

    with pytest.raises(ValueError, match="identity mapping already exists"):
        service.link_identity("saleor-user-2", "tachigo", "tachigo-user-1")


def test_link_identity_rejects_second_active_mapping_for_same_provider():
    session = build_session()
    service = IdentityMappingService(session)
    service.link_identity("saleor-user-1", "tachigo", "tachigo-user-1")

    with pytest.raises(ValueError, match="saleor customer already has active provider mapping"):
        service.link_identity("saleor-user-1", "tachigo", "tachigo-user-2")


def test_unlink_identity_hides_mapping_from_resolution():
    session = build_session()
    service = IdentityMappingService(session)
    mapping = service.link_identity("saleor-user-1", "tachigo", "tachigo-user-1")

    unlinked = service.unlink_identity(mapping.id)

    assert unlinked.unlinked_at is not None
    assert service.resolve_customer_id("tachigo", "tachigo-user-1") is None


def test_unlink_identity_records_audit_event():
    session = build_session()
    service = IdentityMappingService(session)
    mapping = service.link_identity("saleor-user-1", "tachigo", "tachigo-user-1")

    service.unlink_identity(mapping.id, actor="ops-user-1", reason="user requested unlink")

    events = session.query(IdentityAuditEvent).order_by(IdentityAuditEvent.created_at).all()
    assert [event.action for event in events] == ["identity.linked", "identity.unlinked"]
    assert events[-1].actor == "ops-user-1"
    assert events[-1].source == "tachigo:tachigo-user-1"
    assert events[-1].target == "saleor:saleor-user-1"
    assert events[-1].reason == "user requested unlink"
