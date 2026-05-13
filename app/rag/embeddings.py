"""
Embedding service using BAAI/bge-base-en-v1.5 (768-dim, instruction-tuned).
Better retrieval quality than all-MiniLM-L6-v2 for legal text.
"""
from __future__ import annotations
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

# Instruction prefix improves retrieval for BGE models
QUERY_PREFIX = "Represent this legal query for retrieving relevant evidence: "

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_embedding(text: str) -> list[float]:
    model = get_model()
    vec = model.encode([text], normalize_embeddings=True)[0]
    return vec.tolist()


def get_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_model()
    vecs = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    return [v.tolist() for v in vecs]


def get_query_embedding(query: str) -> list[float]:
    """Embed a search query with instruction prefix (improves BGE retrieval)."""
    return get_embedding(QUERY_PREFIX + query)


def get_document_embedding(text: str) -> list[float]:
    """Embed a document chunk (no prefix)."""
    return get_embedding(text)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
