# AGENTS.md — Project Root

## Purpose
Root directory of the **AI Legal Arbitration System** — a multi-agent AI platform for Indian civil dispute resolution. Built with FastAPI (Python) backend + React (TypeScript) frontend.

## Directory Structure

```
legal_arbitration/
├── app/                  # FastAPI backend application
│   ├── agents/           # AI agents (multi-agent pipeline)
│   ├── core/             # Security, PDF parsing, chunking, logging
│   ├── middleware/       # Rate limiting
│   ├── models/           # SQLAlchemy ORM models (PostgreSQL)
│   ├── rag/              # Retrieval-Augmented Generation pipeline
│   ├── routers/          # FastAPI route handlers (HTTP endpoints)
│   ├── schemas/          # Pydantic request/response schemas
│   ├── tasks/            # Background tasks (document processing)
│   ├── config.py         # Pydantic Settings (reads .env)
│   ├── database.py       # Async SQLAlchemy engine + session
│   └── main.py           # FastAPI app entry point
├── alembic/              # Database migration scripts
├── frontend/             # React + TypeScript + Vite frontend
├── CLAUDE.md             # Project instructions for Claude Code
├── CHANGES.md            # Production upgrade plan (v1 → v2)
├── ARCHITECTURE.md       # Full system architecture documentation
├── requirements.txt      # Python dependencies
├── alembic.ini           # Alembic migration configuration
└── .env.example          # Environment variable template
```

## Key Entry Points

| File | Purpose |
|---|---|
| `app/main.py` | Start FastAPI server: `uvicorn app.main:app --reload` |
| `frontend/` | Start React dev server: `npm run dev` inside `frontend/` |
| `alembic/versions/` | Run migrations: `alembic upgrade head` |
| `.env` | Configure secrets (GROQ_API_KEY, ENCRYPTION_KEY, DATABASE_URL) |

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.115+, Python 3.11+ |
| Database | PostgreSQL 16, SQLAlchemy (async), Alembic |
| AI/LLM | Groq API (llama-3.3-70b-versatile) |
| Embeddings | BAAI/bge-base-en-v1.5 (768-dim, sentence-transformers) |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| PII Protection | Microsoft Presidio (analyzer + anonymizer) |
| PDF Parsing | PyMuPDF |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |

## How the System Works (End-to-End)

1. **User registration** — Party A and Party B register with email + password (bcrypt + Fernet encryption)
2. **Case creation** — Party A creates a dispute case; Party B joins via invite token
3. **Document upload** — Each party uploads PDF evidence; system processes in background
4. **Document processing** — PDF → semantic chunks → PII anonymization → BGE embeddings → stored in DB
5. **Verdict generation** — 7-stage orchestrated pipeline:
   - Stage 1: Party analysis (2× PartyAgent)
   - Stage 2: Evidence comparison (EvidenceComparisonAgent)
   - Stage 3: Contradiction detection + consistency check
   - Stage 4: Legal argument generation + liability reasoning
   - Stage 5: Compensation calculation + settlement recommendation
   - Stage 6: Bias/conflict quality assurance
   - Stage 7: Final verdict (ChiefJudgeAgent)
6. **Verdict delivery** — Structured award with citations, compensation breakdown, grounding report

## Environment Variables Required

```
DATABASE_URL=postgresql+asyncpg://arbitration:arbitration_secret@localhost:5432/legal_arbitration
GROQ_API_KEY=gsk_...
ENCRYPTION_KEY=<Fernet base64 key>
JWT_SECRET_KEY=<64-char hex>
```
