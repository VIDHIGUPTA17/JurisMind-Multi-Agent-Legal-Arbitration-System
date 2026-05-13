# AGENTS.md — app/rag/

## Purpose
The Retrieval-Augmented Generation (RAG) pipeline. Converts natural language queries into grounded evidence retrieval from the document database. Prevents hallucination by giving agents access to actual document text with full citation metadata.

## Files

### `embeddings.py`
Manages the sentence-transformer embedding model.

**Model:** `BAAI/bge-base-en-v1.5` (768-dimensional, instruction-tuned for retrieval)

**Functions:**
| Function | Description |
|---|---|
| `get_model()` | Lazy-loads the BGE model (singleton). Downloads ~438 MB on first call. |
| `get_embedding(text)` | Embed any text → 768-dim normalized float list |
| `get_embeddings(texts)` | Batch embed a list of texts (batch_size=32) |
| `get_query_embedding(query)` | Embed a **query** with instruction prefix (improves BGE retrieval accuracy) |
| `get_document_embedding(text)` | Embed a **document chunk** without prefix |
| `cosine_similarity(a, b)` | Cosine similarity between two float lists |

**Instruction prefix (query only):**
```
"Represent this legal query for retrieving relevant evidence: {query}"
```
BGE models are instruction-tuned — adding this prefix to queries (but NOT documents) significantly improves retrieval precision.

**Previous model:** `all-MiniLM-L6-v2` (384-dim, general-purpose) — replaced because it has poor embeddings for legal terminology.

**Warning:** First call to `get_model()` will block for ~30–60 seconds while downloading the model. Warm it at startup in `main.py` lifespan.

### `query_expander.py`
Expands a single legal query into multiple search angles to improve recall.

**Class: `QueryExpander`**

Method: `expand(query, use_llm=False) → list[str]` (capped at 5 queries)

**Expansion strategy:**
1. Original query (always included)
2. Static synonym substitution from `_LEGAL_SYNONYMS` dict:
   - `breach` → `violation`, `non-compliance`, `failure to perform`
   - `contract` → `agreement`, `deed`, `undertaking`
   - `damages` → `compensation`, `relief`, `indemnity`
   - (and 7 more legal term mappings)
3. Statute reference expansion via `_STATUTE_MAP`:
   - `"breach of contract"` → adds `"Section 73 Indian Contract Act 1872"`
   - `"negligence"` → adds `"Law of Torts"`
4. Optional LLM expansion (Groq call, `use_llm=True`) — generates 2–3 alternative phrasings

**Why query expansion matters:** Legal documents use varied terminology. "Breach" and "non-compliance" mean the same thing but have different vector representations. Expanding queries catches all relevant evidence.

### `retriever.py`
The main retrieval function — the 5-layer RAG pipeline.

**Function: `retrieve_relevant_chunks(query, case_id, session, top_k=10, min_similarity=0.35, use_reranker=True)`**

**Pipeline:**
```
Query
  │
  ▼
QueryExpander.expand()          → up to 5 expanded queries
  │
  ▼
get_query_embedding() × N       → 768-dim vectors per query
  │
  ▼
SELECT * FROM document_chunks   → load all chunks for this case
WHERE case_id = ?
  │
  ▼
cosine_similarity() per chunk   → score each chunk against each query
  │  (take max score across all expanded queries)
  ▼
Filter: similarity >= 0.35      → discard irrelevant chunks
  │  (if nothing passes, take top_k by best similarity)
  ▼
Sort descending, cap at 50      → pre-reranking candidates
  │
  ▼
Reranker.rerank(query, chunks)  → cross-encoder rescores all pairs
  │
  ▼
top_k chunks with metadata      → returned as list[dict]
```

