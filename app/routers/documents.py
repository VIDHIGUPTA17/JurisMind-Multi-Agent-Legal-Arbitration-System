import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.case import Case, CaseStatus
from app.models.document import Document, DocumentProcessingStatus
from app.schemas.document import DocumentUploadResponse, DocumentResponse, DocumentListResponse
from app.core.security import get_current_user_payload, encrypt_bytes, decrypt_bytes
from app.tasks.document_tasks import process_document

router = APIRouter(prefix="/cases", tags=["documents"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/{case_id}/documents", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    case_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Validate case access
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    user_id = payload["sub"]
    if case.party_a_id != user_id and case.party_b_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied to this case")

    if case.status == CaseStatus.VERDICT_DELIVERED:
        raise HTTPException(status_code=400, detail="Cannot upload documents after verdict")

    # Read and validate file size
    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")

    # Encrypt raw PDF bytes before storage
    encrypted_bytes = encrypt_bytes(pdf_bytes)

    doc = Document(
        id=str(uuid.uuid4()),
        case_id=case_id,
        uploader_id=user_id,
        filename=file.filename,
        content_encrypted=encrypted_bytes,
        original_size_bytes=len(pdf_bytes),
        processing_status=DocumentProcessingStatus.PENDING,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    await db.flush()

    # Update case status
    if case.party_a_id == user_id and case.status == CaseStatus.OPEN:
        case.status = CaseStatus.PARTY_A_FILED
    elif case.party_b_id == user_id and case.status == CaseStatus.PARTY_A_FILED:
        case.status = CaseStatus.PARTY_B_RESPONDED
    case.updated_at = datetime.now(timezone.utc)

    await db.commit()

    # Dispatch background processing task (no Redis needed)
    background_tasks.add_task(process_document, doc.id)

    return DocumentUploadResponse(
        id=doc.id,
        filename=doc.filename,
        processing_status=doc.processing_status.value,
        task_id=doc.id,
        uploaded_at=doc.uploaded_at,
    )


@router.get("/{case_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    case_id: str,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    user_id = payload["sub"]
    if case.party_a_id != user_id and case.party_b_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    docs_result = await db.execute(
        select(Document).where(Document.case_id == case_id).order_by(Document.uploaded_at.desc())
    )
    documents = docs_result.scalars().all()

    items = []
    for doc in documents:
        # Only show anonymized content to the document owner
        anon_content = doc.content_anonymized if doc.uploader_id == user_id else None
        items.append(
            DocumentResponse(
                id=doc.id,
                case_id=doc.case_id,
                uploader_id=doc.uploader_id,
                filename=doc.filename,
                processing_status=doc.processing_status.value,
                content_anonymized=anon_content,
                uploaded_at=doc.uploaded_at,
                processed_at=doc.processed_at,
            )
        )

    return DocumentListResponse(documents=items, total=len(items))


@router.post("/{case_id}/documents/{doc_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_document(
    case_id: str,
    doc_id: str,
    background_tasks: BackgroundTasks,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    """Re-queue a FAILED document for processing."""
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    user_id = payload["sub"]
    if case.party_a_id != user_id and case.party_b_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    doc_result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.case_id == case_id)
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.processing_status != DocumentProcessingStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only FAILED documents can be retried")

    doc.processing_status = DocumentProcessingStatus.PENDING
    await db.commit()

    background_tasks.add_task(process_document, doc.id)
    return {"doc_id": doc_id, "status": "pending"}
