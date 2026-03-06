"""Base Camp OS - Standalone Data Normalization Platform"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.basecamp.ingestion.router import router as ingestion_router
from app.basecamp.schema.router import router as schema_router
from app.basecamp.storage.router import router as storage_router
from app.basecamp.integration.router import router as integration_router
from app.transform.router import router as transform_router
from app.consumers.router import router as consumers_router
from app.consumers.external_router import router as external_router
from app.db.database import engine
from app.db.models import Base

import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    logger.info("Starting Base Camp OS")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

    logger.info("Base Camp OS startup complete")
    yield
    logger.info("Base Camp OS shutting down")


app = FastAPI(
    title="Base Camp OS",
    description="Data Normalization & Transformation Platform",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "basecamp-os"}


# Core Base Camp routers
app.include_router(ingestion_router, prefix="/api/basecamp/ingest", tags=["Ingestion"])
app.include_router(schema_router, prefix="/api/basecamp/schemas", tags=["Schemas"])
app.include_router(storage_router, prefix="/api/basecamp/data", tags=["Data"])
app.include_router(integration_router, prefix="/api/basecamp/tracecat", tags=["Tracecat Integration"])

# Transformation pipeline
app.include_router(transform_router, prefix="/api/basecamp/transform", tags=["Transform"])

# Consumer output API
app.include_router(consumers_router, prefix="/api/basecamp/consumers", tags=["Consumers"])

# External API (API key auth — no workspace headers needed)
app.include_router(external_router, prefix="/api/v1", tags=["External API"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
