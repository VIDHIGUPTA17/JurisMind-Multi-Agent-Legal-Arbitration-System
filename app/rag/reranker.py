"""
Cross-encoder reranker using ms-marco-MiniLM-L-6-v2.
Reranks cosine-similarity candidates with query-aware scoring.
"""
from __future__ import annotations

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
        except Exception as e:
            raise RuntimeError(f"Failed to load reranker model: {e}") from e
    return _reranker


class Reranker:
    """
    Cross-encoder reranker.
    Takes (query, chunk_text) pairs and scores relevance 0-1.
    Much more accurate than cosine similarity but too slow for first-pass retrieval.
    """

    def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_k: int = 10,
    ) -> list[dict]:
        """
        Input:  candidate chunks from cosine similarity (each dict has 'chunk_text')
        Output: top_k chunks re-scored by cross-encoder, sorted descending

        Falls back to cosine similarity ordering if reranker unavailable.
        """
        if not chunks:
            return []

        try:
            model = _get_reranker()
            pairs = [(query, c.get("chunk_text", "")) for c in chunks]
            scores = model.predict(pairs)
            for chunk, score in zip(chunks, scores):
                chunk["rerank_score"] = float(score)
            chunks_sorted = sorted(chunks, key=lambda x: x.get("rerank_score", 0), reverse=True)
            return chunks_sorted[:top_k]
        except Exception:
            # Graceful fallback: return top_k by cosine similarity
            return chunks[:top_k]
