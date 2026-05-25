"""Retrieval API used by the Chainlit chatbot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import chromadb
from chromadb.config import Settings
from openai import OpenAI


_CHROMA_PATH = Path(os.environ.get("CHROMA_PATH", "chroma-public"))
_COLLECTION_NAME = "amos_chunks"
_EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")


@dataclass(frozen=True)
class RetrievalHit:
    source_id: str
    page_start: int
    page_end: int
    text: str
    score: float

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "text": self.text,
            "score": self.score,
        }


_client_singleton: OpenAI | None = None
_coll_singleton = None


def _client() -> OpenAI:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = OpenAI()
    return _client_singleton


def _collection():
    global _coll_singleton
    if _coll_singleton is None:
        chroma = chromadb.PersistentClient(path=str(_CHROMA_PATH), settings=Settings(anonymized_telemetry=False))
        _coll_singleton = chroma.get_or_create_collection(_COLLECTION_NAME)
    return _coll_singleton


def search_raw_chunks(query: str, k: int = 5) -> list[dict]:
    q_emb = _client().embeddings.create(model=_EMBED_MODEL, input=[query]).data[0].embedding
    res = _collection().query(query_embeddings=[q_emb], n_results=k, include=["metadatas", "documents", "distances"])
    hits: list[dict] = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hits.append(
            RetrievalHit(
                source_id=meta["source_id"],
                page_start=meta["page_start"],
                page_end=meta["page_end"],
                text=doc,
                score=1.0 - dist,
            ).to_dict()
        )
    return hits


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m rag.search '<query>'")
        sys.exit(1)
    print(json.dumps(search_raw_chunks(" ".join(sys.argv[1:]), k=5), indent=2))
