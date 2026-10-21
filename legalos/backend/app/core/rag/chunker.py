import re
from typing import List, Dict, Any

def clean_text(text: str) -> str:
    """Basic text cleanup — normalises CRLF, tabs and redundant whitespace."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)  # collapse triple+ newlines to double
    return text.strip()


def chunk_by_clause(text: str, max_chars: int = 4000) -> List[Dict[str, Any]]:
    """
    Splits legal contract text into clauses.
    Attempts to identify numbered headings (e.g. '1. Scope of Work', 'SECTION 3. term', 'ARTICLE IV')
    to split text into coherent clause boundaries.
    """
    # Normalize line endings
    text = text.replace('\r\n', '\n')
    
    # Define common clause headers
    # E.g. "1. Scope of Work", "Section 2.1", "Article X", "Definitions"
    clause_header_regex = re.compile(
        r'^(?:'
        r'(?:Section|SECTION|Article|ARTICLE|Clause|CLAUSE)\s+\d+(?:\.\d+)*.*'
        r'|\d+\.\s+.*'
        r'|\d+\.\d+\s+.*'
        r'|[A-Z][A-Z\s,&\-\'\"]{5,50}:?'
        r')$'
    )

    lines = text.split('\n')
    chunks = []
    current_chunk = []
    current_length = 0
    clause_index = 0

    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue
            
        # Check if line starts a new clause
        is_new_clause = False
        if len(cleaned_line) < 120:
            if clause_header_regex.match(cleaned_line) or re.match(r'^(?:\d+|\([a-zA-Z0-9]+\))\s+[A-Z]', cleaned_line):
                is_new_clause = True

        # If current chunk has content and we found a new clause, or current chunk exceeds length
        if (is_new_clause and current_chunk) or (current_length + len(cleaned_line) > max_chars and current_chunk):
            clause_text = "\n".join(current_chunk)
            chunks.append({
                "clause_index": clause_index,
                "text": clause_text
            })
            clause_index += 1
            current_chunk = []
            current_length = 0
            
        current_chunk.append(cleaned_line)
        current_length += len(cleaned_line)

    # Append remaining chunk
    if current_chunk:
        clause_text = "\n".join(current_chunk)
        chunks.append({
            "clause_index": clause_index,
            "text": clause_text
        })

    return chunks


def chunk_by_paragraph(text: str, max_chars: int = 1500) -> List[Dict[str, Any]]:
    """
    Standard paragraph-based chunker.
    Splits text by double newlines and returns each paragraph as a separate chunk.
    """
    paragraphs = re.split(r'\n[ \t]*\n', text)
    chunks = []
    chunk_index = 0
    
    for para in paragraphs:
        cleaned_para = clean_text(para)
        if not cleaned_para:
            continue
            
        # If a single paragraph is larger than max_chars, split it into character chunks
        if len(cleaned_para) > max_chars:
            start = 0
            while start < len(cleaned_para):
                end = start + max_chars
                chunks.append({
                    "clause_index": chunk_index,
                    "text": cleaned_para[start:end].strip()
                })
                chunk_index += 1
                start = end
        else:
            chunks.append({
                "clause_index": chunk_index,
                "text": cleaned_para
            })
            chunk_index += 1
            
    return chunks


def chunk_by_paragraph_with_overlap(
    text: str,
    max_chars: int = 800,
    overlap_chars: int = 150
) -> List[Dict[str, Any]]:
    """
    Paragraph-aware chunker with a sliding overlap window.

    Works by collecting consecutive paragraphs until the current chunk exceeds
    `max_chars`, then emits that chunk and starts the next one re-including the
    last `overlap_chars` worth of text so that semantic context is not lost at
    boundaries.

    Args:
        text:          Full extracted document text.
        max_chars:     Approximate maximum characters per chunk (default 800).
        overlap_chars: Characters of the previous chunk to carry forward into the
                       next one (default 150 ~30 tokens).
    Returns:
        List of {"clause_index": int, "text": str} dicts.
    """
    # Split on one-or-more blank lines to get semantic paragraphs
    raw_paragraphs = re.split(r'\n[ \t]*\n', text)
    paragraphs = [clean_text(p) for p in raw_paragraphs if clean_text(p)]

    chunks: List[Dict[str, Any]] = []
    chunk_index = 0
    current_parts: List[str] = []
    current_len = 0

    def _emit(parts: List[str]) -> str:
        return "\n\n".join(parts)

    for para in paragraphs:
        para_len = len(para)

        # If adding this paragraph would overflow, flush current chunk first
        if current_parts and (current_len + para_len) > max_chars:
            chunk_text = _emit(current_parts)
            chunks.append({"clause_index": chunk_index, "text": chunk_text})
            chunk_index += 1

            # Build overlap: take the tail of the emitted chunk up to overlap_chars
            overlap_seed = chunk_text[-overlap_chars:] if len(chunk_text) > overlap_chars else chunk_text
            current_parts = [overlap_seed]
            current_len = len(overlap_seed)

        # If a single paragraph is itself larger than max_chars, split it by chars
        if para_len > max_chars:
            # Flush any accumulated context first
            if current_parts:
                chunks.append({"clause_index": chunk_index, "text": _emit(current_parts)})
                chunk_index += 1
                current_parts = []
                current_len = 0

            start = 0
            while start < para_len:
                end = min(start + max_chars, para_len)
                slice_text = para[start:end].strip()
                if slice_text:
                    chunks.append({"clause_index": chunk_index, "text": slice_text})
                    chunk_index += 1
                start = end - overlap_chars  # slide back by overlap
                if start < 0:
                    start = 0
                if start >= para_len:
                    break
        else:
            current_parts.append(para)
            current_len += para_len

    # Emit any remaining text
    if current_parts:
        chunk_text = _emit(current_parts)
        if chunk_text.strip():
            chunks.append({"clause_index": chunk_index, "text": chunk_text})

    return chunks


def chunk_document(text: str, strategy: str = "clause") -> List[Dict[str, Any]]:
    """
    Dispatches to the correct chunking strategy.
    """
    if strategy == "clause":
        return chunk_by_clause(text)
    elif strategy == "paragraph":
        return chunk_by_paragraph(text)
    elif strategy == "paragraph_overlap":
        return chunk_by_paragraph_with_overlap(text)
    else:
        raise ValueError(f"Unknown chunking strategy: {strategy}")
