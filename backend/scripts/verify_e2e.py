"""End-to-end smoke test for the Base Camp hardening waves.

Exercises the DB-backed paths that unit tests can't cover (they need real Postgres/JSONB):
  1. Envelope + quality persistence through DataRecordService.create_record
  2. Consumer change-feed keyset on (updated_at, id) — no skips, and updated rows re-emerge
  3. Entity resolution clustering over duplicate-laden records

Run it once Postgres is up:

    docker compose up -d postgres
    cd backend
    set DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/basecamp   # Windows
    python -m alembic upgrade head        # or rely on create_all below for a fresh DB
    python scripts/verify_e2e.py

Exits non-zero on the first failed check.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, tuple_, and_
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Make `app` importable when run as `python scripts/verify_e2e.py` from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.models import Base, BaseCampSchema, DataRecord  # noqa: E402
from app.basecamp.storage.service import DataRecordService  # noqa: E402
from app.basecamp.schemas import DataRecordCreate  # noqa: E402
from app.resolution.service import ResolutionService  # noqa: E402
from app.auth.types import Role  # noqa: E402

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/basecamp")

_passed = 0
_failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global _passed, _failed
    mark = "PASS" if ok else "FAIL"
    if ok:
        _passed += 1
    else:
        _failed += 1
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))


async def main() -> int:
    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ws = uuid.uuid4()
    role = Role(user_id=None, workspace_id=ws, service_id="verify-e2e", is_service=True)
    schema_fields = [
        {"name": "id", "field_type": "str", "nullable": False},
        {"name": "name", "field_type": "str", "nullable": False},
        {"name": "email", "field_type": "str", "nullable": True},
    ]

    async with Session() as session:
        # --- setup: a schema ---
        schema = BaseCampSchema(workspace_id=str(ws), name="person", fields=schema_fields)
        session.add(schema)
        await session.flush()
        schema_id = schema.id

        # === Check 1: envelope + quality persisted via the real service ===
        svc = DataRecordService(session, role)
        await svc.create_record(DataRecordCreate(schema_id=uuid.UUID(schema_id), data={
            "id": "1", "name": "Alice Smith", "email": "alice@example.com"}))
        await session.flush()
        row = (await session.execute(
            select(DataRecord).where(DataRecord.schema_id == schema_id))).scalars().first()
        check("envelope record_metadata populated", bool(row.record_metadata), str(row.record_metadata))
        check("quality scored", isinstance(row.quality, dict) and "score" in (row.quality or {}),
              str(row.quality))
        await session.commit()

        # === Check 2: change-feed keyset (no skips + updates re-emerge) ===
        # Insert several records sharing a timestamp to stress the (updated_at, id) keyset.
        base_records = []
        for i in range(5):
            r = DataRecord(workspace_id=str(ws), schema_id=schema_id,
                           data={"id": str(100 + i), "name": f"P{i}"})
            session.add(r)
            base_records.append(r)
        await session.commit()

        async def feed_page(cursor, limit=2):
            conds = [DataRecord.workspace_id == str(ws), DataRecord.schema_id == schema_id]
            if cursor is not None:
                conds.append(tuple_(DataRecord.updated_at, DataRecord.id) > cursor)
            stmt = (select(DataRecord).where(and_(*conds))
                    .order_by(DataRecord.updated_at.asc(), DataRecord.id.asc()).limit(limit))
            rows = (await session.execute(stmt)).scalars().all()
            nxt = (rows[-1].updated_at, rows[-1].id) if rows else cursor
            return rows, nxt

        seen, cursor = [], None
        for _ in range(20):
            rows, cursor = await feed_page(cursor)
            if not rows:
                break
            seen.extend(r.id for r in rows)
        # 5 base + 1 from check-1 = 6 distinct, none skipped
        check("feed returns all records without skips", len(set(seen)) == len(seen) and len(seen) >= 6,
              f"{len(seen)} ids, {len(set(seen))} unique")

        # Update one record → its updated_at advances → it must re-appear past an old cursor.
        target = base_records[0]
        old_cursor = (target.updated_at, target.id)
        target.data = {**target.data, "name": "P0-updated"}
        target.updated_at = datetime.utcnow() + timedelta(seconds=1)
        await session.commit()
        rows_after, _ = await feed_page(old_cursor, limit=50)
        check("updated record re-emerges in feed", any(r.id == target.id for r in rows_after))

        # === Check 3: entity resolution clusters duplicates ===
        dupes = [
            {"id": "d1", "name": "Jonathan Doe", "email": "jdoe@acme.com"},
            {"id": "d2", "name": "Jon Doe", "email": "jdoe@acme.com"},      # same email
            {"id": "d3", "name": "Jonathan Doe", "email": "j.doe@acme.com"},  # same name
            {"id": "d4", "name": "Maria Garcia", "email": "mg@globex.com"},   # distinct
        ]
        for d in dupes:
            session.add(DataRecord(workspace_id=str(ws), schema_id=schema_id, data=d,
                                   record_metadata={"source_type": "file_ingestion"}))
        await session.commit()

        rsvc = ResolutionService(session, ws)
        result = await rsvc.resolve(schema_id)
        await session.commit()
        rd = result.as_dict() if hasattr(result, "as_dict") else result.__dict__
        check("resolution produced at least one cluster", rd.get("clusters", 0) >= 1, str(rd))
        check("resolution compared candidate pairs", rd.get("pairs_compared", 0) >= 1, str(rd))

    await engine.dispose()

    print(f"\n{_passed} passed, {_failed} failed")
    return 1 if _failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
