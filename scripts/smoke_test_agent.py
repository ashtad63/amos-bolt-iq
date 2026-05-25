"""End-to-end agent loop smoke test — calls agent.run() without Chainlit."""

import os
import sys
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("WIKI_PATH", "wiki-public")
os.environ.setdefault("CHROMA_PATH", "chroma-public")

from app import agent

QUERIES = [
    "What is Bolt iQ and how does it work?",
    "What's the DNV-certified accuracy of Bolt iQ?",
    "Compare the bi-wave method to single-wave time-of-flight.",
]


def main() -> int:
    for q in QUERIES:
        print("=" * 80)
        print(f"USER: {q}")
        try:
            result = agent.run([], q)
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")
            return 1
        print(f"AMOS: {result.text}")
        tool_names = [t['name'] for t in result.tool_calls]
        print(f"[tools used: {tool_names}; tokens in={result.input_tokens} out={result.output_tokens}]")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
