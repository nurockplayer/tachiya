import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.identity_audit_event import IdentityAuditEvent
from models.identity_mapping import IdentityMapping
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


def test_link_identity_stores_blank_audit_reason_as_none():
    session = build_session()
    service = IdentityMappingService(session)

    service.link_identity(
        "saleor-user-1",
        "tachigo",
        "tachigo-user-1",
        actor="ops-user-1",
        reason="   ",
    )

    event = session.query(IdentityAuditEvent).one()
    assert event.reason is None


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

    with pytest.raises(
        ValueError, match="saleor customer already has active provider mapping"
    ):
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

    service.unlink_identity(
        mapping.id, actor="ops-user-1", reason="user requested unlink"
    )

    events = (
        session.query(IdentityAuditEvent).order_by(IdentityAuditEvent.created_at).all()
    )
    assert [event.action for event in events] == [
        "identity.linked",
        "identity.unlinked",
    ]
    assert events[-1].actor == "ops-user-1"
    assert events[-1].source == "tachigo:tachigo-user-1"
    assert events[-1].target == "saleor:saleor-user-1"
    assert events[-1].reason == "user requested unlink"


def test_unlink_identity_stores_blank_audit_reason_as_none():
    session = build_session()
    service = IdentityMappingService(session)
    mapping = service.link_identity("saleor-user-1", "tachigo", "tachigo-user-1")

    service.unlink_identity(mapping.id, actor="ops-user-1", reason="   ")

    events = (
        session.query(IdentityAuditEvent).order_by(IdentityAuditEvent.created_at).all()
    )
    assert events[-1].action == "identity.unlinked"
    assert events[-1].reason is None


def test_link_identity_relinks_unlinked_external_subject_with_audit_event():
    session = build_session()
    service = IdentityMappingService(session)
    mapping = service.link_identity("saleor-user-1", "tachigo", "tachigo-user-1")
    service.unlink_identity(
        mapping.id, actor="ops-user-1", reason="user requested unlink"
    )

    relinked = service.link_identity(
        "saleor-user-2",
        "tachigo",
        "tachigo-user-1",
        actor="ops-user-2",
        reason="verified new owner",
    )

    events = (
        session.query(IdentityAuditEvent).order_by(IdentityAuditEvent.created_at).all()
    )
    assert relinked.id == mapping.id
    assert relinked.saleor_customer_id == "saleor-user-2"
    assert relinked.unlinked_at is None
    assert service.resolve_customer_id("tachigo", "tachigo-user-1") == "saleor-user-2"
    assert [event.action for event in events] == [
        "identity.linked",
        "identity.unlinked",
        "identity.relinked",
    ]
    assert events[-1].actor == "ops-user-2"
    assert events[-1].source == "tachigo:tachigo-user-1"
    assert events[-1].target == "saleor:saleor-user-2"
    assert events[-1].reason == "verified new owner"


def test_list_mappings_filters_active_and_unlinked_mappings():
    session = build_session()
    service = IdentityMappingService(session)
    tachigo_mapping = service.link_identity(
        "saleor-user-1", "tachigo", "tachigo-user-1"
    )
    twitch_mapping = service.link_identity("saleor-user-2", "twitch", "twitch-user-1")
    service.unlink_identity(tachigo_mapping.id)

    active_mappings = service.list_mappings()
    tachigo_history = service.list_mappings(provider=" Tachigo ", include_unlinked=True)
    customer_mappings = service.list_mappings(saleor_customer_id=" saleor-user-2 ")

    assert [mapping.id for mapping in active_mappings] == [twitch_mapping.id]
    assert [mapping.id for mapping in tachigo_history] == [tachigo_mapping.id]
    assert [mapping.id for mapping in customer_mappings] == [twitch_mapping.id]


