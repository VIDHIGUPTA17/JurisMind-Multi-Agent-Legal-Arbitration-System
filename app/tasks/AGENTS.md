# AGENTS.md — app/tasks/

## Purpose
Background task definitions. Handles long-running operations that should not block HTTP responses. Currently uses FastAPI's built-in `BackgroundTasks` (no Redis or Celery required).

## Files

### `document_tasks.py`

The main document processing pipeline. Triggered after a PDF is uploaded.

**Function: `process_document(document_id: str) → None`**

**Full pipeline (11 steps):**

```
Step 1  Fetch Document row from DB
Step 2  Set status → PROCESSING, commit
Step 3  decrypt_bytes(doc.content_encrypted) → raw PDF bytes
Step 4  extract_text_from_pdf(pdf_bytes) → full text string
Step 5  semantic_chunk(text, document_id, max_tokens=512) → list[SemanticChunk]
Step 6  anonymize(extracted_text) → PIIResult (anonymized_text, token_map, audit)
Step 7  doc.content_anonymized = pii_result.anonymized_text
Step 8  For each token in pii_result.token_map:
          Create PIIMapping(token, encrypted_value=encrypt(original_value))
Step 9  For each entity_type in pii_result.audit:
          Create PIIAuditLog(entity_type, count_found)
Step 10 For each SemanticChunk:
          anonymize(chunk.text) → anonymized_chunk_text
          get_document_embedding(anonymized_chunk_text) → 768-dim vector
          Create DocumentChunk(chunk_text, embedding, section_header,
                               chunk_type, token_count, page_numbers, document_filename)
Step 11 doc.processing_status = DONE, doc.processed_at = now()
        Commit all in one transaction
```

**Error handling:**
- Any exception → sets `doc.processing_status = FAILED`, `doc.error_message = str(exc)[:500]`
- Uses a fresh `AsyncSessionLocal()` session (not passed from the HTTP request)
- Logs all steps via `logging.getLogger(__name__)`

**Key imports:**
```python
from app.core.security import encrypt, decrypt_bytes
from app.core.pdf_parser import extract_text_from_pdf
from app.core.chunker import semantic_chunk
from app.core.pii_processor import anonymize
from app.rag.embeddings import get_document_embedding
```

**Why a fresh session?**
FastAPI's `BackgroundTasks` run after the HTTP response is sent. The original request's DB session may already be closed. Using `AsyncSessionLocal()` gives the task its own independent session.

### `celery_app.py`

Placeholder file — Celery was removed from the architecture in favor of FastAPI's `BackgroundTasks`. This file exists for compatibility and imports nothing significant.

## How Tasks Are Dispatched

In `app/routers/documents.py`:
```python
from fastapi import BackgroundTasks
from app.tasks.document_tasks import process_document

@router.post("/{case_id}/documents")
async def upload_document(background_tasks: BackgroundTasks, ...):
    # ... save document ...
    background_tasks.add_task(process_document, doc.id)
    return response  # sent immediately; task runs after
```

The HTTP response returns immediately with `PENDING` status. The frontend polls `GET /cases/{id}/documents` every 5 seconds to check when status changes to `DONE`.

## Performance Notes

| Step | Time estimate | Notes |
|---|---|---|
| PDF decryption | <10ms | Fernet is fast |
| Text extraction | 100–2000ms | Depends on PDF size |
| Semantic chunking | <50ms | Pure Python, no model |
| PII anonymization | 500–2000ms | Presidio NLP model |
| Embedding (per chunk) | 20–100ms | BGE-base-en-v1.5 on CPU |
| **Total for 10-page doc** | **~5–15 seconds** | Depends on CPU |

**Note:** For a 50-page document with 100 chunks, embedding each chunk individually is slow. Future optimization: batch embed all chunks with `get_embeddings(texts)` in one call instead of calling `get_document_embedding()` per chunk.

## Known Issues

1. **PII field mismatch risk:** `PIIMapping` schema must match actual column names (`token`, `encrypted_value`). Verify against `app/models/pii_mapping.py` before running.

2. **`doc.filename` vs `doc.original_filename`:** The task uses `doc.filename` — confirm the `Document` model uses this same column name (not `original_filename`).

3. **BackgroundTasks do not survive server restart:** If uvicorn restarts during processing, the task is lost and the document stays `PROCESSING` forever. The planned fix (from CHANGES.md) is a retry endpoint (`POST /documents/{id}/retry`) that resets status to `PENDING` and re-dispatches the task.