**Output dict per chunk:**
```python
{
    "chunk_id": str,
    "chunk_text": str,           # anonymized text
    "chunk_index": int,
    "document_id": str,
    "document_filename": str,    # for citations
    "page_numbers": list[int],
    "section_header": str | None, # "Clause 4.2: Termination"
    "chunk_type": str,           # paragraph | clause | table | header
    "similarity": float,         # cosine similarity score
    "rerank_score": float,       # cross-encoder score (higher = more relevant)
}
```

**Minimum similarity threshold (0.35):**
- Without a threshold, the top-10 results could include chunks with 0.1 similarity (noise)
- The judge would hallucinate connections from irrelevant text
- If nothing passes 0.35, the threshold is relaxed automatically

### `reranker.py`
Cross-encoder reranking of cosine-similarity candidates.

**Model:** `cross-encoder/ms-marco-MiniLM-L-6-v2`

**Class: `Reranker`**

Method: `rerank(query, chunks, top_k=10) → list[dict]`

**How it differs from cosine similarity:**
- Cosine similarity compares **independent** query and chunk embeddings
- Cross-encoder sees query and chunk **together** in the same transformer pass
- This means it understands context, negation, and relevance nuances
- Example: cosine similarity thinks "The contract was NOT breached" ≈ "The contract was breached" (high word overlap). Cross-encoder understands the negation.

**Performance trade-off:**
- Too slow for first-pass retrieval (must run N×M pairs, where N=queries, M=all chunks)
- Fast enough for reranking 50 candidates → 10 final results

**Fallback:** If the model fails to load or an exception occurs during prediction, falls back to cosine-similarity ordering (top_k from the input).

### `citation_tracker.py`
Tracks which document chunks were used in reasoning and verifies the final verdict is grounded in actual evidence.

**Dataclasses:**
- `Citation` — metadata about one retrieved chunk (document, page, section, scores, text snippet)
- `GroundingReport` — result of verification (scores each verdict claim as GROUNDED/UNGROUNDED/CONTRADICTED)

**Class: `CitationTracker`**

Methods:
| Method | Description |
|---|---|
| `build_citations(retrieved_chunks)` | Convert chunk dicts → `list[Citation]` |
| `verify_grounding(verdict_json, retrieved_chunks)` | LLM-based grounding verification |

**Grounding verification process:**
1. Extract factual claims from the verdict JSON (reasoning + verdict text)
2. For each claim, check if any retrieved chunk supports it
3. Classify each claim: `GROUNDED | UNGROUNDED | CONTRADICTED`
4. Calculate `overall_score = grounded_count / total_claims`
5. `passed = overall_score >= 0.6`

**Why this matters:** Without grounding verification, the judge agent could state "The contract was signed on March 5" even if no document mentions that date. The grounding check flags this as `UNGROUNDED` and reduces the confidence score.

## RAG Pipeline Summary (5 Layers)

```
Layer 1: QUERY EXPANSION
  "breach of contract" → ["breach of contract", "contractual violation",
                          "failure to perform obligations", "Section 73 ICA 1872"]

Layer 2: SEMANTIC RETRIEVAL
  BGE-base (768-dim) embeddings
  Cosine similarity against all case chunks
  Filter: similarity ≥ 0.35
  → ~40 candidates

Layer 3: CROSS-ENCODER RERANKING
  ms-marco-MiniLM cross-encoder
  Scores (query, chunk) pairs with full context
  → Top 10 by rerank_score

Layer 4: CITATION ATTACHMENT
  Each chunk gets: {doc_id, filename, page, section, similarity, rerank_score}
  → Structured evidence passed to agents

Layer 5: GROUNDING VERIFICATION (post-verdict)
  ChiefJudge verdict → extract factual claims
  Match each claim to cited evidence
  → GroundingReport {score, grounded[], ungrounded[], contradicted[]}
```

## Dependencies

- `sentence-transformers>=3.3.0` — both BGE embedding model and CrossEncoder reranker
- `numpy` — cosine similarity computation
- `groq` — for LLM-based query expansion (optional) and grounding verification
