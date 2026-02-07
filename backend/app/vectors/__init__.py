"""Vector operations module for Base Camp OS"""
from .qdrant_client import VectorClient
from .embeddings import EmbeddingGenerator

__all__ = ["VectorClient", "EmbeddingGenerator"]
