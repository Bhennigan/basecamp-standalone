"""Base Camp OS - Standalone Data Fusion Platform"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.basecamp.ingestion.router import router as ingestion_router
from app.basecamp.schema.router import router as schema_router
from app.basecamp.storage.router import router as storage_router
from app.basecamp.integration.router import router as integration_router
from app.tracecat.router import router as tracecat_router
from app.enrichment.router import router as enrichment_router
from app.vectors.router import router as vectors_router
from app.graph.router import router as graph_router
from app.connectors.router import router as connectors_router
from app.events.router import router as events_router
from app.compliance.router import router as compliance_router
from app.review.router import router as review_router
from app.storage.router_minio import router as minio_router
from app.compliance.middleware import AuditMiddleware
from app.db.database import engine
from app.db.models import Base

# Service clients
from app.storage.minio_client import get_minio_client
from app.events.nats_client import NATSClient, get_nats_client
from app.vectors.qdrant_client import VectorClient
from app.graph.neo4j_client import Neo4jClient, close_neo4j_client
from app.connectors.manager import get_connector_manager
from app.connectors.base import ConnectorConfig

# Observability imports
from app.observability import (
    MetricsMiddleware,
    LoggingMiddleware,
    metrics_router,
    setup_logging,
    get_logger,
)

# Setup structured logging
setup_logging(level="INFO")
logger = get_logger(__name__)

# Module-level references for graceful shutdown
_nats_client: NATSClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all services on startup, shut down on exit."""
    global _nats_client

    logger.info("Starting Base Camp OS")

    # --- Database ---
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")

    # --- MinIO ---
    try:
        minio = get_minio_client()
        await minio.ensure_buckets()
        logger.info("MinIO buckets ensured (raw, enriched, reports, audit)")
    except Exception as e:
        logger.warning("MinIO initialization failed — file storage unavailable", error=str(e))

    # --- NATS ---
    try:
        _nats_client = NATSClient()
        await _nats_client.connect()
        logger.info("NATS connected, JetStream stream ensured")
    except Exception as e:
        _nats_client = None
        logger.warning("NATS initialization failed — event publishing unavailable", error=str(e))

    # --- Qdrant ---
    try:
        qdrant = VectorClient()
        await qdrant.ensure_collection()
        logger.info("Qdrant collection ensured (entities)")
    except Exception as e:
        logger.warning("Qdrant initialization failed — vector search unavailable", error=str(e))

    # --- Neo4j ---
    try:
        neo4j = Neo4jClient()
        await neo4j.connect()
        logger.info("Neo4j connected")
    except Exception as e:
        logger.warning("Neo4j initialization failed — graph operations unavailable", error=str(e))

    # --- Connectors (auto-register from env vars) ---
    try:
        manager = get_connector_manager()
        netcraft_key = os.environ.get("NETCRAFT_API_KEY")
        if netcraft_key:
            netcraft_brand = os.environ.get("NETCRAFT_BRAND", "")
            manager.register_connector(ConnectorConfig(
                name="netcraft",
                connector_type="netcraft",
                api_key=netcraft_key,
                config={"brand": netcraft_brand},
            ))
            logger.info(f"Netcraft connector auto-registered | brand={netcraft_brand}")
    except Exception as e:
        logger.warning(f"Connector auto-registration failed: {e}")

    logger.info("Base Camp OS startup complete")
    yield

    # --- Shutdown ---
    logger.info("Shutting down Base Camp OS")
    if _nats_client and _nats_client.is_connected:
        try:
            await _nats_client.disconnect()
            logger.info("NATS disconnected")
        except Exception as e:
            logger.warning("Error disconnecting NATS", error=str(e))
    try:
        await close_neo4j_client()
        logger.info("Neo4j disconnected")
    except Exception as e:
        logger.warning("Error disconnecting Neo4j", error=str(e))


app = FastAPI(
    title="Base Camp OS",
    description="Standalone Data Fusion Platform with Tracecat Integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Observability middleware (order matters - metrics first, then logging)
app.add_middleware(LoggingMiddleware)
app.add_middleware(MetricsMiddleware)

# Audit middleware for compliance logging
app.add_middleware(AuditMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "basecamp-os"}

# Metrics endpoint (mounted at root for Prometheus scraping)
app.include_router(metrics_router)

# Base Camp routers
app.include_router(ingestion_router, prefix="/api/basecamp/ingest", tags=["Ingestion"])
app.include_router(schema_router, prefix="/api/basecamp/schemas", tags=["Schemas"])
app.include_router(storage_router, prefix="/api/basecamp/data", tags=["Data"])
app.include_router(integration_router, prefix="/api/basecamp/tracecat", tags=["Tracecat Integration"])

# Tracecat direct API router
app.include_router(tracecat_router, prefix="/api/tracecat", tags=["Tracecat"])

# Entity enrichment router
app.include_router(enrichment_router, prefix="/api/enrichment", tags=["Entity Enrichment"])

# Vector operations router
app.include_router(vectors_router, prefix="/api/vectors", tags=["Vector Operations"])

# Graph operations router
app.include_router(graph_router, prefix="/api/graph", tags=["Graph Operations"])

# OSINT Connectors router
app.include_router(connectors_router, tags=["OSINT Connectors"])

# NATS Events router
app.include_router(events_router, prefix="/api/events", tags=["Events"])

# Human-in-the-loop Review router
app.include_router(review_router, prefix="/api/review", tags=["Review Queue"])

# MinIO storage router
app.include_router(minio_router, prefix="/api/storage", tags=["Object Storage"])

# Compliance and audit router
app.include_router(compliance_router, tags=["Compliance"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
