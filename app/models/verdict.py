import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base


class Verdict(Base):
    __tablename__ = "verdicts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"), nullable=False, unique=True, index=True)
    agent_a_summary: Mapped[str] = mapped_column(Text, nullable=True)
    agent_b_summary: Mapped[str] = mapped_column(Text, nullable=True)
    judge_reasoning: Mapped[str] = mapped_column(Text, nullable=True)
    verdict_text: Mapped[str] = mapped_column(Text, nullable=True)
    applicable_laws: Mapped[list] = mapped_column(JSONB, default=list)
    relief_awarded: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # Sprint 1 additions
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    grounding_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    bias_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    settlement_recommendation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    compensation_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    stage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    total_groq_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
