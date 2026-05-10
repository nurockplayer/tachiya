from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from database import get_db
from security import verify_internal_secret
from services.identity_mapping_service import IdentityMappingService

router = APIRouter(prefix="/identity-mappings", tags=["identity-mappings"])

NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class IdentityMappingCreateRequest(BaseModel):
    saleor_customer_id: NonBlankStr
    provider: NonBlankStr
    external_subject: NonBlankStr
    actor: NonBlankStr = "system"
    reason: str | None = None


class IdentityMappingResponse(BaseModel):
    id: str
    saleor_customer_id: str
    provider: str
    external_subject: str
    verified_at: datetime
    unlinked_at: datetime | None = None


class IdentityMappingListResponse(BaseModel):
    mappings: list[IdentityMappingResponse]


class IdentityMappingResolveResponse(BaseModel):
    saleor_customer_id: str
    provider: str
    external_subject: str


class IdentityMappingUnlinkResponse(BaseModel):
    id: str
    unlinked: bool
    unlinked_at: datetime


class IdentityAuditEventResponse(BaseModel):
    action: str
    actor: str
    source: str
    target: str
    reason: str | None = None
    created_at: datetime


class IdentityAuditEventsResponse(BaseModel):
    events: list[IdentityAuditEventResponse]


@router.post(
    "",
    response_model=IdentityMappingResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def create_identity_mapping(
    req: IdentityMappingCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        mapping = IdentityMappingService(db).link_identity(
            saleor_customer_id=req.saleor_customer_id,
            provider=req.provider,
            external_subject=req.external_subject,
            actor=req.actor,
            reason=req.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return IdentityMappingResponse(
        id=mapping.id,
        saleor_customer_id=mapping.saleor_customer_id,
        provider=mapping.provider,
        external_subject=mapping.external_subject,
        verified_at=mapping.verified_at,
        unlinked_at=mapping.unlinked_at,
    )


@router.get(
    "",
    response_model=IdentityMappingListResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def list_identity_mappings(
    provider: str | None = Query(default=None),
    saleor_customer_id: str | None = Query(default=None),
    external_subject: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    include_unlinked: bool = Query(default=False),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        mappings = IdentityMappingService(db).list_mappings(
            provider=provider,
            saleor_customer_id=saleor_customer_id,
            external_subject=external_subject,
            created_from=created_from,
            created_to=created_to,
            include_unlinked=include_unlinked,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return IdentityMappingListResponse(
        mappings=[
            IdentityMappingResponse(
                id=mapping.id,
                saleor_customer_id=mapping.saleor_customer_id,
                provider=mapping.provider,
                external_subject=mapping.external_subject,
                verified_at=mapping.verified_at,
                unlinked_at=mapping.unlinked_at,
            )
            for mapping in mappings
        ],
    )


@router.get(
    "/resolve",
    response_model=IdentityMappingResolveResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def resolve_identity_mapping(
    provider: str = Query(..., min_length=1),
    external_subject: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    service = IdentityMappingService(db)
    try:
        saleor_customer_id = service.resolve_customer_id(provider, external_subject)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if saleor_customer_id is None:
        raise HTTPException(status_code=404, detail="identity mapping not found")

    return IdentityMappingResolveResponse(
        saleor_customer_id=saleor_customer_id,
        provider=provider.strip().lower(),
        external_subject=external_subject.strip(),
    )


@router.get(
    "/audit-events",
    response_model=IdentityAuditEventsResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def list_identity_audit_events(
    action: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    source: str | None = Query(default=None),
    target: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        events = IdentityMappingService(db).list_audit_events(
            action=action,
            actor=actor,
            source=source,
            target=target,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return IdentityAuditEventsResponse(
        events=[
            IdentityAuditEventResponse(
                action=event.action,
                actor=event.actor,
                source=event.source,
                target=event.target,
                reason=event.reason,
                created_at=event.created_at,
            )
            for event in events
        ],
    )


@router.delete(
    "/{mapping_id}",
    response_model=IdentityMappingUnlinkResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def unlink_identity_mapping(
    mapping_id: str,
    actor: str = Query("system", min_length=1),
    reason: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    normalized_actor = actor.strip()
    if not normalized_actor:
        raise HTTPException(status_code=422, detail="actor is required")

    try:
        mapping = IdentityMappingService(db).unlink_identity(
            mapping_id,
            actor=normalized_actor,
            reason=reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return IdentityMappingUnlinkResponse(
        id=mapping.id,
        unlinked=True,
        unlinked_at=mapping.unlinked_at,
    )
