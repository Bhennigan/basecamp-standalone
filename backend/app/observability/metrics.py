"""Prometheus metrics for Base Camp OS."""

from prometheus_client import Counter, Histogram, Gauge

# Request metrics
request_count = Counter(
    "basecamp_http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"]
)

request_latency = Histogram(
    "basecamp_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

active_connections = Gauge(
    "basecamp_active_connections",
    "Number of active connections"
)

# Entity processing metrics
entities_processed = Counter(
    "basecamp_entities_processed_total",
    "Total number of entities processed",
    ["entity_type", "operation"]
)

# Ingestion job metrics
ingestion_jobs = Counter(
    "basecamp_ingestion_jobs_total",
    "Total number of ingestion jobs",
    ["status", "source_type"]
)

ingestion_job_duration = Histogram(
    "basecamp_ingestion_job_duration_seconds",
    "Duration of ingestion jobs in seconds",
    ["source_type"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0]
)

# Enrichment operation metrics
enrichment_operations = Counter(
    "basecamp_enrichment_operations_total",
    "Total number of enrichment operations",
    ["enrichment_type", "status"]
)

enrichment_duration = Histogram(
    "basecamp_enrichment_duration_seconds",
    "Duration of enrichment operations in seconds",
    ["enrichment_type"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

# Vector operations metrics
vector_operations = Counter(
    "basecamp_vector_operations_total",
    "Total number of vector operations",
    ["operation_type"]
)

# Graph operations metrics
graph_operations = Counter(
    "basecamp_graph_operations_total",
    "Total number of graph operations",
    ["operation_type"]
)

# Database connection pool metrics
db_pool_size = Gauge(
    "basecamp_db_pool_size",
    "Database connection pool size"
)

db_pool_checked_out = Gauge(
    "basecamp_db_pool_checked_out",
    "Number of checked out database connections"
)
