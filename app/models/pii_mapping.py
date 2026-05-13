import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PIIMapping(Base):
    __tablename__ = "pii_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(50))         # e.g. PERSON_1, AADHAAR_2
    entity_type: Mapped[str] = mapped_column(String(50))   # Presidio entity type
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary)  # Fernet-encrypted original value
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
