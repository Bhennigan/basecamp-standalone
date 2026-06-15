"""Add record envelope (metadata + quality) and hash consumer API keys

Revision ID: 0001_envelope_keyhash
Revises:
Create Date: 2026-06-12

This migration is written to be idempotent so it can coexist with the app's
``Base.metadata.create_all`` bootstrap: on a fresh database the columns already exist (the
models define them) and each step is skipped; on a pre-existing database the columns are
added and any plaintext consumer API keys are migrated to sha256 hashes in place.
"""
from __future__ import annotations

import hashlib

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_envelope_keyhash"
down_revision = None
branch_labels = None
depends_on = None


def _columns(inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def _indexes(inspector, table: str) -> set[str]:
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    # --- data_record: canonical envelope columns + feed index ---
    if "data_record" in tables:
        dr_cols = _columns(insp, "data_record")
        if "record_metadata" not in dr_cols:
            op.add_column(
                "data_record",
                sa.Column("record_metadata", JSONB, nullable=False, server_default="{}"),
            )
        if "quality" not in dr_cols:
            op.add_column(
                "data_record",
                sa.Column("quality", JSONB, nullable=False, server_default="{}"),
            )
        if "ix_data_record_feed" not in _indexes(insp, "data_record"):
            op.create_index(
                "ix_data_record_feed",
                "data_record",
                ["workspace_id", "updated_at", "id"],
            )

    # --- consumer: replace plaintext api_key with api_key_hash + api_key_prefix ---
    if "consumer" in tables:
        c_cols = _columns(insp, "consumer")
        if "api_key_hash" not in c_cols:
            op.add_column("consumer", sa.Column("api_key_hash", sa.String(64), nullable=True))
        if "api_key_prefix" not in c_cols:
            op.add_column(
                "consumer",
                sa.Column("api_key_prefix", sa.String(16), nullable=False, server_default=""),
            )

        # Backfill hashes from any existing plaintext keys (Python-side, no pgcrypto needed).
        if "api_key" in c_cols:
            rows = bind.execute(
                sa.text("SELECT id, api_key FROM consumer WHERE api_key IS NOT NULL")
            ).fetchall()
            for row in rows:
                raw = row[1]
                digest = hashlib.sha256(raw.encode()).hexdigest()
                bind.execute(
                    sa.text(
                        "UPDATE consumer SET api_key_hash = :h, api_key_prefix = :p WHERE id = :i"
                    ),
                    {"h": digest, "p": raw[:8], "i": row[0]},
                )
            op.drop_column("consumer", "api_key")

        # Enforce the hash constraints now that data is backfilled.
        if "ix_consumer_api_key_hash" not in _indexes(insp, "consumer"):
            op.create_index(
                "ix_consumer_api_key_hash", "consumer", ["api_key_hash"], unique=True
            )
        try:
            op.alter_column("consumer", "api_key_hash", nullable=False)
        except Exception:
            # Leave nullable if legacy rows can't satisfy NOT NULL; ORM enforces it on writes.
            pass


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "consumer" in tables:
        c_cols = _columns(insp, "consumer")
        if "api_key" not in c_cols:
            op.add_column("consumer", sa.Column("api_key", sa.String(255), nullable=True))
        if "ix_consumer_api_key_hash" in _indexes(insp, "consumer"):
            op.drop_index("ix_consumer_api_key_hash", table_name="consumer")
        for col in ("api_key_hash", "api_key_prefix"):
            if col in _columns(insp, "consumer"):
                op.drop_column("consumer", col)

    if "data_record" in tables:
        if "ix_data_record_feed" in _indexes(insp, "data_record"):
            op.drop_index("ix_data_record_feed", table_name="data_record")
        for col in ("record_metadata", "quality"):
            if col in _columns(insp, "data_record"):
                op.drop_column("data_record", col)
