"""Base Camp OS - Standalone Data Fusion Platform"""
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
from app.compliance.middleware import AuditMiddleware
from app.db.database import engine
from app.db.models import Base

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    logger.info("Starting Base Camp OS")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")
    yield
    logger.info("Shutting down Base Camp OS")


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

# Compliance and audit router
app.include_router(compliance_router, tags=["Compliance"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
