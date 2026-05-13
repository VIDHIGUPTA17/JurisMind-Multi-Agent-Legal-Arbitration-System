import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Enum as SAEnum, DateTime, ForeignKey, Text, Integer, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DocumentProcessingStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    uploader_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500))
    content_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)
    content_anonymized: Mapped[str] = mapped_column(Text, nullable=True)
    original_size_bytes: Mapped[int] = mapped_column(Integer, nullable=True)
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        SAEnum(DocumentProcessingStatus), default=DocumentProcessingStatus.PENDING
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
