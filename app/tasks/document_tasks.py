"""
Background task for processing uploaded legal documents.
Pipeline: decrypt → extract text → semantic chunk → PII anonymize → embed → store
"""
from __future__ import annotations
import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.document import Document, DocumentProcessingStatus
from app.models.embedding import DocumentChunk
from app.models.pii_audit import PIIAuditLog
from app.models.pii_mapping import PIIMapping
from app.core.security import encrypt, decrypt_bytes
from app.core.pdf_parser import extract_text_from_pdf
from app.core.chunker import semantic_chunk
from app.core.pii_processor import anonymize
from app.rag.embeddings import get_document_embedding

logger = logging.getLogger(__name__)


async def process_document(document_id: str) -> None:
    """
    Full document processing pipeline:
    1. Fetch document from DB
    2. Decrypt PDF bytes
    3. Extract text from PDF (PyMuPDF)
    4. Semantic chunk the text (paragraph/section-aware)
    5. PII detection and anonymization (Presidio)
    6. Store anonymized text on document
    7. Save PII mappings
    8. Save PII audit log
    9. Generate BGE-base embeddings for each chunk
    10. Store DocumentChunk rows
    11. Update document status → DONE
    """
    async with AsyncSessionLocal() as session:
        try:
            # 1. Fetch document
            result = await session.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if doc is None:
                logger.error("document_not_found", extra={"document_id": document_id})
                return

            # Mark as processing
            doc.processing_status = DocumentProcessingStatus.PROCESSING
            await session.commit()

            logger.info("document_processing_started", extra={
                "document_id": document_id,
                "doc_filename": doc.filename,
            })

            # 2. Decrypt PDF bytes
            pdf_bytes = decrypt_bytes(doc.content_encrypted)

            # 3. Extract text from PDF
            extracted_text = extract_text_from_pdf(pdf_bytes)
            if not extracted_text or not extracted_text.strip():
                raise ValueError("No text could be extracted from PDF")

            # 4. Semantic chunking
            semantic_chunks = semantic_chunk(
                text=extracted_text,
                document_id=document_id,
                max_tokens=512,
            )

            if not semantic_chunks:
                raise ValueError("No chunks produced from document")

            logger.info("document_chunked", extra={
                "document_id": document_id,
                "chunk_count": len(semantic_chunks),
            })

            # 5. PII detection and anonymization on full text
            pii_result = anonymize(extracted_text)

            # 6. Store anonymized text on document
            doc.content_anonymized = pii_result.anonymized_text

            # 7. Save PII mappings (encrypted original values)
            for pii_token in pii_result.tokens:
                mapping = PIIMapping(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    token=pii_token.token,
                    entity_type=pii_token.entity_type,
                    encrypted_value=encrypt(pii_token.original_value),
                )
                session.add(mapping)

            # 8. Save PII audit log
            for entity_type, count in pii_result.audit.items():
                audit = PIIAuditLog(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    entity_type=entity_type,
                    count_found=count,
                    processing_time_ms=pii_result.processing_time_ms,
                )
                session.add(audit)

            # 9 & 10. Generate embeddings per chunk, apply PII anonymization to chunk text
            for chunk in semantic_chunks:
                # Anonymize the chunk text individually
                chunk_pii = anonymize(chunk.text)
                anonymized_chunk_text = chunk_pii.anonymized_text

                # Generate embedding for anonymized chunk text
                embedding_vec = get_document_embedding(anonymized_chunk_text)

                db_chunk = DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    case_id=doc.case_id,
                    chunk_index=chunk.index,
                    chunk_text=anonymized_chunk_text,
                    embedding=embedding_vec,
                    section_header=chunk.section_header,
                    chunk_type=chunk.chunk_type,
                    token_count=chunk.token_count,
                    page_numbers=chunk.page_numbers,
                    document_filename=doc.filename,
                )
                session.add(db_chunk)

            # 11. Mark document as done
            doc.processing_status = DocumentProcessingStatus.DONE
            doc.processed_at = datetime.now(timezone.utc)

            await session.commit()

            logger.info("document_processing_completed", extra={
                "document_id": document_id,
                "chunk_count": len(semantic_chunks),
            })

        except Exception as exc:
            logger.error("document_processing_failed", extra={
                "document_id": document_id,
                "error": str(exc),
            })
            try:
                result2 = await session.execute(
                    select(Document).where(Document.id == document_id)
                )
                doc2 = result2.scalar_one_or_none()
                if doc2:
                    doc2.processing_status = DocumentProcessingStatus.FAILED
                    doc2.error_message = str(exc)[:500]
                    await session.commit()
            except Exception:
                pass