def test_list_mappings_filters_external_subject_and_created_range():
    session = build_session()
    service = IdentityMappingService(session)
    session.add_all(
        [
            IdentityMapping(
                id="before-range",
                saleor_customer_id="saleor-user-1",
                provider="youtube",
                external_subject="shared-user",
                verified_at=datetime(2026, 1, 1, 0, 0, 0),
                created_at=datetime(2026, 1, 1, 23, 59, 59),
            ),
            IdentityMapping(
                id="matching-old",
                saleor_customer_id="saleor-user-2",
                provider="tachigo",
                external_subject="shared-user",
                verified_at=datetime(2026, 1, 2, 0, 0, 0),
                created_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
            IdentityMapping(
                id="matching-new",
                saleor_customer_id="saleor-user-3",
                provider="twitch",
                external_subject="shared-user",
                verified_at=datetime(2026, 1, 3, 0, 0, 0),
                created_at=datetime(2026, 1, 3, 0, 0, 0),
                unlinked_at=datetime(2026, 1, 4, 0, 0, 0),
            ),
            IdentityMapping(
                id="after-range",
                saleor_customer_id="saleor-user-4",
                provider="discord",
                external_subject="shared-user",
                verified_at=datetime(2026, 1, 3, 0, 0, 1),
                created_at=datetime(2026, 1, 3, 0, 0, 1),
            ),
        ],
    )
    session.commit()

    mappings = service.list_mappings(
        external_subject=" shared-user ",
        created_from=datetime(2026, 1, 2, 0, 0, 0),
        created_to=datetime(2026, 1, 3, 0, 0, 0),
        include_unlinked=True,
        limit=10,
    )

    assert [mapping.id for mapping in mappings] == ["matching-new", "matching-old"]


def test_list_mappings_rejects_invalid_created_range():
    session = build_session()
    service = IdentityMappingService(session)

    with pytest.raises(ValueError, match="invalid created_at range"):
        service.list_mappings(
            created_from=datetime(2026, 1, 3, 0, 0, 0),
            created_to=datetime(2026, 1, 2, 0, 0, 0),
        )


@pytest.mark.parametrize("limit", [0, 101, True])
def test_list_mappings_rejects_invalid_limit(limit):
    session = build_session()

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        IdentityMappingService(session).list_mappings(limit=limit)


def test_list_audit_events_filters_fields_and_created_range():
    session = build_session()
    service = IdentityMappingService(session)
    session.add_all(
        [
            IdentityAuditEvent(
                id="before-range",
                action="identity.linked",
                actor="ops-user-1",
                source="tachigo:tachigo-user-1",
                target="saleor:saleor-user-1",
                reason="before",
                created_at=datetime(2026, 1, 1, 23, 59, 59),
            ),
            IdentityAuditEvent(
                id="matching-old",
                action="identity.relinked",
                actor="ops-user-2",
                source="tachigo:tachigo-user-1",
                target="saleor:saleor-user-2",
                reason="older match",
                created_at=datetime(2026, 1, 2, 0, 0, 0),
            ),
            IdentityAuditEvent(
                id="matching-new",
                action="identity.relinked",
                actor="ops-user-2",
                source="tachigo:tachigo-user-1",
                target="saleor:saleor-user-2",
                reason="newer match",
                created_at=datetime(2026, 1, 3, 0, 0, 0),
            ),
            IdentityAuditEvent(
                id="after-range",
                action="identity.relinked",
                actor="ops-user-2",
                source="tachigo:tachigo-user-1",
                target="saleor:saleor-user-2",
                reason="after",
                created_at=datetime(2026, 1, 3, 0, 0, 1),
            ),
        ],
    )
    session.commit()

    events = service.list_audit_events(
        action=" identity.relinked ",
        actor=" ops-user-2 ",
        source=" tachigo:tachigo-user-1 ",
        target=" saleor:saleor-user-2 ",
        created_from=datetime(2026, 1, 2, 0, 0, 0),
        created_to=datetime(2026, 1, 3, 0, 0, 0),
        limit=10,
    )

    assert [event.reason for event in events] == ["newer match", "older match"]


def test_list_audit_events_rejects_invalid_created_range():
    session = build_session()
    service = IdentityMappingService(session)

    with pytest.raises(ValueError, match="invalid created_at range"):
        service.list_audit_events(
            created_from=datetime(2026, 1, 3, 0, 0, 0),
            created_to=datetime(2026, 1, 2, 0, 0, 0),
        )


@pytest.mark.parametrize("limit", [0, 101, True])
def test_list_audit_events_rejects_invalid_limit(limit):
    session = build_session()

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        IdentityMappingService(session).list_audit_events(limit=limit)


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        ("provider", {"provider": " "}),
        ("saleor_customer_id", {"saleor_customer_id": " "}),
        ("external_subject", {"external_subject": " "}),
    ],
)
def test_list_mappings_rejects_blank_filters(field, kwargs):
    session = build_session()

    with pytest.raises(ValueError, match=f"{field} is required"):
        IdentityMappingService(session).list_mappings(**kwargs)
