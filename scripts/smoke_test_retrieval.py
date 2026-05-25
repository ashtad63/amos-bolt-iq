"""Quick retrieval smoke-test against chroma-public."""

import os
from dotenv import load_dotenv

load_dotenv()
os.environ["CHROMA_PATH"] = os.environ.get("CHROMA_PATH", "chroma-public")

from rag.search import search_raw_chunks


def show(query: str, k: int = 3) -> None:
    print(f"=== Query: {query} ===")
    hits = search_raw_chunks(query, k=k)
    for h in hits:
        sid = h["source_id"]
        p1, p2 = h["page_start"], h["page_end"]
        score = h["score"]
        preview = h["text"][:160].replace("\n", " ")
        print(f"  [{sid} p.{p1}-{p2}] score={score:.3f}")
        print(f"    {preview}...")
    print()


show("DNV certified accuracy of Bolt iQ")
show("bi-wave method versus single wave time of flight")
show("How does Bolt iQ measure tension directly")
