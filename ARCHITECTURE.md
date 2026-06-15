# Base Camp — Architecture Decisions & Contracts

This document records load-bearing decisions so they aren't re-litigated per change.

## Canonical codebase

`basecamp-standalone` (this repo) is the **canonical** Base Camp implementation. The
Tracecat-embedded "Base Camp OS" module (described historically in `Oracle/basecamp.md`) is a
deployment adapter, not a separate source of truth. New capability lands here first; any
Tracecat integration consumes this codebase's contracts rather than forking them.

## Distribution contract

Base Camp exposes normalized data through four mechanisms with distinct, non-overlapping roles:

| Mechanism | Role | Surface |
|-----------|------|---------|
| **Change feed** | Canonical **pull**. Downstream engines poll for deltas. | `consumers/router.py` `/{id}/feed`, `consumers/external_router.py` `/feed` |
| **Webhooks** | Canonical **push**. Base Camp POSTs new records to a consumer's `callback_url`. | `consumers/webhooks.py` |
| **External API** | Auth wrapper over the change feed for off-platform consumers (Bearer API key → consumer/workspace). | `consumers/external_router.py` |
| **NATS events** | Internal eventing / fan-out between services. | `events/` |

### Change-feed semantics
The feed paginates with a **composite keyset on `(updated_at, id)`** (not `created_at`). This
gives a total ordering — eliminating same-timestamp skips — and, because `updated_at` advances
on update, **updated records re-appear in the feed**. The feed therefore has **at-least-once
update semantics**: consumers should treat `id` as the idempotency key and upsert.

## Record envelope

Every `DataRecord` carries, alongside `data`:
- `record_metadata` (JSONB) — inline lineage: source row/sheet/file, job id, source type,
  applied transform names. The durable, queryable lineage graph lives in the `compliance`
  module's `DataLineage` table (populated via `AuditService.track_lineage()`).
- `quality` (JSONB) — per-record quality scores (completeness / validity / consistency /
  timeliness) computed at ingest by `app/quality/`.

## API key handling

Consumer API keys are **never stored in plaintext**. The DB holds `api_key_hash` (sha256, for
lookup) and `api_key_prefix` (short, non-secret, for display). The raw token is returned **once**
at creation and never again. Auth resolves a presented key by hashing it and matching the hash.

## Migrations

Schema changes go through **Alembic** (`backend/alembic/`). `Base.metadata.create_all` still
runs at startup to bootstrap tables for modules not yet under migration control; Alembic
migrations are written to be idempotent so the two coexist. Apply with `alembic upgrade head`
(run with a sync psycopg URL, resolved automatically from `DATABASE_URL` in `alembic/env.py`).
