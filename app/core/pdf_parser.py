"""
PDF text extraction and chunking using PyMuPDF.

Supports text-layer PDFs only (v1 — no OCR).
Returns a list of text chunks suitable for embedding.
"""
from dataclasses import dataclass

import pymupdf  # PyMuPDF


CHUNK_SIZE = 1000       # characters per chunk (approx 250 tokens for LLMs)
CHUNK_OVERLAP = 200     # character overlap between consecutive chunks


@dataclass
class TextChunk:
    index: int
    text: str
    page_numbers: list[int]  # source pages this chunk came from


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF given its raw bytes."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages_text = []
    for page in doc:
        pages_text.append(page.get_text())
    doc.close()
    return "\n\n".join(pages_text)


def extract_pages(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Return list of (page_number, text) tuples (1-indexed)."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        if text:
            pages.append((i, text))
    doc.close()
    return pages


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping character-level chunks."""
    if not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def extract_and_chunk(pdf_bytes: bytes) -> list[TextChunk]:
    """
    Full pipeline: extract text page-by-page, then chunk across all pages.
    Each chunk records which page(s) it originated from.
    """
    pages = extract_pages(pdf_bytes)
    if not pages:
        return []

    # Build a flat text with page boundary markers to track page numbers
    flat_text = ""
    page_boundaries: list[tuple[int, int, int]] = []  # (start_char, end_char, page_num)
    for page_num, text in pages:
        start = len(flat_text)
        flat_text += text + "\n\n"
        end = len(flat_text)
        page_boundaries.append((start, end, page_num))

    raw_chunks = chunk_text(flat_text)
    result: list[TextChunk] = []
    offset = 0
    for idx, chunk_text_ in enumerate(raw_chunks):
        chunk_start = flat_text.find(chunk_text_, offset)
        if chunk_start == -1:
            chunk_start = offset
        chunk_end = chunk_start + len(chunk_text_)

        # Find which pages overlap this chunk
        pages_for_chunk = [
            pn for (ps, pe, pn) in page_boundaries
            if ps < chunk_end and pe > chunk_start
        ]
        result.append(TextChunk(index=idx, text=chunk_text_, page_numbers=pages_for_chunk or [1]))
        offset = max(0, chunk_end - CHUNK_OVERLAP)

    return result
