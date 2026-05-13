"""
Enhanced RAG retriever with:
- Minimum similarity threshold (0.35)
- Multi-query expansion
- Cross-encoder reranking
- Citation metadata attachment
"""
from __future__ import annotations
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import DocumentChunk
from app.rag.embeddings import get_query_embedding, cosine_similarity
from app.rag.query_expander import QueryExpander
from app.rag.reranker import Reranker

_query_expander = QueryExpander()
_reranker = Reranker()

MIN_SIMILARITY_THRESHOLD = 0.35


async def retrieve_relevant_chunks(
    query: str,
    case_id: str,
    session: AsyncSession,
    top_k: int = 10,
    min_similarity: float = MIN_SIMILARITY_THRESHOLD,
    use_reranker: bool = True,
) -> list[dict]:
    """
    Enhanced retrieval pipeline:
    1. Expand query → multiple sub-queries
    2. Embed each sub-query (with query instruction prefix)
    3. Load case chunks from DB
    4. Score each chunk against each query embedding (cosine)
    5. Deduplicate by chunk_id, keep max similarity
    6. Filter by min_similarity threshold
    7. Rerank with cross-encoder → top_k final results
    8. Attach citation metadata
    """
    # Step 1: Query expansion
    expanded_queries = _query_expander.expand(query, use_llm=False)

    # Step 2: Get embeddings for all expanded queries
    query_embeddings = [get_query_embedding(q) for q in expanded_queries]

    # Step 3: Load all chunks for this case from DB
    result = await session.execute(
        select(DocumentChunk).where(DocumentChunk.case_id == case_id)
    )
    chunks = result.scalars().all()

    if not chunks:
        return []

    # Step 4: Score each chunk against each query embedding
    chunk_scores: dict[str, float] = {}  # chunk_id → best similarity score
    chunk_data: dict[str, dict] = {}

    for chunk in chunks:
        if not chunk.embedding:
            continue
        chunk_vec = chunk.embedding
        best_sim = 0.0
        for q_emb in query_embeddings:
            sim = cosine_similarity(q_emb, chunk_vec)
            if sim > best_sim:
                best_sim = sim
        chunk_scores[str(chunk.id)] = best_sim
        chunk_data[str(chunk.id)] = {
            "chunk_id": str(chunk.id),
            "chunk_text": chunk.chunk_text,
            "chunk_index": chunk.chunk_index,
            "document_id": str(chunk.document_id),
            "document_filename": getattr(chunk, "document_filename", ""),
            "page_numbers": getattr(chunk, "page_numbers", [1]),
            "section_header": getattr(chunk, "section_header", None),
            "chunk_type": getattr(chunk, "chunk_type", "paragraph"),
            "similarity": best_sim,
            "rerank_score": 0.0,
        }

    # Step 5: Filter by minimum similarity threshold
    filtered = [
        chunk_data[cid]
        for cid, score in chunk_scores.items()
        if score >= min_similarity
    ]

    if not filtered:
        # Relax threshold if nothing passes
        filtered = [
            chunk_data[cid]
            for cid, score in sorted(chunk_scores.items(), key=lambda x: -x[1])[:top_k]
        ]

    # Sort by cosine similarity descending (pre-reranking)
    filtered.sort(key=lambda x: x["similarity"], reverse=True)

    # Cap at top 50 candidates for reranker
    candidates = filtered[:50]

    # Step 6: Rerank
    if use_reranker and len(candidates) > top_k:
        try:
            candidates = _reranker.rerank(query, candidates, top_k=top_k)
        except Exception:
            candidates = candidates[:top_k]
    else:
        candidates = candidates[:top_k]

    return candidates
