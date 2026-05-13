# AI Legal Arbitration System — Architecture (v2)

A multi-agent AI arbitration platform for Indian civil disputes.
Built with FastAPI + React 18, powered by Groq LLM, PostgreSQL 16, Microsoft Presidio, and real-time SSE streaming.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Technology Stack](#2-technology-stack)
3. [High-Level Architecture Diagram](#3-high-level-architecture-diagram)
4. [Directory Structure](#4-directory-structure)
5. [Database Schema](#5-database-schema)
6. [Data Flow: Document Processing Pipeline](#6-data-flow-document-processing-pipeline)
7. [Agentic Flow: 7-Stage Arbitration Pipeline](#7-agentic-flow-7-stage-arbitration-pipeline)
8. [RAG Pipeline (v2)](#8-rag-pipeline-v2)
9. [SSE Real-Time Streaming](#9-sse-real-time-streaming)
10. [Security Architecture](#10-security-architecture)
11. [API Endpoints](#11-api-endpoints)
12. [Case State Machine](#12-case-state-machine)
13. [Frontend Page Flow](#13-frontend-page-flow)
14. [Key Design Decisions](#14-key-design-decisions)

---

## 1. System Overview

The AI Legal Arbitration System automates civil dispute resolution under Indian law. Two parties (claimant and respondent) submit PDF evidence. The system anonymizes all PII, generates embeddings, and feeds the data to a **7-stage multi-agent AI pipeline** that produces a binding verdict with legal reasoning, bias attestation, and grounding verification.

**Core capabilities (v2):**
- Secure user registration + JWT access/refresh token pair
- Encrypted PDF evidence storage (Fernet)
- Automatic PII detection and anonymization (Aadhaar, PAN, phone, names)
- Semantic PDF chunking (paragraph/section boundaries)
- BGE-base embeddings (768-dim) + cross-encoder reranking
- **7-stage multi-agent deliberation** with per-stage DB tracking
- Real-time SSE streaming of pipeline progress to frontend
- Bias/neutrality verification (BiasConflictAgent, score 0–1)
- Grounding verification (CitationTracker + GroundingReport)
- Rate limiting: 3 verdict requests/hour/IP (slowapi)
- Structured JSON logging (structlog)

---

## 2. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| Backend Framework | FastAPI | ≥0.115 | Async REST API + SSE |
| ASGI Server | Uvicorn | ≥0.32 | Production HTTP server |
| Database | PostgreSQL 16 | — | Primary data store (plain, no extensions) |
| Async DB Driver | asyncpg | ≥0.30 | Non-blocking PostgreSQL |
| ORM | SQLAlchemy | ≥2.0 | Async models + queries |
| Migrations | Alembic | ≥1.14 | Schema versioning |
| LLM Provider | Groq API | — | llama-3.3-70b-versatile |
| Embeddings | BAAI/bge-base-en-v1.5 | — | 768-dim semantic embeddings |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | — | Result reranking |
| PII Detection | Microsoft Presidio | ≥2.2 | Entity recognition + anonymization |
| NLP Backend | spaCy | ≥3.7 | en_core_web_sm model |
| PDF Parsing | PyMuPDF | ≥1.25 | Text extraction from PDFs |
| Encryption | Fernet (cryptography) | ≥44.0 | Symmetric authenticated encryption |
| Password Hashing | bcrypt (passlib) | ≥1.7 | Secure password storage |
| Auth Tokens | python-jose | ≥3.3 | JWT generation + validation |
| Rate Limiting | slowapi | — | 3 verdict req/hour/IP |
| Logging | structlog | — | Structured JSON logs |
| Background Tasks | FastAPI BackgroundTasks | — | Async doc processing (no Redis) |
| Frontend | React 18 + TypeScript | — | Single-page application |
| Build Tool | Vite | — | Fast frontend bundler |
| Styling | Tailwind CSS | — | Utility-first CSS |
| Routing | React Router v6 | — | Client-side routing |

---

## 3. High-Level Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                     AI LEGAL ARBITRATION SYSTEM v2                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

  ┌─────────────────────────────────────────────────────────────────────────┐
  │                     FRONTEND (React 18 + Vite)                           │
  │                       http://localhost:5173                              │
  │                                                                          │
  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐ ┌───────┐  │
  │  │  Login / │ │  Cases   │ │  Case    │ │ ArbitrationRoom  │ │Verdict│  │
  │  │  Register│ │  List    │ │  Detail  │ │  (SSE live view) │ │ Page  │  │
  │  └──────────┘ └──────────┘ └──────────┘ └─────────────────┘ └───────┘  │
  └────────────────────────┬────────────────────────────┬────────────────────┘
                           │  HTTP/REST (JWT Bearer)     │  SSE (?token=)
                           ▼                            ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                     BACKEND (FastAPI + Uvicorn)                          │
  │                       http://localhost:8000                              │
  │                                                                          │
  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
  │  │  /auth   │ │ /cases   │ │/documents│ │/verdicts │ │ /arbitration │  │
  │  │ router   │ │  router  │ │  router  │ │  router  │ │ /stream (SSE)│  │
  │  └──────────┘ └──────────┘ └──────────┘ └────┬─────┘ └──────┬───────┘  │
  │                                               │              │           │
  │                              ┌────────────────┼──────────────┘           │
  │                              ▼                ▼                          │
  │             ┌─────────────────────────────────────────────────┐         │
  │             │         ArbitrationOrchestrator                  │         │
  │             │         (7-stage pipeline + SSE broadcast)       │         │
  │             └─────────────────────────────────────────────────┘         │
  │                              │                                           │
  │     ┌────────────────────────┼────────────────────────┐                 │
  │     ▼                        ▼                        ▼                 │
  │ ┌──────────────┐  ┌─────────────────────┐  ┌───────────────────────┐   │
  │ │ core/security│  │  BackgroundTasks     │  │    RAG Layer (v2)     │   │
  │ │ JWT, Fernet, │  │  process_document()  │  │  BGE 768-dim embeds   │   │
  │ │ bcrypt, SHA  │  │  (PDF→chunk→embed)   │  │  CrossEncoder rerank  │   │
  │ └──────────────┘  └─────────────────────┘  │  CitationTracker      │   │
  │                                             │  QueryExpander        │   │
  │                                             └───────────────────────┘   │
  └─────────────────────────────────────────────────────┬───────────────────┘
                                                        │
                           ┌────────────────────────────┤
                           ▼                            ▼
  ┌──────────────────────────────┐       ┌─────────────────────────┐
  │      PostgreSQL 16           │       │      Groq Cloud API      │
  │  (asyncpg + SQLAlchemy 2.0)  │       │  llama-3.3-70b-versatile │
  │                              │       │  (7–14 calls/verdict)    │
  │  users                       │       └─────────────────────────┘
  │  cases
  │  documents
  │  document_chunks  (JSONB 768-dim)
  │  pii_mappings
  │  pii_audit_logs
  │  verdicts          (v2 + confidence/grounding/bias)
  │  arbitration_stages (7 rows per case)
  │  audit_logs
  └──────────────────────────────┘
```

---

## 4. Directory Structure

```
legal_arbitration/
│
├── app/
│   ├── main.py                            # FastAPI init, CORS, routers, rate limiter, body limit
│   ├── config.py                          # Pydantic Settings (reads .env)
│   ├── database.py                        # Async SQLAlchemy engine, AsyncSessionLocal
│   │
│   ├── agents/                            # Multi-agent AI system
│   │   ├── base_agent.py                  # Groq client, retry logic, JSON parsing, token logging
│   │   ├── party_agent.py                 # Stage 1: Claimant / Respondent summaries
│   │   ├── evidence_comparison_agent.py   # Stage 2: SUPPORTED / NOT_FOUND / CONTRADICTED
│   │   ├── contradiction_detection_agent.py  # Stage 3a: Contradictions + agreed facts
│   │   ├── witness_consistency_agent.py   # Stage 3b: Consistency scores per party
│   │   ├── legal_argument_agent.py        # Stage 4a: Indian statute citations
│   │   ├── liability_reasoning_agent.py   # Stage 4b: Liability split %
│   │   ├── compensation_calculation_agent.py  # Stage 5a: Total award INR
│   │   ├── settlement_recommendation_agent.py # Stage 5b: Settlement range
│   │   ├── bias_conflict_agent.py         # Stage 6: Neutrality score 0–1
│   │   ├── chief_judge_agent.py           # Stage 7: Final verdict + confidence score
│   │   └── orchestrator.py               # Pipeline runner, stage DB tracking, SSE broadcast
│   │
│   ├── core/
│   │   ├── security.py                    # JWT (access+refresh), Fernet, bcrypt, SHA-256
│   │   ├── logging.py                     # Structured JSON logging (structlog)
│   │   ├── chunker.py                     # Semantic PDF chunking (paragraph/section)
│   │   ├── pdf_parser.py                  # PyMuPDF text extraction
│   │   └── pii_processor.py               # Presidio + custom Indian PII recognizers
│   │
│   ├── models/
│   │   ├── user.py                        # User (email_encrypted, email_hash, role)
│   │   ├── case.py                        # Case (status enum, party_a/b, invite_token)
│   │   ├── document.py                    # Document (content_encrypted, content_anonymized)
│   │   ├── embedding.py                   # DocumentChunk (768-dim JSONB, section_header, chunk_type)
│   │   ├── verdict.py                     # Verdict (v2: confidence_score, grounding_report, bias_report)
│   │   ├── arbitration_stage.py           # ArbitrationStage (7 per case, status, output_json)
│   │   └── audit_log.py                   # AuditLog (compliance trail)
│   │
│   ├── rag/
│   │   ├── embeddings.py                  # BAAI/bge-base-en-v1.5 (768-dim)
│   │   ├── query_expander.py              # Legal synonym + statute query expansion
│   │   ├── reranker.py                    # CrossEncoder ms-marco reranker
│   │   ├── citation_tracker.py            # CitationTracker → GroundingReport
│   │   └── retriever.py                   # 5-layer RAG: embed → filter → rerank → cite
│   │
│   ├── routers/
│   │   ├── auth.py                        # /auth/register, /auth/login, /auth/refresh
│   │   ├── cases.py                       # /cases CRUD + /cases/{id}/join
│   │   ├── documents.py                   # /cases/{id}/documents upload + retry
│   │   ├── verdicts.py                    # /cases/{id}/verdict + stages + grounding + bias
│   │   └── arbitration_stream.py          # /cases/{id}/arbitration/stream (SSE, token via QS)
│   │
│   ├── schemas/
│   │   ├── auth.py                        # RegisterRequest, TokenResponse, RefreshTokenRequest
│   │   ├── case.py                        # CaseCreateRequest, CaseResponse, JoinCaseRequest
│   │   ├── document.py                    # DocumentUploadResponse, DocumentResponse
│   │   ├── verdict.py                     # VerdictResponse (v2 fields)
│   │   └── arbitration.py                 # StageResponse, StagesListResponse, StageDetailResponse
│   │
│   └── tasks/
│       └── document_tasks.py              # process_document(): PDF → semantic chunk → BGE embed
│
├── alembic/
│   └── versions/
│       ├── 001_initial_schema.py          # Base tables (users, cases, documents, chunks, verdicts)
│       └── 002_v2_columns_and_tables.py   # v2: chunk columns, verdict columns, arbitration_stages, audit_logs
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Login.tsx                  # Login + Register
│       │   ├── Cases.tsx                  # Case list
│       │   ├── CaseDetail.tsx             # Case detail + doc upload + verdict trigger
│       │   ├── ArbitrationRoom.tsx        # Live SSE pipeline viewer (NEW)
│       │   └── Verdict.tsx               # Final verdict display (with polling)
│       ├── components/
│       │   ├── VerdictCard.tsx            # Verdict render (claims/defences as objects)
│       │   ├── StatusBadge.tsx
│       │   └── UploadDropzone.tsx
│       ├── context/AuthContext.tsx
│       └── api/client.ts
│
├── requirements.txt
├── .env.example
├── CLAUDE.md
├── ARCHITECTURE.md                        # This file
└── CHANGES.md
```

---

## 5. Database Schema

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE: legal_arbitration                           │
└──────────────────────────────────────────────────────────────────────────────┘

users
  id VARCHAR(36) PK
  email_encrypted BYTEA          — Fernet-encrypted
  email_hash VARCHAR(64) UQ      — SHA-256, for O(1) login lookup
  hashed_password VARCHAR(255)   — bcrypt
  full_name_encrypted BYTEA
  role ENUM(PARTY_A, PARTY_B)
  created_at TIMESTAMPTZ

cases
  id VARCHAR(36) PK
  title VARCHAR(500)
  description TEXT
  case_type ENUM(CONTRACT, CONSUMER, PROPERTY, COMPANY)
  status ENUM(OPEN, PARTY_A_FILED, PARTY_B_RESPONDED, IN_ARBITRATION, VERDICT_DELIVERED)
  party_a_id FK→users
  party_b_id FK→users (nullable)
  party_b_invite_email_hash VARCHAR(64)
  party_b_invite_token VARCHAR(64)
  created_at TIMESTAMPTZ
  updated_at TIMESTAMPTZ

documents
  id VARCHAR(36) PK
  case_id FK→cases
  uploader_id FK→users
  filename VARCHAR(500)
  content_encrypted BYTEA        — Fernet-encrypted PDF
  content_anonymized TEXT        — PII-replaced text sent to LLM
  original_size_bytes INTEGER
  processing_status ENUM(PENDING, PROCESSING, DONE, FAILED)
  error_message TEXT
  uploaded_at TIMESTAMPTZ
  processed_at TIMESTAMPTZ

document_chunks                  — BGE 768-dim embeddings (no pgvector)
  id VARCHAR(36) PK
  document_id FK→documents
  case_id FK→cases
  chunk_index INTEGER
  chunk_text TEXT                — anonymized chunk content
  embedding JSONB                — [float × 768]
  section_header TEXT            — detected section heading (nullable)
  chunk_type VARCHAR(50)         — "paragraph" | "header"
  token_count INTEGER
  page_numbers JSONB             — [1, 2, ...]
  document_filename VARCHAR(500)
  created_at TIMESTAMPTZ

pii_mappings
  id VARCHAR(36) PK
  document_id FK→documents
  token VARCHAR(50)              — e.g. "PERSON_1", "AADHAAR_2"
  entity_type VARCHAR(50)        — e.g. "AADHAAR_NUMBER", "PAN_NUMBER"
  encrypted_value BYTEA          — Fernet-encrypted original value
  created_at TIMESTAMPTZ

pii_audit_logs
  id VARCHAR(36) PK
  document_id FK→documents
  entity_type VARCHAR(50)
  count_found INTEGER
  processing_time_ms INTEGER
  created_at TIMESTAMPTZ

verdicts
  id VARCHAR(36) PK
  case_id FK→cases UNIQUE
  agent_a_summary TEXT           — JSON: claimant PartyAgent output
  agent_b_summary TEXT           — JSON: respondent PartyAgent output
  judge_reasoning TEXT           — ChiefJudgeAgent deliberation text
  verdict_text TEXT              — "IN FAVOUR OF CLAIMANT" | "RESPONDENT" | "PARTIAL AWARD" | "DISMISSED"
  applicable_laws JSONB          — ["Indian Contract Act 1872, Section 73", ...]
  relief_awarded TEXT            — JSON string: {type, amount_inr, description, interest, costs}
  confidence_score FLOAT         — 0.0–1.0 (ChiefJudgeAgent)
  grounding_report JSONB         — CitationTracker output
  bias_report JSONB              — BiasConflictAgent output
  settlement_recommendation JSONB
  compensation_breakdown JSONB
  stage_count INTEGER            — always 7
  total_groq_tokens INTEGER
  total_duration_ms INTEGER
  created_at TIMESTAMPTZ

arbitration_stages               — 7 rows per case (one per pipeline stage)
  id VARCHAR(36) PK
  case_id FK→cases
  stage_number INTEGER           — 1–7
  stage_name VARCHAR(100)        — e.g. "party_analysis"
  status ENUM(PENDING, RUNNING, COMPLETED, FAILED, SKIPPED)
  agent_name VARCHAR(100)        — e.g. "PartyAgent"
  input_summary TEXT
  output_json JSONB              — full stage context (except raw docs)
  output_summary TEXT            — human-readable stage result
  citations JSONB
  error_message TEXT
  started_at TIMESTAMPTZ
  completed_at TIMESTAMPTZ
  duration_ms INTEGER
  groq_tokens_used INTEGER
  created_at TIMESTAMPTZ

audit_logs                       — compliance trail
  id VARCHAR(36) PK
  user_id VARCHAR(36)
  case_id VARCHAR(36)
  action VARCHAR(100)
  resource_type VARCHAR(100)
  resource_id VARCHAR(36)
  details JSONB
  ip_address VARCHAR(50)
  created_at TIMESTAMPTZ
```

---

## 6. Data Flow: Document Processing Pipeline

```
  User uploads PDF → POST /cases/{case_id}/documents
           │
           ▼
  documents.py router
    1. Validate: PDF only, ≤20 MB, case access check
    2. encrypt_bytes(pdf_bytes)  →  Fernet ciphertext
    3. INSERT document row (status=PENDING)
    4. Update case status (OPEN→PARTY_A_FILED or PARTY_A_FILED→PARTY_B_RESPONDED)
    5. background_tasks.add_task(process_document, doc_id)
    6. Return 201 immediately
           │ (async background)
           ▼
  document_tasks.process_document(doc_id)
    │
    ├─ Step 1: Fetch doc from DB, UPDATE status=PROCESSING
    ├─ Step 2: decrypt_bytes() → raw PDF bytes
    ├─ Step 3: PyMuPDF extract text per page
    ├─ Step 4: Semantic chunking (chunker.py)
    │           - Detect paragraph/section boundaries
    │           - Preserve section headers
    │           - Output: list[SemanticChunk] with type, page_numbers, token_count
    ├─ Step 5: Presidio PII detection on full_text
    │           - Custom recognizers: AADHAAR_NUMBER, PAN_NUMBER, IN_PHONE_NUMBER, BANK_ACCOUNT
    │           - Replace with stable tokens: PERSON_1, AADHAAR_2, etc.
    │           - Encrypt originals → INSERT pii_mappings
    │           - INSERT pii_audit_logs per entity_type
    ├─ Step 6: doc.content_anonymized = anonymized_text
    ├─ Step 7: get_embeddings(chunk_texts) via BAAI/bge-base-en-v1.5 (768-dim)
    ├─ Step 8: INSERT document_chunks(chunk_text, embedding, section_header, chunk_type, ...)
    └─ Step 9: UPDATE document status=DONE, processed_at=now()

  On error → UPDATE status=FAILED, error_message=...
```

---

## 7. Agentic Flow: 7-Stage Arbitration Pipeline

```
  POST /cases/{case_id}/verdict
    → validates case status, all docs DONE, both parties filed
    → UPDATE case.status = IN_ARBITRATION
    → background_tasks.add_task(_run_orchestrator, case_id, claimant_text, respondent_text)
    → return 202 immediately


  ╔══════════════════════════════════════════════════════════════════════════╗
  ║           ArbitrationOrchestrator.run()  — 7-Stage Pipeline             ║
  ║     Each stage: INSERT arbitration_stage row → run → UPDATE + broadcast ║
  ╚══════════════════════════════════════════════════════════════════════════╝

  ┌──────────────────────────────────────────────────────────────────────────┐
  │ STAGE 1 — Party Analysis                                                 │
  │ Agents : PartyAgent × 2  (run in parallel via asyncio.gather)            │
  │                                                                          │
  │  claimant_docs ──► PartyAgent("CLAIMANT") ──► claimant_summary:          │
  │  {                                                                       │
  │    role: "CLAIMANT",                                                     │
  │    claims: [{claim, evidence_basis, strength: STRONG|MODERATE|WEAK}],   │
  │    facts: [...],                                                         │
  │    relief_sought: "INR 45,00,000 compensation",                          │
  │    applicable_laws: ["Employees' Compensation Act", ...],                │
  │    overall_strength_assessment: "STRONG"                                 │
  │  }                                                                       │
  │                                                                          │
  │  respondent_docs ──► PartyAgent("RESPONDENT") ──► respondent_summary:    │
  │  {                                                                       │
  │    role: "RESPONDENT",                                                   │
  │    defences: [{defence, evidence_basis, strength}],                      │
  │    counter_claims: [...],                                                │
  │    disputed_facts: [...],                                                │
  │    overall_strength_assessment: "MODERATE"                               │
  │  }                                                                       │
  │                                                                          │
  │  SSE broadcast: stage_started → stage_completed                          │
  └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ STAGE 2 — Evidence Comparison                                            │
  │ Agent  : EvidenceComparisonAgent                                         │
  │                                                                          │
  │  Input : claimant_summary + respondent_summary + RAG evidence_chunks     │
  │          (retrieve_relevant_chunks query: "breach payment delivery")     │
  │                                                                          │
  │  Output: evidence_map:                                                   │
  │  {                                                                       │
  │    total_claims_analyzed: N,                                             │
  │    supported_count: N,                                                   │
  │    not_found_count: N,                                                   │
  │    contradicted_count: N,                                                │
  │    evidence_assessment: [                                                │
  │      {claim, verdict: SUPPORTED|NOT_FOUND|CONTRADICTED, evidence_refs}  │
  │    ]                                                                     │
  │  }                                                                       │
  └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ STAGE 3 — Contradiction & Consistency Check                              │
  │ Agents : ContradictionDetectionAgent + WitnessConsistencyAgent × 2      │
  │          (run in parallel via asyncio.gather)                            │
  │                                                                          │
  │  ContradictionDetectionAgent                                             │
  │    Input : claimant_summary + respondent_summary + evidence_map          │
  │    Output: {                                                             │
  │      contradictions: [{issue, claimant_position, respondent_position}], │
  │      agreed_facts: [...],                                                │
  │      contradiction_count: N,                                             │
  │      agreed_fact_count: N                                                │
  │    }                                                                     │
  │                                                                          │
  │  WitnessConsistencyAgent("CLAIMANT")                                     │
  │  WitnessConsistencyAgent("RESPONDENT")                                   │
  │    Output: { consistency_score: 0.0–1.0, inconsistencies: [...] }       │
  └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ STAGE 4 — Legal Reasoning                                                │
  │ Agents : LegalArgumentAgent → LiabilityReasoningAgent  (sequential)     │
  │                                                                          │
  │  LegalArgumentAgent                                                      │
  │    Input : contradiction_report + evidence_map + both summaries          │
  │    Output: legal_analysis:                                               │
  │    {                                                                     │
  │      legal_issues: [                                                     │
  │        {issue, applicable_statute, section, relevance, party_favored}   │
  │      ],                                                                  │
  │      claimant_legal_strength: STRONG|MODERATE|WEAK,                     │
  │      respondent_legal_strength: STRONG|MODERATE|WEAK                    │
  │    }                                                                     │
  │                                                                          │
  │  LiabilityReasoningAgent                                                 │
  │    Input : legal_analysis + contradiction_report                         │
  │    Output: liability_determination:                                      │
  │    {                                                                     │
  │      primary_liability: "RESPONDENT",                                   │
  │      liability_split: {claimant_pct: 20, respondent_pct: 80},           │
  │      reasoning: "..."                                                    │
  │    }                                                                     │
  │                                                                          │
  │  Indian statutes the agents apply:                                       │
  │    Arbitration and Conciliation Act, 1996                                │
  │    Indian Contract Act, 1872                                             │
  │    Employees' Compensation Act, 1923                                     │
  │    Consumer Protection Act, 2019                                         │
  │    Transfer of Property Act, 1882                                        │
  │    Specific Relief Act, 1963                                             │
  │    Factories Act, 1948                                                   │
  │    Indian Evidence Act, 1872                                             │
  └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ STAGE 5 — Resolution & Compensation                                      │
  │ Agents : CompensationCalculationAgent + SettlementRecommendationAgent   │
  │          (run in parallel via asyncio.gather)                            │
  │                                                                          │
  │  CompensationCalculationAgent                                            │
  │    Input : liability_determination + evidence_chunks + claimant_summary  │
  │    Output: compensation_breakdown:                                       │
  │    {                                                                     │
  │      compensatory_damages: INR,                                          │
  │      punitive_damages: INR,                                              │
  │      special_damages: INR,                                               │
  │      total_award: INR,                                                   │
  │      basis: "..."                                                        │
  │    }                                                                     │
  │                                                                          │
  │  SettlementRecommendationAgent                                           │
  │    Output: {                                                             │
  │      settlement_recommended: true|false,                                 │
  │      recommendation_strength: STRONG|MODERATE|WEAK,                     │
  │      recommended_settlement_range: {minimum_inr, maximum_inr},          │
  │      terms: [...]                                                        │
  │    }                                                                     │
  └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ STAGE 6 — Bias & Neutrality QA                                           │
  │ Agent  : BiasConflictAgent                                               │
  │                                                                          │
  │  Input : full pipeline context                                           │
  │  Output: bias_report:                                                    │
  │  {                                                                       │
  │    overall_bias_score: 0.0–1.0,   (0=neutral, 1=heavily biased)         │
  │    bias_level: MINIMAL|LOW|MODERATE|HIGH,                                │
  │    evidence_balance: {claimant_cited, respondent_cited, balance_ratio}, │
  │    flags: [...],                                                         │
  │    passed: true|false,            (threshold: score < 0.3)              │
  │    recommendation: "..."                                                 │
  │  }                                                                       │
  └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ STAGE 7 — Final Verdict                                                  │
  │ Agent  : ChiefJudgeAgent                                                 │
  │                                                                          │
  │  Input : entire pipeline context (all 6 prior outputs)                  │
  │  Output: final_verdict:                                                  │
  │  {                                                                       │
  │    verdict: "IN FAVOUR OF CLAIMANT|RESPONDENT|PARTIAL AWARD|DISMISSED", │
  │    reasoning: "Multi-paragraph legal reasoning...",                      │
  │    applicable_laws: ["Indian Contract Act 1872, Section 73", ...],      │
  │    liability_determination: "RESPONDENT liable for material breach",    │
  │    relief_awarded: {                                                     │
  │      type: "MONETARY",                                                   │
  │      amount_inr: "25,00,000",                                            │
  │      description: "...",                                                 │
  │      interest: "6% per annum from date of accident",                    │
  │      costs: "Litigation costs ₹50,000 to Claimant"                      │
  │    },                                                                    │
  │    confidence_score: 0.0–1.0,                                           │
  │    bias_attestation: "Bias check PASSED, score 0.08"                    │
  │  }                                                                       │
  │                                                                          │
  │  Post-verdict:                                                           │
  │    CitationTracker.verify_grounding(final_verdict, evidence_chunks)      │
  │    → GroundingReport { overall_score, grounded_claims, citations[] }    │
  │                                                                          │
  │  SSE broadcast: verdict_ready { verdict, confidence }                   │
  └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
  Persist to DB:
    INSERT verdicts (all v2 fields)
    UPDATE case.status = VERDICT_DELIVERED
    COMMIT


  ══════════════════════════════════════════════════════════════════
  BaseAgent (base_agent.py) — shared by ALL 10 agents above
  ══════════════════════════════════════════════════════════════════
    - Groq client singleton (llama-3.3-70b-versatile, temp=0.2)
    - Exponential backoff retry on 429 (rate limit) or 5xx
    - _parse_json_response(): strip markdown fences, json.loads()
    - Logs: agent name, token count, duration_ms, attempt number
```

---

## 8. RAG Pipeline (v2)

```
  ═══════════════════════════════════════════════════════════
  INDEXING — during document_tasks.process_document()
  ═══════════════════════════════════════════════════════════

  anonymized_text
       │
       ▼
  SemanticChunker (chunker.py)
       │  - Split at paragraph/section boundaries
       │  - Detect section headers (headings, bold text)
       │  - Assign chunk_type: "paragraph" | "header"
       │  - Track page_numbers, token_count
       ▼
  BAAI/bge-base-en-v1.5  (sentence-transformers)
       │  encode(texts, normalize_embeddings=True)
       │  → list[list[float]]  (768-dim L2-normalized)
       ▼
  INSERT document_chunks(chunk_text, embedding JSONB,
                          section_header, chunk_type, ...)


  ═══════════════════════════════════════════════════════════
  RETRIEVAL — during Stage 2 (EvidenceComparisonAgent)
               and Stage 7 (ChiefJudgeAgent grounding)
  ═══════════════════════════════════════════════════════════

  retrieve_relevant_chunks(query, case_id, top_k=15)
       │
       ├─ Layer 1: QueryExpander (query_expander.py)
       │     - Expand legal synonyms
       │     - Add related statute references
       │     - Generate 3–5 expanded queries
       │
       ├─ Layer 2: Dense Retrieval
       │     get_embedding(expanded_query) → 768-dim vector
       │     SELECT all document_chunks WHERE case_id=:case_id
       │     cosine_similarity(query_vec, chunk_vec) for each
       │     Sort DESC, take top 30 candidates
       │
       ├─ Layer 3: CrossEncoder Reranking (reranker.py)
       │     cross-encoder/ms-marco-MiniLM-L-6-v2
       │     predict([(query, chunk_text), ...]) → scores
       │     Re-sort by rerank score, take top_k=15
       │
       ├─ Layer 4: CitationTracker (citation_tracker.py)
       │     Tag each chunk with document_filename, page_numbers
       │     Track which chunks are actually cited in verdicts
       │
       └─ Layer 5: GroundingReport
             overall_score: fraction of verdict claims grounded
             grounded_claims: [...matched chunks...]
             passed: bool (threshold: score >= 0.5)
```

---

## 9. SSE Real-Time Streaming

```
  GET /cases/{case_id}/arbitration/stream?token=<jwt>
       │
       │  (EventSource cannot set Authorization headers,
       │   so JWT is passed as query param)
       │
       ▼
  arbitration_stream.py
    decode_token(token) → user_id
    subscribe_to_case(case_id) → asyncio.Queue
    StreamingResponse(event_generator(), media_type="text/event-stream")

  orchestrator.py broadcasts via _broadcast(case_id, event_type, data):
    _sse_queues: dict[case_id → list[asyncio.Queue]]

  Events emitted:
  ┌───────────────────┬─────────────────────────────────────────────────────┐
  │ Event Type        │ Data Payload                                         │
  ├───────────────────┼─────────────────────────────────────────────────────┤
  │ stage_started     │ {stage_number, stage_name, message}                  │
  │ stage_completed   │ {stage_number, stage_name, summary, duration_ms}     │
  │ stage_failed      │ {stage_number, stage_name, error}                    │
  │ verdict_ready     │ {verdict, confidence}                                │
  └───────────────────┴─────────────────────────────────────────────────────┘
  Keep-alive: ": ping\n\n"  every 30 seconds (asyncio.wait_for timeout)

  Frontend (ArbitrationRoom.tsx):
    new EventSource(url)
    addEventListener("stage_started") → set stage status=running, pulse anim
    addEventListener("stage_completed") → show summary text, fill progress bar
    addEventListener("verdict_ready") → show banner, navigate to /verdict after 2.5s
    On disconnect → es.close()
```

---

## 10. Security Architecture

```
  LAYER 1: Transport
    CORS: localhost:5173 and localhost:3000 only
    Bearer token required on all protected routes
    Body size limit enforced in main.py

  LAYER 2: Authentication (v2 — access + refresh tokens)
    Registration:
      email  ──► SHA-256 hash ──► email_hash (DB lookup key)
      email  ──► Fernet encrypt ──► email_encrypted
      name   ──► Fernet encrypt ──► full_name_encrypted
      pwd    ──► bcrypt hash ──────► hashed_password
      → returns {access_token (60min), refresh_token (7 days)}

    Login:
      email ──► SHA-256 ──► DB lookup by email_hash
      password ──► bcrypt.verify(input, stored)
      success ──► JWT { sub: user_id, role, exp }

    Token Refresh (POST /auth/refresh):
      refresh_token ──► decode ──► new access_token

  LAYER 3: Data Encryption
    Fernet (AES-128-CBC + HMAC-SHA256):
      PDF bytes ──► encrypt_bytes() ──► BYTEA in documents
      PII values ──► encrypt() ──► BYTEA in pii_mappings
      Email + name ──► encrypt() ──► BYTEA in users

  LAYER 4: PII Protection (before ANY text reaches Groq)
    "Vidhi Gupta — Aadhaar 1234 5678 9012 — PAN ABCDE1234F"
    ─────────────────────────────────────────────────────────
    "[PERSON_1] — Aadhaar [AADHAAR_NUMBER_1] — PAN [PAN_NUMBER_1]"

    Custom Indian recognizers:
      AADHAAR_NUMBER  — 12-digit format (4-4-4)
      PAN_NUMBER      — ABCDE1234F pattern
      IN_PHONE_NUMBER — 10-digit, +91/91/0 prefix
      BANK_ACCOUNT    — 9–18 digit context-aware

  LAYER 5: Authorization
    Case access: party_a_id == user_id OR party_b_id == user_id
    Only PARTY_A can create cases
    Only PARTY_B can join cases (role + invite token)
    Anonymous content only shown to uploader of that document

  LAYER 6: Rate Limiting
    slowapi: 3 verdict requests per hour per IP
    429 Too Many Requests returned when exceeded
```

---

## 11. API Endpoints

```
  BASE URL: http://localhost:8000

  Auth
  ────
  POST  /auth/register                    Register new user (PARTY_A or PARTY_B)
  POST  /auth/login                       Login → {access_token, refresh_token}
  POST  /auth/refresh                     Exchange refresh_token → new access_token

  Cases
  ─────
  POST  /cases/                           Create dispute case (PARTY_A only)
  GET   /cases/                           List user's cases
  GET   /cases/{case_id}                  Get case details
  POST  /cases/{case_id}/join             Join case with invite token (PARTY_B)

  Documents
  ─────────
  POST  /cases/{case_id}/documents              Upload PDF evidence
  GET   /cases/{case_id}/documents              List documents
  POST  /cases/{case_id}/documents/{doc_id}/retry  Retry FAILED document

  Verdict & Pipeline
  ──────────────────
  POST  /cases/{case_id}/verdict                Trigger 7-stage pipeline (202)
  GET   /cases/{case_id}/verdict                Fetch full verdict (404 until ready)
  GET   /cases/{case_id}/verdict/grounding      Grounding verification report
  GET   /cases/{case_id}/verdict/bias           Bias/neutrality report

  Stages
  ──────
  GET   /cases/{case_id}/arbitration/stages     All 7 stage statuses
  GET   /cases/{case_id}/arbitration/stages/{n} Single stage detail + output_json
  POST  /cases/{case_id}/arbitration/resume     Resume from last FAILED stage
  GET   /cases/{case_id}/arbitration/stream     SSE stream (?token=<jwt>)

  System
  ──────
  GET   /health                                 Deep health check (DB + embedding model)

  API Docs: http://localhost:8000/docs
```

---

## 12. Case State Machine

```
                   Party A creates case
                          │
                          ▼
                    ┌──────────┐
                    │   OPEN   │
                    └────┬─────┘
                         │ Party A uploads first document
                         ▼
               ┌──────────────────┐
               │  PARTY_A_FILED   │
               └────────┬─────────┘
                        │ Party B joins + uploads first document
                        ▼
           ┌──────────────────────────┐
           │   PARTY_B_RESPONDED      │◄── "Trigger AI Verdict" button appears
           └────────────┬─────────────┘
                        │ POST /cases/{id}/verdict
                        ▼
            ┌──────────────────────────┐
            │     IN_ARBITRATION       │◄── "Watch Live Pipeline →" button
            │  (7-stage pipeline runs) │     ArbitrationRoom SSE active
            └────────────┬─────────────┘
                         │ orchestrator_completed
                         ▼
         ┌────────────────────────────────┐
         │      VERDICT_DELIVERED         │  terminal state
         │   "View Verdict" button shown  │
         └────────────────────────────────┘

  Rules:
  • Only PARTY_A (role) can create cases
  • Only PARTY_B (role) can join cases (invite token required)
  • Documents cannot be uploaded after VERDICT_DELIVERED
  • Verdict cannot be triggered until PARTY_B_RESPONDED
  • Verdict cannot be re-triggered after VERDICT_DELIVERED
  • All documents must be status=DONE before verdict triggers
  • Idempotency: 409 if a stage is already RUNNING
```

---

## 13. Frontend Page Flow

```
  /login
    Register (PARTY_A or PARTY_B) or Login
    → stores {token, userId, role} in AuthContext
    → navigate to /cases

  /cases
    List all cases for the logged-in user
    Party A: "New Case" button → POST /cases
    → navigate to /cases/{id}

  /cases/{id}  (CaseDetail)
    Shows: case info, invite token (if no Party B yet), documents
    Upload PDF via drag-and-drop (UploadDropzone)
    Polls every 5s while any doc is PENDING/PROCESSING
    Status transitions shown as StatusBadge components

    Buttons (conditional on case.status):
      PARTY_B_RESPONDED  → "Trigger AI Verdict"
                           POST /verdict → navigate to /cases/{id}/arbitration
      IN_ARBITRATION     → "Watch Live Pipeline →"
                           navigate to /cases/{id}/arbitration
      VERDICT_DELIVERED  → "View Verdict" + "View Pipeline"

  /cases/{id}/arbitration  (ArbitrationRoom)  ← NEW in v2
    Dark-themed live deliberation room
    Left panel:   Claimant claims (fills after stage 1 completes)
    Center:       7-stage pipeline tracker
                  - Progress bar (completed/7)
                  - Stage cards: pending=grey, running=pulse+bounce, done=green
                  - Running stage shows description as italic pulse text
                  - Completed stage shows summary + duration
                  - Legal issues panel appears after stage 4
                  - Tentative award amount appears after stage 5
                  - "Verdict Delivered!" banner → auto-redirect to /verdict
    Right panel:  Respondent defences + live agent activity log (timestamped)
    SSE:          EventSource(?token=jwt) → real-time updates

  /cases/{id}/verdict  (Verdict)
    Polls GET /cases/{id}/verdict every 4s until 200 (handles 404 during pipeline)
    Shows: VerdictCard with:
      - Verdict banner (color-coded: green/red/amber/grey)
      - Award amount, description, interest, costs
      - Applicable Indian laws
      - Judge's reasoning (whitespace-preserved)
      - Claimant claims list (with STRONG/MODERATE/WEAK badges)
      - Respondent defences list (with strength badges)
```

---

## 14. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **7-stage pipeline** | Specialized agents per task | Each agent has a narrower prompt, improving JSON reliability and legal quality |
| **asyncio.gather for parallel agents** | Stage 1, 3, 5 | Cuts pipeline time by ~40% vs sequential; Groq 429s handled by backoff |
| **Per-stage DB rows** | arbitration_stages table | Resume from FAILED stage without re-running completed work; audit trail |
| **SSE for live updates** | StreamingResponse + asyncio.Queue | No WebSocket overhead; works with browser EventSource; keep-alive pings |
| **SSE token via query param** | ?token= | Browser EventSource API cannot set Authorization headers |
| **BGE-base 768-dim** | BAAI/bge-base-en-v1.5 | Better legal domain retrieval than all-MiniLM (384-dim); still CPU-feasible |
| **CrossEncoder reranking** | ms-marco-MiniLM-L-6-v2 | Dramatically improves precision of top-k chunks sent to agents |
| **QueryExpander** | Legal synonym expansion | Retrieves statute-relevant chunks even when query uses colloquial phrasing |
| **CitationTracker** | Grounding verification | Verifiable evidence link between verdict claims and source document chunks |
| **BiasConflictAgent as Stage 6** | Neutrality gate before final verdict | Catches systematic bias before ChiefJudgeAgent synthesizes the award |
| **Confidence score on verdict** | ChiefJudgeAgent outputs 0–1 | Parties can see how certain the AI is; flags low-confidence cases |
| **relief_awarded as JSON string** | TEXT column, JSON.stringify | Preserves backward compatibility with TEXT column while storing structured data |
| **Refresh tokens** | 7-day refresh + 60-min access | Avoids repeated logins in long arbitration sessions |
| **Semantic chunking** | paragraph/section boundaries | Preserves legal clause integrity vs character-level splits |
| **No Redis/Celery** | FastAPI BackgroundTasks | Zero extra infrastructure; sufficient for single-server deployments |
| **No pgvector** | JSONB + numpy cosine | No PostgreSQL extension needed; simpler setup; CrossEncoder compensates |
| **Rate limiting** | slowapi 3/hour/IP on verdict | Prevents pipeline abuse; Groq TPM limits make this necessary |
| **Temperature 0.2** | Low randomness | Deterministic legal reasoning across all 10 agents |
| **Stable PII tokens** | PERSON_1, AADHAAR_2 | Consistent cross-document references; LLM never sees real identity data |
