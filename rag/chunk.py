"""Chunk source documents into ~500-token windows for RAG embedding.

Preserves page boundaries from extract.py's `[page N]` markers so that each chunk's
metadata can resolve back to a citation. Uses tiktoken for accurate token counts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import tiktoken

from ingest.extract import extract


_ENC = tiktoken.encoding_for_model("text-embedding-3-small")
_PAGE_RE = re.compile(r"^\[page (\d+)\]\s*$")

CHUNK_TOKENS = 500
OVERLAP_TOKENS = 50


@dataclass(frozen=True)
class Chunk:
    source_id: str
    chunk_index: int
    page_start: int
    page_end: int
    text: str

    def to_metadata(self) -> dict:
        return {
            "source_id": self.source_id,
            "chunk_index": self.chunk_index,
            "page_start": self.page_start,
            "page_end": self.page_end,
        }


def _split_pages(text: str) -> list[tuple[int, str]]:
    """Split extracted text into (page_number, page_text) tuples."""
    pages: list[tuple[int, str]] = []
    current_page: int | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        m = _PAGE_RE.match(line.strip())
        if m:
            if current_page is not None:
                pages.append((current_page, "\n".join(current_lines).strip()))
            current_page = int(m.group(1))
            current_lines = []
        else:
            current_lines.append(line)
    if current_page is not None:
        pages.append((current_page, "\n".join(current_lines).strip()))
    return pages


def chunk_document(source_id: str, source_path: Path) -> list[Chunk]:
    text = extract(source_path)
    pages = _split_pages(text)
    if not pages:
        return []

    # Tokenize all pages once, tracking the page each token came from.
    all_tokens: list[int] = []
    token_to_page: list[int] = []
    for page_num, page_text in pages:
        toks = _ENC.encode(page_text)
        all_tokens.extend(toks)
        token_to_page.extend([page_num] * len(toks))

    chunks: list[Chunk] = []
    step = CHUNK_TOKENS - OVERLAP_TOKENS
    for chunk_idx, start in enumerate(range(0, len(all_tokens), step)):
        end = min(start + CHUNK_TOKENS, len(all_tokens))
        if end - start < 50:  # discard runt at the end
            break
        chunk_tokens = all_tokens[start:end]
        chunk_text = _ENC.decode(chunk_tokens).strip()
        page_start = token_to_page[start]
        page_end = token_to_page[end - 1]
        chunks.append(
            Chunk(
                source_id=source_id,
                chunk_index=chunk_idx,
                page_start=page_start,
                page_end=page_end,
                text=chunk_text,
            )
        )
        if end >= len(all_tokens):
            break
    return chunks


def chunk_manifest(documents: Iterable[dict], data_root: Path) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for doc in documents:
        path = data_root / doc["filename"]
        if not path.exists():
            continue
        all_chunks.extend(chunk_document(doc["id"], path))
    return all_chunks
