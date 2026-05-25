"""Tool implementations exposed to the OpenAI function-calling agent.

The wiki and chroma directories are configured via env vars (WIKI_PATH, CHROMA_PATH)
so the same code serves the public and internal deployments.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from rag.search import search_raw_chunks as _search_raw_chunks


_WIKI_PATH = Path(os.environ.get("WIKI_PATH", "wiki-public"))


def _resolve_page(name: str) -> Path | None:
    """Resolve a wiki page by name. Accepts 'pages/products/bolt-iq.md' or 'bolt-iq' or 'bolt iq'."""
    name = name.strip()
    if name.endswith(".md"):
        candidate = _WIKI_PATH / name
        return candidate if candidate.exists() else None

    slug = name.lower().replace(" ", "-").replace("_", "-")
    # Try direct top-level files first (index, log, contradictions)
    for fname in ("index.md", "log.md", "contradictions.md"):
        if Path(fname).stem == slug:
            return _WIKI_PATH / fname
    # Walk the pages tree
    pages_root = _WIKI_PATH / "pages"
    if pages_root.exists():
        for md in pages_root.rglob("*.md"):
            if md.stem == slug:
                return md
    return None


def read_wiki_index() -> str:
    index_path = _WIKI_PATH / "index.md"
    if not index_path.exists():
        return "Wiki index not found. The wiki may not be built yet."
    return index_path.read_text(encoding="utf-8")


def read_wiki_page(name: str) -> str:
    resolved = _resolve_page(name)
    if resolved is None:
        # Return a helpful "not found" with available pages
        pages_root = _WIKI_PATH / "pages"
        available: list[str] = []
        if pages_root.exists():
            for md in pages_root.rglob("*.md"):
                available.append(str(md.relative_to(_WIKI_PATH)).replace("\\", "/"))
        sample = ", ".join(available[:30])
        return (
            f"Page '{name}' not found. "
            f"Available pages (first 30): {sample or '(none — wiki not built yet)'}"
        )
    return resolved.read_text(encoding="utf-8")


def search_raw_chunks(query: str, k: int = 5) -> list[dict[str, Any]]:
    return _search_raw_chunks(query, k=k)


# --- OpenAI tool schemas -------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_wiki_index",
            "description": "Read the wiki's index.md — a catalogue of curated pages grouped by category. ALWAYS call this first for factual questions to see what pages exist before reading any specific page.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_wiki_page",
            "description": "Read the full markdown of a specific wiki page. Pass a page slug like 'bolt-iq' or 'ultrasonic-time-of-flight', or a full wiki-relative path like 'pages/products/bolt-iq.md'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Page slug or wiki-relative path."}
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_raw_chunks",
            "description": "Search the raw source PDFs via semantic vector similarity. Returns up to k chunks with source_id and page numbers. Use as a fallback when the wiki doesn't cover the question, or when the user explicitly wants primary-source quotes/numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The semantic search query."},
                    "k": {"type": "integer", "description": "Number of chunks to return (1–10).", "default": 5},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]


def dispatch(name: str, arguments: dict) -> Any:
    if name == "read_wiki_index":
        return read_wiki_index()
    if name == "read_wiki_page":
        return read_wiki_page(arguments["name"])
    if name == "search_raw_chunks":
        return search_raw_chunks(arguments["query"], k=int(arguments.get("k", 5)))
    raise ValueError(f"Unknown tool: {name}")
