# AGENTS.md — app/models/

## Purpose
SQLAlchemy ORM models that define the PostgreSQL database schema. All models use async-compatible `Mapped` + `mapped_column` syntax (SQLAlchemy 2.0 style). Managed by Alembic migrations.

## Files

### `__init__.py`
Imports all models so they are registered with `Base.metadata` before Alembic runs.
```python
from app.models.user import User
from app.models.case import Case
from app.models.document import Document
from app.models.verdict import Verdict
from app.models.embedding import DocumentChunk
from app.models.pii_mapping import PIIMapping
from app.models.pii_audit import PIIAuditLog
from app.models.arbitration_stage import ArbitrationStage, StageStatus
from app.models.audit_log import AuditLog
```

### `user.py` — Table: `users`

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR(36) PK | UUID |
| `email_encrypted` | Text | Fernet-encrypted email (for display) |
| `email_hash` | VARCHAR(64) UNIQUE | SHA-256 of email (for fast lookup) |
| `hashed_password` | Text | bcrypt hash |
| `full_name_encrypted` | Text | Fernet-encrypted full name |
| `role` | Enum | `PARTY_A` or `PARTY_B` |
| `created_at` | DateTime(tz) | UTC timestamp |

**Why two email fields:** The hash allows uniqueness checks without decrypting every row. The encrypted field allows displaying the email back to the user.

### `case.py` — Table: `cases`

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR(36) PK | UUID |
| `title` | Text | Case title |
| `description` | Text | Optional description |
| `case_type` | Enum | `CONTRACT \| CONSUMER \| PROPERTY \| COMPANY` |
| `status` | Enum | See status lifecycle below |
| `party_a_id` | VARCHAR(36) FK → users | Claimant |
| `party_b_id` | VARCHAR(36) FK → users | Respondent (nullable until joined) |
| `invite_token` | VARCHAR(64) | One-time token for Party B to join |
| `created_at` | DateTime(tz) | |
| `updated_at` | DateTime(tz) | |

**Case status lifecycle:**
```
OPEN → PARTY_A_FILED → PARTY_B_RESPONDED → IN_ARBITRATION → VERDICT_DELIVERED
```

### `document.py` — Table: `documents`

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR(36) PK | UUID |
| `case_id` | FK → cases | |
| `uploader_id` | FK → users | Which party uploaded |
| `filename` | VARCHAR(500) | Original filename |
| `content_encrypted` | LargeBinary | Fernet-encrypted raw PDF bytes |
| `content_anonymized` | Text | PII-anonymized extracted text (set after processing) |
| `original_size_bytes` | Integer | Original PDF size |
| `processing_status` | Enum | `PENDING → PROCESSING → DONE \| FAILED` |
| `error_message` | Text | Populated if FAILED |
| `uploaded_at` | DateTime(tz) | |
| `processed_at` | DateTime(tz) | Set when DONE |

### `embedding.py` — Table: `document_chunks`

Stores text chunks from processed documents along with their vector embeddings for RAG retrieval.

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR(36) PK | UUID |
| `document_id` | FK → documents (CASCADE) | |
| `case_id` | FK → cases (CASCADE) | Denormalized for fast per-case queries |
| `chunk_index` | Integer | Order within document |
| `chunk_text` | Text | PII-anonymized chunk text |
| `embedding` | JSONB | 768-dim float vector (BGE-base-en-v1.5) |
| `section_header` | Text | Which clause/section this chunk came from |
| `chunk_type` | VARCHAR(50) | `paragraph \| clause \| table \| header` |
| `token_count` | Integer | Approximate token count |
| `page_numbers` | JSONB | List of page numbers this chunk spans |
| `document_filename` | VARCHAR(500) | Denormalized filename for citations |

**Note on embedding dimension:** Old documents processed before the BGE upgrade used 384-dim vectors (all-MiniLM-L6-v2). New documents use 768-dim. Do not mix old and new chunks in the same retrieval query — re-embed old documents if needed.

### `verdict.py` — Table: `verdicts`

