from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from security import verify_internal_secret
from services.identity_mapping_service import IdentityMappingService

router = APIRouter(prefix="/identity-mappings", tags=["identity-mappings"])


class IdentityMappingCreateRequest(BaseModel):
    saleor_customer_id: str
    provider: str
    external_subject: str


class IdentityMappingResponse(BaseModel):
    id: str
    saleor_customer_id: str
    provider: str
    external_subject: str
    verified_at: datetime
    unlinked_at: datetime | None = None


class IdentityMappingResolveResponse(BaseModel):
    saleor_customer_id: str
    provider: str
    external_subject: str


class IdentityMappingUnlinkResponse(BaseModel):
    id: str
    unlinked: bool
    unlinked_at: datetime


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
    saleor_customer_id = service.resolve_customer_id(provider, external_subject)
    if saleor_customer_id is None:
        raise HTTPException(status_code=404, detail="identity mapping not found")

    return IdentityMappingResolveResponse(
        saleor_customer_id=saleor_customer_id,
        provider=provider.strip().lower(),
        external_subject=external_subject.strip(),
    )


@router.delete(
    "/{mapping_id}",
    response_model=IdentityMappingUnlinkResponse,
    dependencies=[Depends(verify_internal_secret)],
)
def unlink_identity_mapping(
    mapping_id: str,
    db: Session = Depends(get_db),
):
    try:
        mapping = IdentityMappingService(db).unlink_identity(mapping_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return IdentityMappingUnlinkResponse(
        id=mapping.id,
        unlinked=True,
        unlinked_at=mapping.unlinked_at,
    )
