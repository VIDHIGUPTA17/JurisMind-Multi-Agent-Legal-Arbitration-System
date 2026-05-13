# AGENTS.md — app/core/

## Purpose
Core utilities shared across the entire backend. Handles security (encryption, JWT, passwords), document parsing (PDF text extraction), semantic text chunking, PII detection/anonymization, and structured logging.

## Files

### `security.py`
All cryptographic and authentication operations.

**Functions:**
| Function | Description |
|---|---|
| `hash_password(plain)` | bcrypt hash of a password |
| `verify_password(plain, hashed)` | bcrypt verification |
| `hash_email(email)` | SHA-256 deterministic hash (for DB uniqueness lookup without storing plaintext) |
| `encrypt(text: str) → str` | Fernet symmetric encryption of a string → base64 ciphertext |
| `decrypt(token: str) → str` | Fernet decryption → original string |
| `encrypt_bytes(data: bytes) → bytes` | Fernet encryption of raw bytes |
| `decrypt_bytes(data: bytes) → bytes` | Fernet decryption → raw bytes |
| `create_access_token(data, expires_minutes)` | Create JWT (HS256, default 60 min) |
| `get_current_user_id(token)` | FastAPI dependency — extracts `sub` from JWT |
| `get_current_user_payload(token)` | FastAPI dependency — returns full JWT payload dict |

**Key design decisions:**
- Fernet key comes from `settings.encryption_key` (must be a valid base64 Fernet key)
- Email is **hashed** (SHA-256) for fast lookup by email, but **also encrypted** for storage (so the actual email address is never stored in plaintext anywhere)
- JWT algorithm: HS256; secret from `settings.jwt_secret_key`

### `pdf_parser.py`
PDF text extraction using PyMuPDF (fitz).

**Functions:**
| Function | Description |
|---|---|
| `extract_text_from_pdf(pdf_bytes: bytes) → str` | Extracts all text from a PDF file in memory. Returns concatenated text from all pages. No OCR — text layer only. |

**Notes:**
- Returns empty string if PDF has no selectable text (scanned image PDFs not supported)
- Used by `document_tasks.py` as the first step of the document processing pipeline
- The old `chunk_text()` and `extract_and_chunk()` functions (character-level) have been superseded by `chunker.py`

### `chunker.py`
Semantic document chunker — splits text at paragraph/section boundaries instead of character positions.

**Classes:**
```python
@dataclass
class SemanticChunk:
    index: int
    text: str
    page_numbers: list[int]
    section_header: str | None   # e.g. "Clause 4.2: Termination"
    chunk_type: str              # "clause" | "paragraph" | "table" | "header"
    document_id: str
    token_count: int
```

**Functions:**
| Function | Description |
|---|---|
| `semantic_chunk(text, document_id, max_tokens=512)` | Main chunking function. Returns `list[SemanticChunk]`. |
| `_is_header(line)` | Detects section headers using regex patterns |
| `_split_into_sentences(text)` | Sentence boundary splitting for oversized sections |
| `_estimate_tokens(text)` | Rough token estimate (1 token ≈ 4 characters) |

**Algorithm:**
1. Split text into paragraphs (double newline)
2. Detect section headers via regex: numbered patterns (`1.2 Section`), ALL CAPS, `CLAUSE/SECTION/ARTICLE`, `WHEREAS/NOW THEREFORE`
3. Group consecutive paragraphs under the same section header
4. If a group exceeds `max_tokens`, split at sentence boundaries
5. Sentence-level overlap: last sentence of chunk N = first sentence of chunk N+1

**Why not character-level chunking:**
- Character splits break mid-sentence, mid-clause → LLM gets incomplete legal text
- Semantic chunks preserve entire clauses → judge gets full context
- Section headers are preserved → each chunk knows which clause it came from

### `pii_processor.py`
PII (Personally Identifiable Information) detection and anonymization using Microsoft Presidio.

**Functions:**
| Function | Description |
|---|---|
| `anonymize(text: str) → PIIResult` | Detect and replace PII entities with stable tokens |

**`PIIResult` attributes:**
- `anonymized_text` — text with all PII replaced by tokens (e.g. `PERSON_1`, `AADHAAR_1`)
- `token_map: dict[str, str]` — maps token → original value (for later de-anonymization if authorized)
- `audit: dict[str, int]` — entity type → count (e.g. `{"PERSON": 2, "AADHAAR_NUMBER": 1}`)

**Custom recognizers for Indian documents:**
| Entity | Pattern |
|---|---|
| `AADHAAR_NUMBER` | 12-digit number matching Aadhaar format |
| `PAN_NUMBER` | `[A-Z]{5}[0-9]{4}[A-Z]` (ABCDE1234F) |
| `IN_PHONE_NUMBER` | +91 prefix or 10-digit Indian mobile |
| `BANK_ACCOUNT` | 9–18 digit account numbers |

**Tokenization:**
- Tokens are document-scoped and stable: first PERSON encountered → `PERSON_1`, second → `PERSON_2`
- Only anonymized text is ever sent to Groq API (raw PII never leaves the backend)

### `logging.py`
Structured JSON logging using Python's stdlib `logging` module.

**Functions:**
| Function | Description |
|---|---|
| `setup_logging(level="INFO")` | Configure root logger with `JSONFormatter`, silence SQLAlchemy/uvicorn |
| `get_logger(name)` | Return a named logger (wraps `logging.getLogger`) |

**`JSONFormatter`** outputs one JSON object per line:
```json
{"timestamp": "2024-01-01T00:00:00Z", "level": "INFO", "event": "stage_completed",
 "logger": "app.agents.orchestrator", "case_id": "abc", "stage": "legal_reasoning", "duration_ms": 3200}
```

**Usage in agents/tasks:**
```python
from app.core.logging import get_logger
logger = get_logger(__name__)
logger.info("stage_completed", extra={"case_id": case_id, "duration_ms": 3200})
```

## Data Flow Through core/

```
PDF bytes (encrypted in DB)
    │
    ▼ security.decrypt_bytes()
PDF bytes (raw)
    │
    ▼ pdf_parser.extract_text_from_pdf()
Full document text (plain)
    │
    ▼ chunker.semantic_chunk()
list[SemanticChunk]
    │
    ▼ pii_processor.anonymize() per chunk
Anonymized chunk text + token_map + audit
    │
    ├──► stored as DocumentChunk.chunk_text (anonymized)
    ├──► PIIMapping rows (token → encrypted original)
    └──► PIIAuditLog rows (entity type counts)
```

## Dependencies

- `pymupdf` — PDF text extraction
- `presidio-analyzer`, `presidio-anonymizer`, `spacy` (en_core_web_sm) — PII detection
- `cryptography` — Fernet encryption
- `passlib[bcrypt]` — password hashing
- `python-jose[cryptography]` — JWT
