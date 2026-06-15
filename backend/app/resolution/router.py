"""REST API for entity resolution."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.db.dependencies import AsyncDBSession
from app.auth.credentials import WorkspaceUserDep

from app.resolution.blocking import BlockingKey
from app.resolution.scoring import FieldRule
from app.resolution.survivorship import SurvivorshipRule
from app.resolution.service import ResolutionService, ResolutionConfig
from app.resolution.schemas import (
    ResolveRequest,
    ResolveResponse,
    MergeRequest,
    ClusterOut,
    ClusterDetailOut,
    ClusterListOut,
    ClusterMemberOut,
    ResolutionConfigIn,
)

router = APIRouter(tags=["Entity Resolution"])


def _build_config(cfg: Optional[ResolutionConfigIn]) -> Optional[ResolutionConfig]:
    """Translate an inbound pydantic config into the service dataclass config.

    Returns None when no config (or an empty one) is supplied, so the service derives a
    default config from the schema.
    """
    if cfg is None:
        return None
    # If the caller gave no rules, defer to schema-derived defaults.
    if not cfg.rules and not cfg.blocking_keys:
        return None
    return ResolutionConfig(
        blocking_keys=[
            BlockingKey(field=k.field, strategy=k.strategy, length=k.length)
            for k in (cfg.blocking_keys or [])
        ],
        rules=[
            FieldRule(field=r.field, comparator=r.comparator, weight=r.weight, threshold=r.threshold)
            for r in (cfg.rules or [])
        ],
        survivorship=[
            SurvivorshipRule(field=s.field, strategy=s.strategy, source_priority=s.source_priority)
            for s in (cfg.survivorship or [])
        ],
        match=cfg.match,
        review_low=cfg.review_low,
        review_high=cfg.review_high,
        entity_type=cfg.entity_type,
    )


def _cluster_out(c) -> ClusterOut:
    return ClusterOut(
        id=c.id,
        workspace_id=c.workspace_id,
        schema_id=c.schema_id,
        entity_type=c.entity_type,
        canonical=c.canonical or {},
        member_count=c.member_count,
        status=c.status,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.post("/resolve", response_model=ResolveResponse)
async def resolve(
    request: ResolveRequest,
    role: WorkspaceUserDep,
    db: AsyncDBSession,
):
    service = ResolutionService(db, role.workspace_id)
    config = _build_config(request.config)
    result = await service.resolve(request.schema_id, config)
    return ResolveResponse(**result.as_dict())


@router.get("/clusters", response_model=ClusterListOut)
async def list_clusters(
    role: WorkspaceUserDep,
    db: AsyncDBSession,
    schema_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    service = ResolutionService(db, role.workspace_id)
    clusters = await service.list_clusters(schema_id, limit, offset)
    return ClusterListOut(
        clusters=[_cluster_out(c) for c in clusters],
        count=len(clusters),
    )


@router.get("/clusters/{cluster_id}", response_model=ClusterDetailOut)
async def get_cluster(
    cluster_id: str,
    role: WorkspaceUserDep,
    db: AsyncDBSession,
):
    service = ResolutionService(db, role.workspace_id)
    cluster_row = await service.get_cluster(cluster_id)
    if cluster_row is None:
        raise HTTPException(status_code=404, detail="Cluster not found")
    members = await service.get_members(cluster_id)
    base = _cluster_out(cluster_row)
    return ClusterDetailOut(
        **base.model_dump(),
        members=[
            ClusterMemberOut(
                id=m.id,
                record_id=m.record_id,
                source=m.source,
                match_score=m.match_score,
                linked_at=m.linked_at,
            )
            for m in members
        ],
    )


@router.post("/clusters/{cluster_id}/split")
async def split_cluster(
    cluster_id: str,
    role: WorkspaceUserDep,
    db: AsyncDBSession,
):
    service = ResolutionService(db, role.workspace_id)
    ok = await service.split_cluster(cluster_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return {"status": "split", "cluster_id": cluster_id}


@router.post("/merge", response_model=ClusterDetailOut)
async def manual_merge(
    request: MergeRequest,
    role: WorkspaceUserDep,
    db: AsyncDBSession,
):
    service = ResolutionService(db, role.workspace_id)
    cluster_row = await service.manual_merge(
        request.schema_id, request.record_ids, entity_type=request.entity_type
    )
    members = await service.get_members(cluster_row.id)
    base = _cluster_out(cluster_row)
    return ClusterDetailOut(
        **base.model_dump(),
        members=[
            ClusterMemberOut(
                id=m.id,
                record_id=m.record_id,
                source=m.source,
                match_score=m.match_score,
                linked_at=m.linked_at,
            )
            for m in members
        ],
    )
