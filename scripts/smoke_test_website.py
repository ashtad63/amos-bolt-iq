"""Smoke-test that the new website snapshot is retrievable."""

import os
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("WIKI_PATH", "wiki-public")
os.environ.setdefault("CHROMA_PATH", "chroma-public")

from app import agent

QUERIES = [
    "Where is Predictant headquartered?",
    "How can I contact Predictant for sales inquiries?",
    "How fast can Bolt iQ test 100 bolts?",
]

for q in QUERIES:
    print("=" * 80)
    print(f"USER: {q}")
    result = agent.run([], q)
    print(f"AMOS: {result.text}")
    print(f"[tools: {[t['name'] for t in result.tool_calls]}; tokens in={result.input_tokens} out={result.output_tokens}]")
    print()
