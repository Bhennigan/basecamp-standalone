"""Entity-resolution orchestration.

``ResolutionService.resolve`` runs the full pipeline for one schema:

    load records -> blocking -> candidate pairs -> score -> classify
                 -> cluster MATCH pairs (transitive closure)
                 -> survivorship (golden record) -> persist clusters/members
                 -> queue REVIEW-band pairs for human approval
                 -> record DataLineage per cluster

Transaction discipline mirrors the rest of the codebase: rows are added to the
request-scoped session and the request-level ``get_db`` commits. We rely on the
models' Python-side UUID defaults so cluster ids are available for child rows without a
per-row flush.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select, and_, func

from app.db.models import DataRecord, BaseCampSchema
from app.compliance.models import DataLineage
from app.review.service import ReviewService

from app.resolution.blocking import BlockingKey, build_blocks, candidate_pairs
from app.resolution.scoring import FieldRule, ScoreConfig, score_pair, classify
from app.resolution.clustering import cluster as cluster_pairs
from app.resolution.survivorship import SurvivorshipRule, build_golden
from app.resolution.models import EntityCluster, ClusterMember


# Reserved meta keys injected onto each record dict for survivorship.
SOURCE_FIELD = "_source"
UPDATED_FIELD = "_updated"
RECORD_ID_FIELD = "_record_id"


@dataclass
class ResolutionConfig:
    blocking_keys: list[BlockingKey]
    rules: list[FieldRule]
    survivorship: list[SurvivorshipRule] = dc_field(default_factory=list)
    match: float = 0.85
    review_low: float = 0.6
    review_high: float = 0.85
    entity_type: Optional[str] = None

    @property
    def score_config(self) -> ScoreConfig:
        return ScoreConfig(
            rules=self.rules,
            match=self.match,
            review_low=self.review_low,
            review_high=self.review_high,
        )


@dataclass
class ResolutionResult:
    records: int
    pairs_compared: int
    clusters: int
    merged: int
    queued_for_review: int

    def as_dict(self) -> dict:
        return {
            "records": self.records,
            "pairs_compared": self.pairs_compared,
            "clusters": self.clusters,
            "merged": self.merged,
            "queued_for_review": self.queued_for_review,
        }


# --- Heuristics for auto-deriving a config from a schema -----------------------

# Natural identifiers: strong, cross-source match features (a real person carries these).
_ID_HINTS = ("email", "ssn", "tax", "phone", "msisdn")
_NAME_HINTS = ("name", "first", "last", "surname", "given", "company", "org", "title")
# Surrogate keys: identify a SOURCE ROW, not the entity. They differ across systems for the
# same real-world entity, so comparing them is meaningless and actively prevents matches.
# Detected precisely (exact name or *_id / *_uuid suffix), never by loose substring.
_SURROGATE_KEYS = {"id", "uuid", "guid", "pk", "rowid", "key", "_id"}
_SURROGATE_SUFFIXES = ("_id", "_uuid", "_guid", "_pk", "_key")


def _is_surrogate_key(low: str) -> bool:
    return low in _SURROGATE_KEYS or low.endswith(_SURROGATE_SUFFIXES)


def _field_names(schema_fields) -> list[str]:
    """Extract field names from a BaseCampSchema.fields blob (list[dict] or dict)."""
    names: list[str] = []
    if isinstance(schema_fields, list):
        for f in schema_fields:
            if isinstance(f, dict):
                n = f.get("name") or f.get("field") or f.get("key")
                if n:
                    names.append(str(n))
            elif isinstance(f, str):
                names.append(f)
    elif isinstance(schema_fields, dict):
        names.extend(str(k) for k in schema_fields.keys())
    return names


def default_config(schema_fields, *, entity_type: Optional[str] = None) -> ResolutionConfig:
    """Derive a reasonable resolution config from schema fields.

    - exact comparator + exact blocking on id-ish / email fields.
    - jaro_winkler comparator + prefix/soundex blocking on name-ish fields.
    - levenshtein on everything else (lower weight).
    """
    names = _field_names(schema_fields)
    rules: list[FieldRule] = []
    blocking_keys: list[BlockingKey] = []
    survivorship: list[SurvivorshipRule] = []

    for name in names:
        low = name.lower()
        if _is_surrogate_key(low):
            # Surrogate row key — exclude from matching entirely (don't compare or block on it).
            continue
        if any(h in low for h in _ID_HINTS):
            rules.append(FieldRule(field=name, comparator="exact", weight=3.0))
            blocking_keys.append(BlockingKey(field=name, strategy="exact"))
            survivorship.append(SurvivorshipRule(field=name, strategy="most_frequent"))
        elif any(h in low for h in _NAME_HINTS):
            rules.append(FieldRule(field=name, comparator="jaro_winkler", weight=2.0))
            blocking_keys.append(BlockingKey(field=name, strategy="prefix", length=4))
            blocking_keys.append(BlockingKey(field=name, strategy="soundex"))
            survivorship.append(SurvivorshipRule(field=name, strategy="most_complete"))
        else:
            rules.append(FieldRule(field=name, comparator="levenshtein", weight=1.0))
            survivorship.append(SurvivorshipRule(field=name, strategy="most_recent"))

    # Guarantee at least one blocking key so we don't fall back to O(n^2).
    if not blocking_keys and names:
        blocking_keys.append(BlockingKey(field=names[0], strategy="prefix", length=4))
    if not rules:
        # Empty schema: nothing to compare on; leave rules empty (resolve is a no-op).
        pass

    return ResolutionConfig(
        blocking_keys=blocking_keys,
        rules=rules,
        survivorship=survivorship,
        entity_type=entity_type,
    )


class ResolutionService:
    def __init__(self, session, workspace_id):
        self.session = session
        self.workspace_id = str(workspace_id)

    # --- helpers -------------------------------------------------------------

    @staticmethod
    def _derive_source(record: DataRecord) -> Optional[str]:
        meta = record.record_metadata or {}
        if isinstance(meta, dict):
            return meta.get("source_type") or meta.get("source")
        return None

    def _record_to_dict(self, record: DataRecord) -> dict:
        """Project a DataRecord into a flat dict for scoring + survivorship.

        Carries the record id and reserved meta keys (_source/_updated) alongside the
        user data fields.
        """
        data = dict(record.data or {})
        data[RECORD_ID_FIELD] = str(record.id)
        data[SOURCE_FIELD] = self._derive_source(record)
        data[UPDATED_FIELD] = record.updated_at.isoformat() if record.updated_at else None
        return data

    async def _load_schema_fields(self, schema_id: str):
        result = await self.session.execute(
            select(BaseCampSchema).where(
                and_(
                    BaseCampSchema.id == schema_id,
                    BaseCampSchema.workspace_id == self.workspace_id,
                )
            )
        )
        schema = result.scalar_one_or_none()
        return schema.fields if schema else None

    async def _load_records(self, schema_id: str) -> list[DataRecord]:
        result = await self.session.execute(
            select(DataRecord)
            .where(
                and_(
                    DataRecord.workspace_id == self.workspace_id,
                    DataRecord.schema_id == schema_id,
                )
            )
            .order_by(DataRecord.updated_at.asc(), DataRecord.id.asc())
        )
        return list(result.scalars().all())

    # --- main pipeline -------------------------------------------------------

    async def resolve(self, schema_id: str, config: Optional[ResolutionConfig] = None) -> ResolutionResult:
        records = await self._load_records(schema_id)

        if config is None:
            schema_fields = await self._load_schema_fields(schema_id)
            config = default_config(schema_fields or [])

        entity_type = config.entity_type

        dicts = [self._record_to_dict(r) for r in records]
        n = len(dicts)

        if n < 2 or not config.rules:
            return ResolutionResult(
                records=n, pairs_compared=0, clusters=0, merged=0, queued_for_review=0
            )

        # 1. Blocking -> candidate pairs.
        blocks = build_blocks(dicts, config.blocking_keys)
        pairs = candidate_pairs(blocks)

        # 2. Score + classify each candidate pair.
        match_pairs: list[tuple[int, int]] = []
        review_pairs: list[tuple[int, int, float]] = []
        score_config = config.score_config
        for i, j in pairs:
            s = score_pair(dicts[i], dicts[j], config.rules)
            band = classify(s, score_config)
            if band == "match":
                match_pairs.append((i, j))
            elif band == "review":
                review_pairs.append((i, j, s))

        # 3. Transitive closure of MATCH pairs.
        components = cluster_pairs(match_pairs)

        # Build per-pair best score so we can attribute a match_score to each member.
        pair_score: dict[tuple[int, int], float] = {}
        for i, j in match_pairs:
            key = (i, j) if i < j else (j, i)
            pair_score[key] = max(pair_score.get(key, 0.0), score_pair(dicts[i], dicts[j], config.rules))

        merged_records = 0
        clusters_created = 0

        for component in components:
            member_idxs = sorted(component)
            if len(member_idxs) < 2:
                continue  # singletons are not persisted as clusters
            members_data = [dicts[k] for k in member_idxs]

            golden = build_golden(
                members_data,
                config.survivorship,
                source_priority_field=SOURCE_FIELD,
                updated_field=UPDATED_FIELD,
            )

            cluster_row = EntityCluster(
                id=str(uuid4()),
                workspace_id=self.workspace_id,
                schema_id=schema_id,
                entity_type=entity_type,
                canonical=golden,
                member_count=len(member_idxs),
                status="active",
            )
            self.session.add(cluster_row)

            for k in member_idxs:
                # Best score linking this member to anything else in the cluster.
                best = 0.0
                for other in member_idxs:
                    if other == k:
                        continue
                    key = (k, other) if k < other else (other, k)
                    if key in pair_score:
                        best = max(best, pair_score[key])
                self.session.add(
                    ClusterMember(
                        id=str(uuid4()),
                        workspace_id=self.workspace_id,
                        cluster_id=cluster_row.id,
                        record_id=dicts[k][RECORD_ID_FIELD],
                        source=dicts[k].get(SOURCE_FIELD),
                        match_score=best,
                    )
                )

            # 4. Durable lineage row for the cluster (inline; no AuditService).
            #    cluster_row.id is set by our explicit uuid above, so no flush needed.
            self.session.add(
                DataLineage(
                    workspace_id=self.workspace_id,
                    record_id=cluster_row.id,
                    source_type="entity_resolution",
                    source_id=schema_id,
                    transformation="entity_resolution",
                    parent_record_id=None,
                    lineage_metadata={
                        "member_record_ids": [dicts[k][RECORD_ID_FIELD] for k in member_idxs],
                        "member_count": len(member_idxs),
                        "entity_type": entity_type,
                    },
                )
            )

            clusters_created += 1
            merged_records += len(member_idxs)

        # 5. Queue REVIEW-band pairs for human merge approval.
        queued = 0
        for i, j, s in review_pairs:
            await ReviewService.queue_for_review(
                self.session,
                workspace_id=self.workspace_id,
                item_type="entity_merge",
                confidence_score=s,
                data={
                    "schema_id": schema_id,
                    "record_a": {
                        "record_id": dicts[i][RECORD_ID_FIELD],
                        "source": dicts[i].get(SOURCE_FIELD),
                        "data": records[i].data,
                    },
                    "record_b": {
                        "record_id": dicts[j][RECORD_ID_FIELD],
                        "source": dicts[j].get(SOURCE_FIELD),
                        "data": records[j].data,
                    },
                    "score": s,
                },
                record_id=dicts[i][RECORD_ID_FIELD],
                reason=f"Candidate entity merge at score {s:.2f} (review band)",
            )
            queued += 1

        return ResolutionResult(
            records=n,
            pairs_compared=len(pairs),
            clusters=clusters_created,
            merged=merged_records,
            queued_for_review=queued,
        )

    # --- read / manual-override operations -----------------------------------

    async def list_clusters(self, schema_id: Optional[str], limit: int, offset: int) -> list[EntityCluster]:
        conditions = [EntityCluster.workspace_id == self.workspace_id]
        if schema_id:
            conditions.append(EntityCluster.schema_id == schema_id)
        result = await self.session.execute(
            select(EntityCluster)
            .where(and_(*conditions))
            .order_by(EntityCluster.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_cluster(self, cluster_id: str) -> Optional[EntityCluster]:
        result = await self.session.execute(
            select(EntityCluster).where(
                and_(
                    EntityCluster.id == cluster_id,
                    EntityCluster.workspace_id == self.workspace_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_members(self, cluster_id: str) -> list[ClusterMember]:
        result = await self.session.execute(
            select(ClusterMember)
            .where(
                and_(
                    ClusterMember.cluster_id == cluster_id,
                    ClusterMember.workspace_id == self.workspace_id,
                )
            )
            .order_by(ClusterMember.match_score.desc())
        )
        return list(result.scalars().all())

    async def split_cluster(self, cluster_id: str) -> bool:
        """Manual override: dissolve a cluster (delete it + its members)."""
        cluster_row = await self.get_cluster(cluster_id)
        if cluster_row is None:
            return False
        await self.session.delete(cluster_row)  # cascade deletes members
        await self.session.flush()
        return True

    async def manual_merge(
        self, schema_id: str, record_ids: list[str], entity_type: Optional[str] = None
    ) -> EntityCluster:
        """Manual override: force a set of records into a new cluster.

        Loads the named records, builds a golden record with default survivorship, and
        persists a new EntityCluster + members. Records not found in this workspace/schema
        are silently skipped.
        """
        result = await self.session.execute(
            select(DataRecord).where(
                and_(
                    DataRecord.workspace_id == self.workspace_id,
                    DataRecord.schema_id == schema_id,
                    DataRecord.id.in_(record_ids),
                )
            )
        )
        records = list(result.scalars().all())
        members_data = [self._record_to_dict(r) for r in records]

        golden = build_golden(
            members_data,
            [],  # default per-field most_complete
            source_priority_field=SOURCE_FIELD,
            updated_field=UPDATED_FIELD,
        )

        cluster_row = EntityCluster(
            id=str(uuid4()),
            workspace_id=self.workspace_id,
            schema_id=schema_id,
            entity_type=entity_type,
            canonical=golden,
            member_count=len(members_data),
            status="active",
        )
        self.session.add(cluster_row)

        for d in members_data:
            self.session.add(
                ClusterMember(
                    id=str(uuid4()),
                    workspace_id=self.workspace_id,
                    cluster_id=cluster_row.id,
                    record_id=d[RECORD_ID_FIELD],
                    source=d.get(SOURCE_FIELD),
                    match_score=1.0,  # operator-asserted
                )
            )

        self.session.add(
            DataLineage(
                workspace_id=self.workspace_id,
                record_id=cluster_row.id,
                source_type="entity_resolution",
                source_id=schema_id,
                transformation="manual_merge",
                parent_record_id=None,
                lineage_metadata={
                    "member_record_ids": [d[RECORD_ID_FIELD] for d in members_data],
                    "member_count": len(members_data),
                    "manual": True,
                },
            )
        )
        await self.session.flush()
        return cluster_row
