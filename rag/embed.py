"""Embed chunks with OpenAI text-embedding-3-small and persist to ChromaDB."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import chromadb
from chromadb.config import Settings
from openai import OpenAI
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn
from tenacity import retry, stop_after_attempt, wait_exponential

from ingest.full_manifest import build as build_full_manifest
from rag.chunk import chunk_manifest, Chunk


console = Console()
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
COLLECTION_NAME = "amos_chunks"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20), reraise=True)
def _embed_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def _load_manifest(path: Path, data_root: Path) -> list[dict]:
    if path.name == "AUTO" or path.name.startswith("manifest_full"):
        return build_full_manifest(data_root.parent)["documents"]
    return json.loads(path.read_text(encoding="utf-8"))["documents"]


def _existing_source_ids(coll) -> set[str]:
    try:
        res = coll.get(include=["metadatas"])
    except Exception:
        return set()
    return {m["source_id"] for m in (res.get("metadatas") or []) if m and "source_id" in m}


def _embed_and_add(client: OpenAI, coll, chunks: list[Chunk], batch_size: int = 64) -> None:
    with Progress(TextColumn("{task.description}"), BarColumn(), TextColumn("{task.completed}/{task.total}")) as p:
        task = p.add_task("Embedding…", total=len(chunks))
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            vectors = _embed_batch(client, [c.text for c in batch])
            ids = [f"{c.source_id}:{c.chunk_index}" for c in batch]
            coll.add(
                ids=ids,
                embeddings=vectors,
                documents=[c.text for c in batch],
                metadatas=[c.to_metadata() for c in batch],
            )
            p.advance(task, advance=len(batch))


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    parser = argparse.ArgumentParser(description="Embed chunks and store in ChromaDB.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--chroma-out", type=Path, required=True)
    parser.add_argument("--new-only", action="store_true")
    args = parser.parse_args()

    if "OPENAI_API_KEY" not in os.environ:
        console.print("[red]OPENAI_API_KEY not set[/]")
        return 2

    args.chroma_out.mkdir(parents=True, exist_ok=True)
    client = OpenAI()
    chroma = chromadb.PersistentClient(path=str(args.chroma_out), settings=Settings(anonymized_telemetry=False))
    coll = chroma.get_or_create_collection(COLLECTION_NAME)

    docs = _load_manifest(args.manifest, args.data_root)
    if args.new_only:
        already = _existing_source_ids(coll)
        docs = [d for d in docs if d["id"] not in already]

    console.print(f"[bold]Embed:[/] {len(docs)} docs into {args.chroma_out}")
    if not docs:
        console.print("[green]Nothing to embed.[/]")
        return 0

    all_chunks = chunk_manifest(docs, args.data_root)
    console.print(f"  {len(all_chunks)} chunks total")
    if not all_chunks:
        return 0
    _embed_and_add(client, coll, all_chunks)
    console.print(f"[green]Done.[/] Collection size: {coll.count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
