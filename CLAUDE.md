# AI Legal Arbitration System — v2

A multi-agent AI arbitration platform for Indian civil disputes. Built with FastAPI (Python) + React (TypeScript), powered by Groq LLM, PostgreSQL, and FastAPI BackgroundTasks for async processing.

## Architecture

```
Backend  : FastAPI + SQLAlchemy (async) + Alembic migrations
Database : PostgreSQL 16 (plain, no extensions — JSONB for embeddings)
Async    : FastAPI BackgroundTasks (no Redis/Celery needed)
LLM      : Groq API (llama-3.3-70b-versatile)
RAG      : BAAI/bge-base-en-v1.5 (768-dim) + cross-encoder reranker + citation tracking
PII      : Microsoft Presidio (analyzer + anonymizer) + Fernet encryption
PDF      : PyMuPDF + semantic chunking (paragraph/section boundaries)
Frontend : React 18 + TypeScript + Vite + Tailwind CSS
SSE      : Real-time arbitration stage updates via Server-Sent Events
Rate     : slowapi (3 verdict requests/hour/IP)
Logging  : Structured JSON logging via app/core/logging.py
```

### 7-Stage Agent Pipeline (ArbitrationOrchestrator)

| Stage | Agent(s) | Output |
|---|---|---|
| 1 | PartyAgent × 2 | Claimant & respondent summaries with claim strength |
| 2 | EvidenceComparisonAgent | SUPPORTED / NOT_FOUND / CONTRADICTED per claim |
| 3 | ContradictionDetectionAgent + WitnessConsistencyAgent | Contradictions, agreed facts, consistency scores |
| 4 | LegalArgumentAgent + LiabilityReasoningAgent | Legal issues (Indian statutes), liability split % |
| 5 | CompensationCalculationAgent + SettlementRecommendationAgent | Total award INR, settlement range |
| 6 | BiasConflictAgent | Neutrality score 0–1, pass/fail flag |
| 7 | ChiefJudgeAgent | Final verdict with confidence score + bias attestation |

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16 (plain install, no extensions needed)

---

## How to Run (without Docker)

### 1. Install PostgreSQL 16

Download and install from https://www.postgresql.org/download/windows/

After installation, verify it is running:
```powershell
pg_isready -U postgres
```

### 2. (Optional) Install pgAdmin

pgAdmin is the GUI tool for PostgreSQL.
Download from https://www.pgadmin.org/download/ and connect to your local PostgreSQL instance.

### 3. Create the database and user via pgAdmin

Open **pgAdmin**, connect to your local PostgreSQL server, then open the **Query Tool** (Tools → Query Tool) and run:

```sql
CREATE USER arbitration WITH PASSWORD 'arbitration_secret';
CREATE DATABASE legal_arbitration OWNER arbitration;
GRANT ALL PRIVILEGES ON DATABASE legal_arbitration TO arbitration;
```

### 4. Set up Python environment

```powershell
cd legal_arbitration
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Download spaCy model (required by Presidio)

```powershell
python -m spacy download en_core_web_sm
```

### 6. Configure environment

```powershell
copy .env.example .env
```

Edit `.env` and fill in:
- `GROQ_API_KEY` — get from https://console.groq.com
- `ENCRYPTION_KEY` — generate with:
  ```powershell
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `JWT_SECRET_KEY` — generate with:
  ```powershell
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

The `DATABASE_URL` in `.env` should match the credentials you set in step 3 above:
```
DATABASE_URL=postgresql+asyncpg://arbitration:arbitration_secret@localhost:5432/legal_arbitration
```

### 7. Run database migrations

```powershell
alembic upgrade head
```

This creates all tables including `arbitration_stages` and `audit_logs` (v2 tables).

### 8. Start FastAPI backend

```powershell
.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend: http://localhost:8000  
API docs: http://localhost:8000/docs

### 9. Start React frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

---

