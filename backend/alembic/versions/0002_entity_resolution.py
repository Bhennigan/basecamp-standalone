"""Entity resolution: entity_cluster + cluster_member tables

Revision ID: 0002_entity_resolution
Revises: 0001_envelope_keyhash
Create Date: 2026-06-12

Idempotent (mirrors 0001): each table is created only if absent, so this coexists with
the app's ``Base.metadata.create_all`` bootstrap. On a fresh DB the tables already exist
(the models define them) and creation is skipped; on an upgraded DB they are created.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0002_entity_resolution"
down_revision = "0001_envelope_keyhash"
branch_labels = None
depends_on = None


def _indexes(inspector, table: str) -> set[str]:
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "entity_cluster" not in tables:
        op.create_table(
            "entity_cluster",
            sa.Column("id", UUID(as_uuid=False), primary_key=True),
            sa.Column("workspace_id", UUID(as_uuid=False), nullable=False),
            sa.Column("schema_id", UUID(as_uuid=False), nullable=False),
            sa.Column("entity_type", sa.String(100), nullable=True),
            sa.Column("canonical", JSONB, nullable=False, server_default="{}"),
            sa.Column("member_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("status", sa.String(50), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime, nullable=True),
            sa.Column("updated_at", sa.DateTime, nullable=True),
        )
        op.create_index("ix_entity_cluster_workspace_id", "entity_cluster", ["workspace_id"])
        op.create_index(
            "ix_entity_cluster_ws_schema", "entity_cluster", ["workspace_id", "schema_id"]
        )
    else:
        idx = _indexes(insp, "entity_cluster")
        if "ix_entity_cluster_ws_schema" not in idx:
            op.create_index(
                "ix_entity_cluster_ws_schema", "entity_cluster", ["workspace_id", "schema_id"]
            )

    if "cluster_member" not in tables:
        op.create_table(
            "cluster_member",
            sa.Column("id", UUID(as_uuid=False), primary_key=True),
            sa.Column("workspace_id", UUID(as_uuid=False), nullable=False),
            sa.Column(
                "cluster_id",
                UUID(as_uuid=False),
                sa.ForeignKey("entity_cluster.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("record_id", UUID(as_uuid=False), nullable=False),
            sa.Column("source", sa.String(255), nullable=True),
            sa.Column("match_score", sa.Float, nullable=False, server_default="0"),
            sa.Column("linked_at", sa.DateTime, nullable=True),
        )
        op.create_index("ix_cluster_member_workspace_id", "cluster_member", ["workspace_id"])
        op.create_index("ix_cluster_member_cluster", "cluster_member", ["cluster_id"])
        op.create_index(
            "ix_cluster_member_record", "cluster_member", ["workspace_id", "record_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "cluster_member" in tables:
        op.drop_table("cluster_member")
    if "entity_cluster" in tables:
        op.drop_table("entity_cluster")
