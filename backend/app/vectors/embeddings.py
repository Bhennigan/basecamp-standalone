"""Text embedding generation using lightweight hash-based approach.

For production, consider integrating with:
- OpenAI Embeddings API
- Ollama local embeddings
- Sentence Transformers (requires additional dependencies)
"""
from typing import List, Dict, Any
import hashlib
import os


VECTOR_SIZE = 384  # Standard size for MiniLM-L6-v2 compatibility


class EmbeddingGenerator:
    """Lightweight embedding generator using hash-based vectors.

    This provides consistent vector representations without heavy ML dependencies.
    For semantic search, integrate with an external embedding API.
    """

    def __init__(self):
        self.vector_size = int(os.getenv("VECTOR_SIZE", str(VECTOR_SIZE)))
        self.use_api = os.getenv("EMBEDDING_API_URL", "")

    def _hash_to_vector(self, text: str) -> List[float]:
        """Convert text to a consistent vector using SHA-256 hashing.

        This creates deterministic vectors where similar texts may have
        similar representations based on character n-grams.
        """
        # Generate base hash
        text_bytes = text.lower().encode('utf-8')

        # Create multiple hash variations for the full vector
        vectors = []
        for i in range(self.vector_size // 32 + 1):
            h = hashlib.sha256(text_bytes + str(i).encode()).digest()
            # Convert bytes to floats in range [-1, 1]
            for byte in h:
                vectors.append((byte / 127.5) - 1.0)

        # Truncate to exact size and normalize
        vector = vectors[:self.vector_size]

        # L2 normalize
        magnitude = sum(x*x for x in vector) ** 0.5
        if magnitude > 0:
            vector = [x / magnitude for x in vector]

        return vector

    def generate(self, text: str) -> List[float]:
        """Generate embedding for text."""
        return self._hash_to_vector(text)

    def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch of texts."""
        return [self._hash_to_vector(t) for t in texts]

    def entity_to_text(self, entity: Dict[str, Any]) -> str:
        """Convert entity to text for embedding."""
        parts = [entity.get("type", ""), entity.get("value", "")]
        if entity.get("tags"):
            parts.extend(entity["tags"])
        if entity.get("metadata"):
            parts.append(str(entity["metadata"]))
        return " ".join(str(p) for p in parts if p)