## Key API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register a new user (returns access + refresh token) |
| POST | `/auth/login` | Login, receive JWT pair |
| POST | `/auth/refresh` | Exchange refresh token for new token pair |
| POST | `/cases/` | Create a dispute case |
| GET  | `/cases/{id}` | Get case details |
| POST | `/cases/{id}/documents` | Upload evidence PDF |
| POST | `/cases/{id}/documents/{doc_id}/retry` | Retry failed document processing |
| POST | `/cases/{id}/verdict` | Trigger 7-stage AI pipeline (returns 202) |
| GET  | `/cases/{id}/verdict` | Fetch full verdict with v2 fields |
| GET  | `/cases/{id}/verdict/grounding` | Grounding verification report |
| GET  | `/cases/{id}/verdict/bias` | Bias/neutrality report |
| GET  | `/cases/{id}/arbitration/stages` | All 7 stage statuses |
| GET  | `/cases/{id}/arbitration/stages/{n}` | Single stage detail + output JSON |
| POST | `/cases/{id}/arbitration/resume` | Resume from last FAILED stage |
| GET  | `/cases/{id}/arbitration/stream` | SSE stream of real-time stage events |
| GET  | `/health` | Deep health check (DB + embedding model) |

## Project Structure

```
legal_arbitration/
├── app/
│   ├── agents/
│   │   ├── base_agent.py                  # Retry logic, JSON parsing
│   │   ├── party_agent.py                 # Claimant/respondent summaries
│   │   ├── evidence_comparison_agent.py   # SUPPORTED/NOT_FOUND/CONTRADICTED
│   │   ├── contradiction_detection_agent.py
│   │   ├── witness_consistency_agent.py
│   │   ├── legal_argument_agent.py        # Indian statute citations
│   │   ├── liability_reasoning_agent.py   # Liability split %
│   │   ├── compensation_calculation_agent.py  # Total award INR
│   │   ├── settlement_recommendation_agent.py
│   │   ├── bias_conflict_agent.py         # Neutrality 0–1 score
│   │   ├── chief_judge_agent.py           # Final verdict
│   │   └── orchestrator.py               # 7-stage pipeline + SSE broadcast
│   ├── core/
│   │   ├── chunker.py                     # Semantic PDF chunking
│   │   ├── logging.py                     # JSON structured logging
│   │   ├── pii_processor.py               # Presidio + Indian recognizers
│   │   ├── pdf_parser.py
│   │   └── security.py                    # JWT, Fernet, bcrypt
│   ├── models/
│   │   ├── arbitration_stage.py           # 7-stage tracking per case
│   │   ├── audit_log.py                   # Compliance audit trail
│   │   ├── case.py
│   │   ├── document.py
│   │   ├── embedding.py                   # semantic chunk metadata
│   │   ├── user.py
│   │   └── verdict.py                     # v2 fields: confidence, grounding, bias
│   ├── rag/
│   │   ├── embeddings.py                  # BAAI/bge-base-en-v1.5 (768-dim)
│   │   ├── query_expander.py              # Legal synonym + statute expansion
│   │   ├── reranker.py                    # cross-encoder/ms-marco reranker
│   │   ├── citation_tracker.py            # CitationTracker + GroundingReport
│   │   └── retriever.py                   # 5-layer RAG pipeline
│   ├── routers/
│   │   ├── arbitration_stream.py          # SSE /cases/{id}/arbitration/stream
│   │   ├── auth.py                        # register / login / refresh
│   │   ├── cases.py
│   │   ├── documents.py                   # upload + retry
│   │   └── verdicts.py                    # trigger / get / stages / grounding / bias
│   ├── schemas/
│   │   ├── arbitration.py                 # StageResponse, StagesListResponse
│   │   ├── auth.py                        # RegisterRequest, TokenResponse, RefreshTokenRequest
│   │   ├── case.py
│   │   ├── document.py
│   │   └── verdict.py                     # VerdictResponse with v2 fields
│   ├── tasks/
│   │   └── document_tasks.py              # Semantic chunking + BGE embedding
│   ├── config.py
│   ├── database.py
│   └── main.py                            # Lifespan, rate limiter, body size limit
├── alembic/                               # DB migration scripts
├── frontend/                              # React + Vite + Tailwind
├── requirements.txt
└── .env.example
```

## Stopping the System

```powershell
# Stop FastAPI — Ctrl+C in its terminal

# Stop PostgreSQL (Windows service)
Stop-Service postgresql-x64-16
```