One verdict per case (UNIQUE constraint on `case_id`).

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR(36) PK | |
| `case_id` | FK → cases UNIQUE | |
| `agent_a_summary` | Text | JSON string: PartyAgent claimant output |
| `agent_b_summary` | Text | JSON string: PartyAgent respondent output |
| `judge_reasoning` | Text | Full reasoning text from ChiefJudgeAgent |
| `verdict_text` | Text | Outcome: `IN FAVOUR OF CLAIMANT` etc. |
| `applicable_laws` | JSONB | List of law references |
| `relief_awarded` | Text | Relief description |
| `created_at` | DateTime(tz) | |
| `confidence_score` | Float | 0.0–1.0 from ChiefJudgeAgent |
| `grounding_report` | JSONB | CitationTracker grounding verification result |
| `bias_report` | JSONB | BiasConflictAgent output |
| `settlement_recommendation` | JSONB | SettlementRecommendationAgent output |
| `compensation_breakdown` | JSONB | CompensationCalculationAgent output |
| `stage_count` | Integer | Number of stages run (default 7) |
| `total_groq_tokens` | Integer | Total Groq API tokens consumed |
| `total_duration_ms` | Integer | Total pipeline wall-clock time |

### `arbitration_stage.py` — Table: `arbitration_stages`

Tracks each stage of the 7-stage pipeline for transparency and resume capability.

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR(36) PK | |
| `case_id` | FK → cases (CASCADE) | |
| `stage_number` | Integer | 1–7 |
| `stage_name` | VARCHAR(100) | `party_analysis`, `evidence_comparison`, etc. |
| `status` | Enum | `PENDING \| RUNNING \| COMPLETED \| FAILED \| SKIPPED` |
| `agent_name` | VARCHAR(100) | Which agent(s) ran this stage |
| `input_summary` | Text | Brief description of inputs |
| `output_json` | JSONB | Full structured output from agent(s) |
| `output_summary` | Text | Human-readable summary for frontend display |
| `citations` | JSONB | Citation references used in this stage |
| `error_message` | Text | Populated if FAILED |
| `started_at` | DateTime(tz) | |
| `completed_at` | DateTime(tz) | |
| `duration_ms` | Integer | Wall-clock time of this stage |
| `groq_tokens_used` | Integer | Tokens consumed by this stage |
| `created_at` | DateTime(tz) | |

### `audit_log.py` — Table: `audit_logs`

Audit trail for compliance — every significant user action is recorded.

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR(36) PK | |
| `user_id` | FK → users (CASCADE) | Who performed the action |
| `action` | VARCHAR(100) | `verdict_viewed`, `document_uploaded`, `case_created` |
| `resource_type` | VARCHAR(50) | `case`, `document`, `verdict` |
| `resource_id` | VARCHAR(36) | The specific resource UUID |
| `ip_address` | VARCHAR(50) | Client IP |
| `timestamp` | DateTime(tz) | UTC |
| `metadata_` | JSONB | Additional context (stored as column `metadata`) |

### `pii_mapping.py` — Table: `pii_mappings`

Maps PII anonymization tokens back to encrypted original values. Allows authorized de-anonymization.

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR(36) PK | |
| `document_id` | FK → documents | |
| `token` | VARCHAR(100) | e.g. `PERSON_1`, `AADHAAR_2` |
| `entity_type` | VARCHAR(50) | e.g. `PERSON`, `AADHAAR_NUMBER` |
| `encrypted_value` | Text | Fernet-encrypted original PII value |

### `pii_audit.py` — Table: `pii_audit_logs`

Logs how many PII entities of each type were found per document.

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR(36) PK | |
| `document_id` | FK → documents | |
| `entity_type` | VARCHAR(100) | e.g. `PERSON`, `PHONE_NUMBER` |
| `count_found` | Integer | How many instances detected |
| `processing_time_ms` | Integer | Optional timing |

## Entity Relationship Diagram

```
users ──1:N──► cases (as party_a or party_b)
cases ──1:N──► documents
cases ──1:1──► verdicts
cases ──1:N──► arbitration_stages (7 per verdict run)
documents ──1:N──► document_chunks
documents ──1:N──► pii_mappings
documents ──1:N──► pii_audit_logs
users ──1:N──► audit_logs
```

## Naming Conventions

- All PKs are `VARCHAR(36)` UUID strings (not auto-increment integers)
- All timestamps are `DateTime(timezone=True)` (stored as UTC)
- Foreign keys use `ondelete="CASCADE"` where appropriate (chunks deleted with document)
- JSONB columns default to `[]` for arrays, `{}` for objects
