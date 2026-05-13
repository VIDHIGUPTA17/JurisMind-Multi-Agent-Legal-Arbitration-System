# AI Legal Arbitration System

A production-grade **multi-agent AI arbitration platform** for Indian civil disputes. Two parties submit PDF evidence, the system anonymises all PII, and a **10-agent, 7-stage pipeline** powered by Groq LLM delivers a binding arbitral award — with legal reasoning, bias attestation, grounding verification, and real-time progress streaming.

Built with **FastAPI + React 18 + PostgreSQL 16 + Groq (llama-3.3-70b)**.

---

## Table of Contents

- [Demo Flow](#demo-flow)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Architecture Overview](#architecture-overview)
- [Agentic Architecture — 10 Agents, 7 Stages](#agentic-architecture--10-agents-7-stages)
  - [Stage 1 — Party Analysis](#stage-1--party-analysis)
  - [Stage 2 — Evidence Comparison](#stage-2--evidence-comparison)
  - [Stage 3 — Contradiction & Witness Consistency](#stage-3--contradiction--witness-consistency)
  - [Stage 4 — Legal Reasoning & Liability](#stage-4--legal-reasoning--liability)
  - [Stage 5 — Compensation & Settlement](#stage-5--compensation--settlement)
  - [Stage 6 — Bias & Neutrality Check](#stage-6--bias--neutrality-check)
  - [Stage 7 — Final Verdict (Chief Judge)](#stage-7--final-verdict-chief-judge)
- [Agentic Flow Diagram](#agentic-flow-diagram)
- [RAG Pipeline](#rag-pipeline)
- [Real-Time SSE Streaming](#real-time-sse-streaming)
- [Security Architecture](#security-architecture)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Frontend Pages](#frontend-pages)
- [Setup & Run](#setup--run)
- [Project Structure](#project-structure)

---

## Demo Flow

```
Register → Create Case → Upload PDF (Party A) → Party B Joins → Upload PDF (Party B)
→ Trigger AI Verdict → Watch Live 7-Stage Pipeline → View Binding Award
```

The live **ArbitrationRoom** page streams every agent's progress in real time via Server-Sent Events, showing both parties' arguments side by side as the pipeline deliberates.

---

## Features

| Feature | Detail |
|---|---|
| Multi-agent pipeline | 10 specialised AI agents across 7 stages |
| Real-time streaming | Server-Sent Events (SSE) — per-stage progress to browser |
| PII anonymisation | Presidio + Indian-specific recognisers (Aadhaar, PAN, phone) |
| Semantic RAG | BGE-base 768-dim embeddings + CrossEncoder reranker |
| Legal grounding | CitationTracker verifies every verdict claim against evidence |
| Bias attestation | BiasConflictAgent scores neutrality 0–1, flags partisan reasoning |
| JWT security | Access + refresh token pair, Fernet document encryption |
| Rate limiting | 3 verdict requests / hour / IP (slowapi) |
| Structured logging | JSON logs via structlog for every pipeline event |
| Retry on failure | Resume arbitration from last failed stage |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI ≥0.115, Uvicorn |
| Database | PostgreSQL 16, asyncpg, SQLAlchemy 2.0, Alembic |
| LLM | Groq API — `llama-3.3-70b-versatile` |
| Embeddings | `BAAI/bge-base-en-v1.5` (768-dim) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| PII | Microsoft Presidio + spaCy `en_core_web_sm` |
| PDF | PyMuPDF |
| Encryption | Fernet (cryptography), bcrypt (passlib), python-jose JWT |
| Frontend | React 18 + TypeScript, Vite, Tailwind CSS, React Router v6 |
| Async tasks | FastAPI BackgroundTasks (no Redis/Celery required) |
| Rate limiting | slowapi |
| Logging | structlog (structured JSON) |

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                   FRONTEND  (React 18 + Vite)                        │
│  Login │ Cases List │ Case Detail │ ArbitrationRoom │ Verdict Page   │
└─────────────────────────┬──────────────────────┬─────────────────────┘
                          │  HTTP/REST (JWT)      │  SSE (?token=)
                          ▼                      ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   BACKEND  (FastAPI + Uvicorn :8000)                 │
│                                                                      │
│  /auth    /cases    /documents    /verdicts    /arbitration/stream   │
│                                       │               │              │
│                          ┌────────────┘               │              │
│                          ▼                            ▼              │
│              ArbitrationOrchestrator       SSE broadcast queues      │
│              (7-stage pipeline)            (asyncio.Queue per case)  │
│                          │                                           │
│       ┌──────────────────┼──────────────────┐                       │
│       ▼                  ▼                  ▼                       │
│  BackgroundTasks     RAG Layer          core/security               │
│  (PDF→chunk→embed)   (BGE + reranker    (JWT, Fernet,               │
│                       + citations)       bcrypt)                     │
└──────────────────────────────────────────────────┬───────────────────┘
                                                   │
                    ┌──────────────────────────────┤
                    ▼                              ▼
       ┌────────────────────────┐    ┌──────────────────────────┐
       │    PostgreSQL 16        │    │     Groq Cloud API        │
       │  9 tables, asyncpg     │    │  llama-3.3-70b-versatile  │
       │  JSONB for embeddings  │    │  7–14 LLM calls/verdict   │
       └────────────────────────┘    └──────────────────────────┘
```

---

## Agentic Architecture — 10 Agents, 7 Stages

The `ArbitrationOrchestrator` runs a deterministic 7-stage pipeline. Each stage:
- Creates an `ArbitrationStage` DB record (status: RUNNING → COMPLETED / FAILED)
- Broadcasts a `stage_started` / `stage_completed` / `stage_failed` SSE event
- Passes its output as context to the next stage
- Can be individually resumed if it fails

All agents extend `BaseAgent`, which handles:
- Groq API call with exponential backoff (handles 429 rate limits)
- JSON response parsing and validation
- Token usage logging per call

---

### Stage 1 — Party Analysis

**Agents:** `PartyAgent` × 2 (run in parallel via `asyncio.gather`)

**Input:** Raw anonymised document text from claimant and respondent

**What it does:**
- Each `PartyAgent` instance independently reads one party's documents
- Extracts structured claims (claimant) or defences (respondent)
- Scores each claim/defence with a strength: `STRONG` / `MODERATE` / `WEAK`
- Produces `overall_strength_assessment` and `relief_sought`

**Output JSON:**
```json
{
  "claimant_summary": {
    "claims": [{"claim": "...", "evidence_basis": "...", "strength": "STRONG"}],
    "relief_sought": "₹5,00,000 compensation",
    "overall_strength_assessment": "MODERATE"
  },
  "respondent_summary": {
    "defences": [{"defence": "...", "evidence_basis": "...", "strength": "WEAK"}],
    "overall_strength_assessment": "WEAK"
  }
}
```

**SSE event broadcast:** `stage_started`, `stage_completed` with claim/defence counts

---

### Stage 2 — Evidence Comparison

**Agent:** `EvidenceComparisonAgent`

**Input:** Stage 1 summaries + RAG-retrieved evidence chunks (top-15 via BGE + CrossEncoder)

**What it does:**
- For every claim filed by the claimant, cross-references it against the evidence corpus
- Labels each claim: `SUPPORTED` / `NOT_FOUND` / `CONTRADICTED`
- Counts totals for a quick scorecard

**Output JSON:**
```json
{
  "evidence_findings": [
    {"claim": "...", "status": "SUPPORTED", "supporting_chunks": ["..."]},
    {"claim": "...", "status": "CONTRADICTED", "contradiction_reason": "..."}
  ],
  "supported_count": 3,
  "not_found_count": 1,
  "contradicted_count": 1,
  "total_claims_analyzed": 5
}
```

---

### Stage 3 — Contradiction & Witness Consistency

**Agents:** `ContradictionDetectionAgent` + `WitnessConsistencyAgent` × 2 (run in parallel)

**Input:** Stages 1 & 2 outputs

**What it does:**
- `ContradictionDetectionAgent` finds internal contradictions within each party's statements and between them; also extracts agreed facts
- `WitnessConsistencyAgent` independently checks each party's documents for self-consistency and assigns a score 0–1

**Output JSON:**
```json
{
  "contradiction_report": {
    "contradictions": [{"fact": "...", "party_a_claim": "...", "party_b_claim": "..."}],
    "agreed_facts": ["Payment was due on 15 Jan 2024"],
    "contradiction_count": 2,
    "agreed_fact_count": 1
  },
  "claimant_consistency": {"consistency_score": 0.85, "issues": []},
  "respondent_consistency": {"consistency_score": 0.60, "issues": ["Date mismatch..."]}
}
```

---

### Stage 4 — Legal Reasoning & Liability

**Agents:** `LegalArgumentAgent` → `LiabilityReasoningAgent` (sequential, second uses first's output)

**Input:** Stages 1–3 outputs

**What it does:**
- `LegalArgumentAgent` maps the dispute to applicable **Indian statutes** (Indian Contract Act 1872, Sale of Goods Act 1930, Consumer Protection Act 2019, IPC, etc.) and generates structured legal arguments for both sides
- `LiabilityReasoningAgent` synthesises all findings to determine a **liability split** (e.g., Party A: 70%, Party B: 30%) with reasoning

**Output JSON:**
```json
{
  "legal_analysis": {
    "legal_issues": [
      {"issue": "Breach of contract", "statute": "Indian Contract Act 1872, S.73", "applicable_to": "CLAIMANT"}
    ],
    "claimant_arguments": ["..."],
    "respondent_arguments": ["..."]
  },
  "liability_determination": {
    "primary_liability": "PARTY_A",
    "liability_split": {"party_a": 70, "party_b": 30},
    "reasoning": "..."
  }
}
```

---

### Stage 5 — Compensation & Settlement

**Agents:** `CompensationCalculationAgent` + `SettlementRecommendationAgent` (run in parallel)

**Input:** Stage 4 liability determination + Stage 1 claimant summary

**What it does:**
- `CompensationCalculationAgent` calculates the total monetary award in INR (principal + interest + costs), broken down by component
- `SettlementRecommendationAgent` recommends a negotiated settlement range and whether out-of-court resolution is advisable

**Output JSON:**
```json
{
  "compensation_breakdown": {
    "principal_amount": 400000,
    "interest": 32000,
    "legal_costs": 15000,
    "total_award": 447000
  },
  "settlement_recommendation": {
    "settlement_recommended": true,
    "settlement_range": {"min": 350000, "max": 420000},
    "rationale": "..."
  }
}
```

---

### Stage 6 — Bias & Neutrality Check

**Agent:** `BiasConflictAgent`

**Input:** Full pipeline context (all prior stage outputs)

**What it does:**
- Reviews the entire reasoning chain for signs of partisan bias, inconsistent evidence weighting, or cultural/gender favouritism
- Outputs a neutrality score from 0 (heavily biased) to 1 (fully neutral)
- Flags specific reasoning statements that appear biased
- If `passed = false`, the verdict must be reviewed

**Output JSON:**
```json
{
  "overall_bias_score": 0.92,
  "passed": true,
  "flags": [],
  "party_a_favorability": 0.55,
  "party_b_favorability": 0.45,
  "assessment": "Reasoning is balanced. Evidence weighting is proportional."
}
```

---

### Stage 7 — Final Verdict (Chief Judge)

**Agent:** `ChiefJudgeAgent`

**Input:** Full pipeline context including bias report

**What it does:**
- Synthesises all 6 prior stages into a single binding arbitral award
- Selects one of: `IN FAVOUR OF CLAIMANT` / `IN FAVOUR OF RESPONDENT` / `PARTIAL AWARD` / `DISMISSED`
- Produces full judge's reasoning (2–4 paragraphs), applicable laws list, and a confidence score
- After the verdict, `CitationTracker` verifies every claim in the reasoning against the original evidence chunks (grounding verification)

**Output JSON:**
```json
{
  "verdict": "PARTIAL AWARD",
  "verdict_text": "IN FAVOUR OF CLAIMANT",
  "judge_reasoning": "Having considered all submissions...",
  "applicable_laws": ["Indian Contract Act 1872, Section 73", "..."],
  "relief_awarded": {
    "amount_inr": 447000,
    "description": "Compensation for breach of contract",
    "interest": "9% per annum from date of breach",
    "costs": "Arbitration costs awarded to claimant"
  },
  "confidence_score": 0.87,
  "bias_attestation": "Pipeline passed neutrality check (score: 0.92)"
}
```

---

## Agentic Flow Diagram

```
                        ARBITRATION ORCHESTRATOR
                               │
         ┌─────────────────────▼──────────────────────┐
         │              STAGE 1: Party Analysis         │
         │   PartyAgent(CLAIMANT) ║ PartyAgent(RESPONDENT)  │
         │     [parallel execution via asyncio.gather]   │
         └──────────────────────┬─────────────────────-─┘
                                │  claimant_summary, respondent_summary
         ┌──────────────────────▼──────────────────────┐
         │          STAGE 2: Evidence Comparison         │
         │           EvidenceComparisonAgent             │
         │    [RAG retrieval: BGE embed → rerank → cite] │
         └──────────────────────┬──────────────────────-┘
                                │  evidence_map (SUPPORTED/NOT_FOUND/CONTRADICTED)
         ┌──────────────────────▼──────────────────────┐
         │    STAGE 3: Contradiction & Consistency       │
         │  ContradictionDetectionAgent                  │
         │    ║ WitnessConsistencyAgent(CLAIMANT)        │
         │    ║ WitnessConsistencyAgent(RESPONDENT)      │
         │      [3-way parallel execution]               │
         └──────────────────────┬──────────────────────-┘
                                │  contradiction_report, consistency scores
         ┌──────────────────────▼──────────────────────┐
         │          STAGE 4: Legal Reasoning             │
         │    LegalArgumentAgent → LiabilityReasoningAgent  │
         │      [sequential — liability uses legal args] │
         └──────────────────────┬──────────────────────-┘
                                │  legal_analysis, liability_split %
         ┌──────────────────────▼──────────────────────┐
         │         STAGE 5: Resolution & Compensation    │
         │  CompensationCalculationAgent                 │
         │    ║ SettlementRecommendationAgent            │
         │      [parallel execution]                     │
         └──────────────────────┬──────────────────────-┘
                                │  total_award INR, settlement range
         ┌──────────────────────▼──────────────────────┐
         │         STAGE 6: Bias & Neutrality Check      │
         │               BiasConflictAgent               │
         │    [reviews entire context for partisan bias] │
         └──────────────────────┬──────────────────────-┘
                                │  bias_score 0–1, passed flag
         ┌──────────────────────▼──────────────────────┐
         │           STAGE 7: Final Verdict              │
         │              ChiefJudgeAgent                  │
         │    [synthesises all 6 stages → binding award] │
         │    + CitationTracker grounding verification   │
         └──────────────────────┬──────────────────────-┘
                                │
                    verdict_ready SSE event
                                │
                    ┌───────────▼───────────┐
                    │  Verdict stored in DB  │
                    │  Case → VERDICT_DELIVERED │
                    │  Frontend auto-redirects  │
                    └───────────────────────┘

Each stage broadcasts via SSE:
  → stage_started  { stage_number, stage_name }
  → stage_completed { stage_number, summary, duration_ms }
  → stage_failed   { stage_number, error }
  → verdict_ready  { verdict, confidence }
```

---

## RAG Pipeline

Evidence retrieval runs a **5-layer pipeline** before feeding context to agents:

```
User Query / Agent Query
        │
        ▼
1. QueryExpander
   — adds Indian legal synonyms
   — expands to related statutes (e.g. "breach" → "Section 73 ICA 1872")
        │
        ▼
2. Dense Retrieval
   — BAAI/bge-base-en-v1.5 encodes the query (768-dim)
   — cosine similarity search against document_chunks table
   — top-50 candidates retrieved
        │
        ▼
3. CrossEncoder Reranking
   — cross-encoder/ms-marco-MiniLM-L-6-v2
   — re-scores all 50 candidates
   — top-15 selected
        │
        ▼
4. CitationTracker
   — assigns chunk_id references to each retrieved passage
   — tracks which document each chunk came from (claimant vs respondent)
        │
        ▼
5. GroundingReport (post-verdict)
   — verifies every claim in the final verdict against cited chunks
   — outputs overall grounding score 0–1
```

---

## Real-Time SSE Streaming

The `ArbitrationRoom` frontend page connects to:

```
GET /cases/{case_id}/arbitration/stream?token=<jwt>
```

The browser `EventSource` API cannot send `Authorization` headers, so the JWT is passed as a query parameter and decoded server-side.

Each subscriber gets its own `asyncio.Queue`. The orchestrator broadcasts to all queues for a case.

**SSE Event types:**

| Event | Payload |
|---|---|
| `stage_started` | `{ stage_number, stage_name, message }` |
| `stage_completed` | `{ stage_number, stage_name, summary, duration_ms }` |
| `stage_failed` | `{ stage_number, stage_name, error }` |
| `verdict_ready` | `{ verdict, confidence }` |
| `: ping` | Keep-alive (every 30s of inactivity) |

---

## Security Architecture

| Concern | Solution |
|---|---|
| Passwords | bcrypt via passlib |
| Auth tokens | JWT (HS256) — access (30 min) + refresh (7 days) |
| Document content | Fernet symmetric encryption at rest |
| Email lookup | SHA-256 hash stored separately — O(1) login, no plaintext |
| PII in PDFs | Presidio analyser + custom Indian recognisers (Aadhaar, PAN, phone numbers) — anonymised before embedding |
| Rate limiting | slowapi — 3 verdict requests / hour / IP |
| Body size | 10 MB upload limit enforced at ASGI level |

---

## Database Schema

```
users               — id, email_encrypted, email_hash, hashed_password, role
cases               — id, title, case_type, status (enum), party_a_id, party_b_id, invite_token
documents           — id, case_id, uploader_id, filename, content_encrypted, content_anonymized,
                       processing_status (PENDING/PROCESSING/PROCESSED/FAILED)
document_chunks     — id, document_id, case_id, chunk_text, embedding (JSONB 768-dim),
                       chunk_index, section_header, chunk_type, page_number
verdicts            — id, case_id, verdict_text, judge_reasoning, applicable_laws,
                       agent_a_summary, agent_b_summary, relief_awarded,
                       confidence_score, grounding_report, bias_report  ← v2 fields
arbitration_stages  — id, case_id, stage_number, stage_name, agent_name,
                       status, started_at, completed_at, duration_ms,
                       output_summary, output_json, error_message
audit_logs          — id, case_id, user_id, action, details, timestamp
pii_mappings        — id, document_id, original_text, anonymized_text, entity_type
pii_audit_logs      — id, document_id, entities_found, processing_timestamp
```

**Case status state machine:**
```
CREATED → PARTY_A_FILED → PARTY_B_JOINED → PARTY_B_RESPONDED
       → IN_ARBITRATION → VERDICT_DELIVERED
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register, returns JWT pair |
| POST | `/auth/login` | Login, returns JWT pair |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/cases/` | Create a dispute case |
| GET | `/cases/` | List my cases |
| GET | `/cases/{id}` | Case detail |
| POST | `/cases/{id}/join` | Party B joins via invite token |
| POST | `/cases/{id}/documents` | Upload PDF evidence |
| POST | `/cases/{id}/documents/{doc_id}/retry` | Retry failed processing |
| POST | `/cases/{id}/verdict` | Trigger 7-stage pipeline (202) |
| GET | `/cases/{id}/verdict` | Fetch completed verdict |
| GET | `/cases/{id}/verdict/grounding` | Grounding verification report |
| GET | `/cases/{id}/verdict/bias` | Bias / neutrality report |
| GET | `/cases/{id}/arbitration/stages` | All 7 stage statuses |
| GET | `/cases/{id}/arbitration/stages/{n}` | Single stage + output JSON |
| POST | `/cases/{id}/arbitration/resume` | Resume from last FAILED stage |
| GET | `/cases/{id}/arbitration/stream` | SSE stream (pass `?token=`) |
| GET | `/health` | Deep health check (DB + embedding model) |

---

## Frontend Pages

| Page | Route | Description |
|---|---|---|
| Login / Register | `/login` | Auth forms, stores JWT in localStorage |
| Cases List | `/cases` | All cases for current user, create new case |
| Case Detail | `/cases/:id` | Upload docs, see processing status, trigger verdict |
| Arbitration Room | `/cases/:id/arbitration` | **Live SSE pipeline viewer** — both party positions, 7-stage tracker, real-time agent log, progress bar. Auto-redirects to verdict on completion |
| Verdict | `/cases/:id/verdict` | Final binding award — verdict banner, judge reasoning, applicable laws, both party summaries, relief awarded |

---

## Setup & Run

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16

### 1. Database

```sql
-- Run in pgAdmin or psql
CREATE USER arbitration WITH PASSWORD 'arbitration_secret';
CREATE DATABASE legal_arbitration OWNER arbitration;
GRANT ALL PRIVILEGES ON DATABASE legal_arbitration TO arbitration;
```

### 2. Backend

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
python -m spacy download en_core_web_sm

cp .env.example .env
# Edit .env — fill in GROQ_API_KEY, ENCRYPTION_KEY, JWT_SECRET_KEY

alembic upgrade head

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Generate secrets:
```bash
# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- Frontend: http://localhost:5173

---

## Project Structure

```
legal_arbitration/
├── app/
│   ├── agents/
│   │   ├── base_agent.py                      # Groq client, retry, JSON parsing
│   │   ├── party_agent.py                     # Stage 1
│   │   ├── evidence_comparison_agent.py       # Stage 2
│   │   ├── contradiction_detection_agent.py   # Stage 3a
│   │   ├── witness_consistency_agent.py       # Stage 3b
│   │   ├── legal_argument_agent.py            # Stage 4a
│   │   ├── liability_reasoning_agent.py       # Stage 4b
│   │   ├── compensation_calculation_agent.py  # Stage 5a
│   │   ├── settlement_recommendation_agent.py # Stage 5b
│   │   ├── bias_conflict_agent.py             # Stage 6
│   │   ├── chief_judge_agent.py               # Stage 7
│   │   └── orchestrator.py                   # Pipeline runner + SSE broadcast
│   ├── core/
│   │   ├── security.py                        # JWT, Fernet, bcrypt
│   │   ├── logging.py                         # structlog JSON
│   │   ├── chunker.py                         # Semantic PDF chunking
│   │   ├── pdf_parser.py                      # PyMuPDF
│   │   └── pii_processor.py                   # Presidio + Indian recognisers
│   ├── models/                                # SQLAlchemy ORM models
│   ├── rag/                                   # BGE embeddings, reranker, retriever, citations
│   ├── routers/                               # FastAPI route handlers
│   ├── schemas/                               # Pydantic request/response models
│   ├── tasks/document_tasks.py               # Async document processing
│   ├── config.py
│   ├── database.py
│   └── main.py
├── alembic/versions/
│   ├── 001_initial_schema.py
│   └── 002_v2_columns_and_tables.py
├── frontend/src/
│   ├── pages/                                 # Login, Cases, CaseDetail, ArbitrationRoom, Verdict
│   ├── components/                            # VerdictCard, StatusBadge, UploadDropzone
│   ├── context/AuthContext.tsx
│   └── api/client.ts
├── requirements.txt
├── .env.example
└── ARCHITECTURE.md
```

---

## License

MIT
