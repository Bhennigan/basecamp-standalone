"""Transformation API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, and_
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_404_NOT_FOUND

from app.auth.credentials import WorkspaceUserDep
from app.db.dependencies import AsyncDBSession
from app.db.models import MappingProfile as MappingProfileModel
from app.transform.models import (
    FieldMapping,
    MappingProfile,
    MappingProfileRead,
    TransformPreviewRequest,
    TransformPreviewResponse,
)
from app.transform.engine import transform_batch

router = APIRouter(prefix="", tags=["transform"])


def _profile_to_read(p: MappingProfileModel) -> MappingProfileRead:
    return MappingProfileRead(
        id=p.id,
        workspace_id=p.workspace_id,
        name=p.name,
        description=p.description,
        source_schema_id=p.source_schema_id,
        target_schema_id=p.target_schema_id,
        mappings=p.mappings or [],
        drop_unmapped=p.drop_unmapped,
        created_at=p.created_at.isoformat() if p.created_at else "",
        updated_at=p.updated_at.isoformat() if p.updated_at else "",
    )


@router.get("/profiles")
async def list_profiles(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[MappingProfileRead]:
    """List all mapping profiles for the workspace."""
    stmt = (
        select(MappingProfileModel)
        .where(MappingProfileModel.workspace_id == str(role.workspace_id))
        .order_by(MappingProfileModel.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return [_profile_to_read(p) for p in result.scalars().all()]


@router.post("/profiles", status_code=HTTP_201_CREATED)
async def create_profile(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    data: MappingProfile,
) -> MappingProfileRead:
    """Create a new mapping profile."""
    profile = MappingProfileModel(
        workspace_id=str(role.workspace_id),
        name=data.name,
        description=data.description,
        source_schema_id=data.source_schema_id,
        target_schema_id=data.target_schema_id,
        mappings=[m.model_dump() for m in data.mappings],
        drop_unmapped=data.drop_unmapped,
    )
    session.add(profile)
    await session.flush()
    await session.refresh(profile)
    return _profile_to_read(profile)


@router.get("/profiles/{profile_id}")
async def get_profile(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    profile_id: str,
) -> MappingProfileRead:
    """Get a mapping profile by ID."""
    stmt = select(MappingProfileModel).where(
        and_(
            MappingProfileModel.workspace_id == str(role.workspace_id),
            MappingProfileModel.id == profile_id,
        )
    )
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Mapping profile not found")
    return _profile_to_read(profile)


@router.patch("/profiles/{profile_id}")
async def update_profile(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    profile_id: str,
    data: MappingProfile,
) -> MappingProfileRead:
    """Update a mapping profile."""
    stmt = select(MappingProfileModel).where(
        and_(
            MappingProfileModel.workspace_id == str(role.workspace_id),
            MappingProfileModel.id == profile_id,
        )
    )
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Mapping profile not found")

    profile.name = data.name
    profile.description = data.description
    profile.source_schema_id = data.source_schema_id
    profile.target_schema_id = data.target_schema_id
    profile.mappings = [m.model_dump() for m in data.mappings]
    profile.drop_unmapped = data.drop_unmapped

    await session.flush()
    await session.refresh(profile)
    return _profile_to_read(profile)


@router.delete("/profiles/{profile_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_profile(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    profile_id: str,
) -> None:
    """Delete a mapping profile."""
    stmt = select(MappingProfileModel).where(
        and_(
            MappingProfileModel.workspace_id == str(role.workspace_id),
            MappingProfileModel.id == profile_id,
        )
    )
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Mapping profile not found")
    await session.delete(profile)
    await session.flush()


@router.post("/preview")
async def preview_transform(
    *,
    role: WorkspaceUserDep,
    session: AsyncDBSession,
    request: TransformPreviewRequest,
) -> TransformPreviewResponse:
    """Preview a transformation on sample data without persisting."""
    if request.mapping_profile_id:
        stmt = select(MappingProfileModel).where(
            and_(
                MappingProfileModel.workspace_id == str(role.workspace_id),
                MappingProfileModel.id == request.mapping_profile_id,
            )
        )
        result = await session.execute(stmt)
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Mapping profile not found")
        mappings = [FieldMapping(**m) for m in (profile.mappings or [])]
        drop_unmapped = profile.drop_unmapped
    elif request.mappings:
        mappings = request.mappings
        drop_unmapped = False
    else:
        raise HTTPException(status_code=400, detail="Either mapping_profile_id or mappings required")

    transformed, errors = transform_batch(request.sample_records, mappings, drop_unmapped)

    all_source_fields = set()
    for record in request.sample_records:
        all_source_fields.update(record.keys())
    mapped_fields = {m.source_field for m in mappings}

    return TransformPreviewResponse(
        transformed_records=transformed,
        errors=errors,
        fields_mapped=len(mapped_fields & all_source_fields),
        fields_dropped=len(all_source_fields - mapped_fields) if drop_unmapped else 0,
    )
