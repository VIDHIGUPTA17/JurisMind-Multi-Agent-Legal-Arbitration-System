from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    processing_status: str
    task_id: Optional[str] = None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: str
    case_id: str
    uploader_id: str
    filename: str
    processing_status: str
    content_anonymized: Optional[str] = None  # Only shown to owner
    uploaded_at: datetime
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
