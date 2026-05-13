import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import engine
from app.models import Base  # noqa: ensures all models are registered
from app.routers import auth, cases, documents, verdicts
from app.routers.arbitration_stream import router as stream_router
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)

# Rate limiter singleton (used by verdict router via middleware registration)
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    # Warm up the BGE embedding model at startup to avoid cold-start latency
    try:
        from app.rag.embeddings import get_model
        get_model()
        logger.info("embedding_model_warmed_up")
    except Exception as exc:
        logger.warning("embedding_model_warmup_failed", extra={"error": str(exc)})

    yield

    await engine.dispose()
    logger.info("engine_disposed")


app = FastAPI(
    title="AI Legal Arbitration System",
    description="Multi-agent AI arbitration platform for Indian civil disputes",
    version="2.0.0",
    lifespan=lifespan,
)

# Rate limiter state + exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Body size limit — 25 MB
@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    if request.headers.get("content-length"):
        content_length = int(request.headers["content-length"])
        if content_length > 25 * 1024 * 1024:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=413, content={"detail": "Request body too large (max 25 MB)"})
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(documents.router)
app.include_router(verdicts.router)
app.include_router(stream_router)


@app.get("/health")
async def health():
    """Deep health check — DB connectivity + embedding model availability."""
    checks: dict = {"status": "ok", "db": "unknown", "embedding_model": "unknown"}

    # DB check
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"error: {exc}"
        checks["status"] = "degraded"

    # Embedding model check
    try:
        from app.rag.embeddings import get_model
        get_model()
        checks["embedding_model"] = "ok"
    except Exception as exc:
        checks["embedding_model"] = f"error: {exc}"
        checks["status"] = "degraded"

    return checks
