"""
Semantic chunker that splits documents at paragraph/section boundaries
instead of character boundaries, preserving complete sentences and clauses.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class SemanticChunk:
    index: int
    text: str
    page_numbers: list[int]
    section_header: str | None
    chunk_type: str  # "clause" | "paragraph" | "table" | "header"
    document_id: str
    token_count: int

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "text": self.text,
            "page_numbers": self.page_numbers,
            "section_header": self.section_header,
            "chunk_type": self.chunk_type,
            "document_id": self.document_id,
            "token_count": self.token_count,
        }


# Patterns for section headers
_HEADER_PATTERNS = [
    re.compile(r"^\s*(\d+[\.\d]*)\s+[A-Z][A-Za-z ]{3,}$", re.MULTILINE),  # "1.2 Section Name"
    re.compile(r"^\s*[A-Z][A-Z\s]{4,}:?\s*$", re.MULTILINE),               # "ALL CAPS HEADER"
    re.compile(r"^\s*(CLAUSE|SECTION|ARTICLE|SCHEDULE|ANNEXURE)\s+\d+", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*(WHEREAS|NOW THEREFORE|IN WITNESS WHEREOF)", re.MULTILINE | re.IGNORECASE),
]


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters."""
    return max(1, len(text) // 4)


def _is_header(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    for pattern in _HEADER_PATTERNS:
        if pattern.match(line):
            return True
    return False


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences using simple regex."""
    # Split on '. ', '? ', '! ' followed by uppercase
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if s.strip()]


def semantic_chunk(
    text: str,
    document_id: str,
    page_map: dict[int, int] | None = None,  # char_offset → page_number
    max_tokens: int = 512,
) -> list[SemanticChunk]:
    """
    Split document text into semantic chunks:
    1. Split into paragraphs (double newline)
    2. Detect section headers
    3. Group consecutive paragraphs under same header
    4. If a section exceeds max_tokens, split at sentence boundaries
    5. Add overlap: last sentence of chunk N = first sentence of chunk N+1
    """
    if not text or not text.strip():
        return []

    # Split into paragraphs
    raw_paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in raw_paragraphs if p.strip()]

    chunks: list[SemanticChunk] = []
    current_header: str | None = None
    current_group: list[str] = []
    chunk_index = 0

    def flush_group(group: list[str], header: str | None, chunk_type: str = "paragraph"):
        nonlocal chunk_index
        combined = " ".join(group)
        if not combined.strip():
            return

        if _estimate_tokens(combined) <= max_tokens:
            chunks.append(SemanticChunk(
                index=chunk_index,
                text=combined,
                page_numbers=[1],  # simplified; real page tracking needs offset map
                section_header=header,
                chunk_type=chunk_type,
                document_id=document_id,
                token_count=_estimate_tokens(combined),
            ))
            chunk_index += 1
        else:
            # Too large — split at sentence boundaries
            sentences = _split_into_sentences(combined)
            current_sentences: list[str] = []
            current_tokens = 0
            last_sentence: str | None = None

            for i, sentence in enumerate(sentences):
                st = _estimate_tokens(sentence)
                if current_tokens + st > max_tokens and current_sentences:
                    chunk_text = " ".join(current_sentences)
                    chunks.append(SemanticChunk(
                        index=chunk_index,
                        text=chunk_text,
                        page_numbers=[1],
                        section_header=header,
                        chunk_type=chunk_type,
                        document_id=document_id,
                        token_count=_estimate_tokens(chunk_text),
                    ))
                    chunk_index += 1
                    # Overlap: start next chunk with last sentence of previous
                    current_sentences = ([last_sentence] if last_sentence else []) + [sentence]
                    current_tokens = sum(_estimate_tokens(s) for s in current_sentences)
                else:
                    current_sentences.append(sentence)
                    current_tokens += st
                last_sentence = sentence

            if current_sentences:
                chunk_text = " ".join(current_sentences)
                chunks.append(SemanticChunk(
                    index=chunk_index,
                    text=chunk_text,
                    page_numbers=[1],
                    section_header=header,
                    chunk_type=chunk_type,
                    document_id=document_id,
                    token_count=_estimate_tokens(chunk_text),
                ))
                chunk_index += 1

    for para in paragraphs:
        if _is_header(para):
            # Flush current group before starting new section
            if current_group:
                flush_group(current_group, current_header)
                current_group = []
            current_header = para.strip()
            # Header itself becomes a tiny chunk
            chunks.append(SemanticChunk(
                index=chunk_index,
                text=para,
                page_numbers=[1],
                section_header=None,
                chunk_type="header",
                document_id=document_id,
                token_count=_estimate_tokens(para),
            ))
            chunk_index += 1
        else:
            # Check if it looks like a table (many | characters)
            if para.count("|") >= 4:
                if current_group:
                    flush_group(current_group, current_header)
                    current_group = []
                flush_group([para], current_header, chunk_type="table")
            else:
                current_group.append(para)

    # Flush remaining
    if current_group:
        flush_group(current_group, current_header)

    return chunks
