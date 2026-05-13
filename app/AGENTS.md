# AGENTS.md — app/

## Purpose
The FastAPI backend application package. This is the Python package root for the entire backend. Contains the application entry point (`main.py`), configuration (`config.py`), database setup (`database.py`), and all sub-packages.

## Files

### `main.py`
FastAPI application factory and entry point.

**Current state:**
```python
app = FastAPI(title="AI Legal Arbitration System", version="1.0.0")

# Middleware
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Routers
app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(documents.router)
app.include_router(verdicts.router)

# Lifespan: disposes SQLAlchemy engine on shutdown
```

**Health check:**
```
GET /health → {"status": "ok"}
```
Currently shallow (does not verify PostgreSQL or Groq API connectivity). The planned deep health check (see CHANGES.md) also pings the DB and Groq API.

**What still needs to be added to `main.py`:**
- Rate limiter registration (`app.state.limiter = limiter`)
- Rate limit exception handler
- SSE router (`arbitration_stream.router`)
- Body size limit middleware (25 MB cap)
- Structured logging setup (`setup_logging()` from `app.core.logging`)
- BGE model warm-up in lifespan (to avoid cold-start blocking)

### `config.py`
Pydantic `Settings` class — reads all configuration from `.env` file.

**Settings:**
| Variable | Description |
|---|---|
| `database_url` | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `groq_api_key` | Groq API key (from console.groq.com) |
| `groq_model` | LLM model name (default: `llama-3.3-70b-versatile`) |
| `encryption_key` | Fernet base64 key (generate once, keep secret) |
| `jwt_secret_key` | 64-char hex string for JWT signing |
| `jwt_algorithm` | Default: `HS256` |
| `access_token_expire_minutes` | Default: 60 |
| `app_host` | Default: `0.0.0.0` |
| `app_port` | Default: `8000` |

**Usage:**
```python
from app.config import settings
api_key = settings.groq_api_key
```

Or with `get_settings()` (if using `@lru_cache`):
```python
from app.config import get_settings
settings = get_settings()
```

### `database.py`
Async SQLAlchemy engine and session factory.

```python
engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()
```

**FastAPI dependency:**
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
        await session.commit()
```

Used in all route handlers:
```python
db: AsyncSession = Depends(get_db)
```

**Background tasks** use `AsyncSessionLocal` directly (not `get_db`) since they run outside the request lifecycle.

### `__init__.py`
Empty package marker.

## Sub-package Overview

| Directory | Contents |
|---|---|
| `agents/` | 12 AI agents + orchestrator (multi-agent arbitration pipeline) |
| `core/` | Security, PDF parsing, semantic chunking, PII processor, logging |
| `middleware/` | Rate limiting (`slowapi`) |
| `models/` | SQLAlchemy ORM models (9 database tables) |
| `rag/` | 5-layer RAG pipeline (embeddings, retrieval, reranking, citations) |
| `routers/` | FastAPI route handlers (auth, cases, documents, verdicts) |
| `schemas/` | Pydantic request/response models |
| `tasks/` | FastAPI BackgroundTasks (document processing pipeline) |

## Request Lifecycle

```
HTTP Request
    │
    ▼
CORSMiddleware          ← validates origin
    │
    ▼
RateLimitMiddleware     ← checks IP-based rate limits (planned)
    │
    ▼
Router handler          ← validates JWT, parses body with Pydantic schema
    │
    ├──► get_db()        ← opens async DB session
    ├──► get_current_user_payload()  ← validates JWT, extracts user_id
    │
    ├──► Business logic (models, agents, rag)
    │
    ▼
Response (JSON)         ← Pydantic schema serialization
    │
    ▼ (after response sent)
BackgroundTask          ← process_document(), run_orchestrator()
```

## How to Run

```bash
# Development (with auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --workers 1 --host 0.0.0.0 --port 8000
```

**Note:** Use `--workers 1` in production if using in-memory SSE queues. Multi-worker mode requires Redis pub/sub for SSE broadcasting.
