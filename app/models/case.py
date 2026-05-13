import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Enum as SAEnum, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CaseType(str, enum.Enum):
    CONTRACT = "CONTRACT"
    CONSUMER = "CONSUMER"
    PROPERTY = "PROPERTY"
    COMPANY = "COMPANY"


class CaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    PARTY_A_FILED = "PARTY_A_FILED"
    PARTY_B_RESPONDED = "PARTY_B_RESPONDED"
    IN_ARBITRATION = "IN_ARBITRATION"
    VERDICT_DELIVERED = "VERDICT_DELIVERED"


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    case_type: Mapped[CaseType] = mapped_column(SAEnum(CaseType), nullable=False)
    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus), default=CaseStatus.OPEN, nullable=False
    )
    party_a_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    party_b_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    party_b_invite_email_hash: Mapped[str] = mapped_column(String(64), nullable=True)
    party_b_invite_token: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
