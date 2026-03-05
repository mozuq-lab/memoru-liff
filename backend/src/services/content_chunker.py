"""Content chunker for splitting web page text into AI-processable chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

# Default max characters per chunk
DEFAULT_MAX_CHUNK_SIZE = 3000

# Heading pattern (markdown-style)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass
class ContentChunk:
    """A single chunk of page content."""

    text: str
    section_title: Optional[str]
    page_title: str
    chunk_index: int
    total_chunks: int


def chunk_content(
    text: str,
    page_title: str,
    max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
) -> List[ContentChunk]:
    """Split text into chunks suitable for card generation.

    Splits at heading boundaries first, then at paragraph boundaries if sections
    are still too large.

    Args:
        text: The full text content to chunk.
        page_title: The page title (attached to every chunk for context).
        max_chunk_size: Maximum characters per chunk.

    Returns:
        List of ContentChunk objects, empty if text is blank.
    """
    text = text.strip()
    if not text:
        return []

    # Split into sections by headings
    sections = _split_by_headings(text)

    # Further split large sections by paragraphs
    raw_chunks: list[tuple[str, Optional[str]]] = []
    for section_title, section_text in sections:
        if len(section_text) <= max_chunk_size:
            raw_chunks.append((section_text, section_title))
        else:
            sub_chunks = _split_by_paragraphs(section_text, max_chunk_size)
            for sub in sub_chunks:
                # If a single paragraph is still too large, force-split it
                if len(sub) > max_chunk_size:
                    force_chunks = _force_split(sub, max_chunk_size)
                    for fc in force_chunks:
                        raw_chunks.append((fc, section_title))
                else:
                    raw_chunks.append((sub, section_title))

    # Filter out empty chunks
    raw_chunks = [(t, s) for t, s in raw_chunks if t.strip()]

    if not raw_chunks:
        return []

    total = len(raw_chunks)
    return [
        ContentChunk(
            text=chunk_text,
            section_title=section_title,
            page_title=page_title,
            chunk_index=i,
            total_chunks=total,
        )
        for i, (chunk_text, section_title) in enumerate(raw_chunks)
    ]


def _split_by_headings(text: str) -> list[tuple[Optional[str], str]]:
    """Split text into (section_title, section_body) tuples at heading boundaries."""
    matches = list(_HEADING_RE.finditer(text))

    if not matches:
        return [(None, text)]

    sections: list[tuple[Optional[str], str]] = []

    # Content before first heading
    if matches[0].start() > 0:
        pre_content = text[: matches[0].start()].strip()
        if pre_content:
            sections.append((None, pre_content))

    for i, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((title, body))

    return sections


def _split_by_paragraphs(text: str, max_size: int) -> list[str]:
    """Split text into chunks at paragraph boundaries (\n\n)."""
    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para_len = len(para)

        if current_len + para_len + 2 > max_size and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len + 2  # +2 for \n\n separator

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _force_split(text: str, max_size: int) -> list[str]:
    """Force-split a single large block of text at sentence boundaries."""
    # Split at sentence endings (. ! ? followed by space)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        s_len = len(sentence)

        if current_len + s_len + 1 > max_size and current:
            chunks.append(" ".join(current))
            current = [sentence]
            current_len = s_len
        else:
            current.append(sentence)
            current_len += s_len + 1

    if current:
        chunks.append(" ".join(current))

    return chunks
