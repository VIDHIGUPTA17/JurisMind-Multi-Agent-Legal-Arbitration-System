import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Enum as SAEnum, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    PARTY_A = "PARTY_A"
    PARTY_B = "PARTY_B"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email_encrypted: Mapped[bytes] = mapped_column()
    email_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name_encrypted: Mapped[bytes] = mapped_column()
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
