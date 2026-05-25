"""Rebuild wiki index.md deterministically from the filesystem.

The ingest agent focuses on creating high-quality content pages; this script keeps
index.md correct without relying on the agent's discipline. Run after every ingest.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


CATEGORIES = [
    ("concepts", "Concepts", "Physical and scientific concepts."),
    ("products", "Products", "Predictant Bolt iQ and related products."),
    ("standards", "Standards", "Certifications and standards (DNV, ISO, ASTM, …)."),
    ("applications", "Applications", "Practical applications and use cases."),
    ("sources", "Sources", "One page per ingested document (provenance)."),
]


def _title_from_slug(stem: str) -> str:
    """Convert 'bi-wave-method' → 'Bi-Wave Method'. Preserves common acronyms."""
    parts = stem.replace("_", "-").split("-")
    acronyms = {"dnv", "iso", "astm", "iq", "us", "ml", "ai", "rag"}
    out: list[str] = []
    for p in parts:
        out.append(p.upper() if p.lower() in acronyms else p.capitalize())
    return " ".join(out)


def _extract_title(md_path: Path) -> str:
    """Prefer the H1; otherwise derive from the slug (never the first paragraph)."""
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception:
        return _title_from_slug(md_path.stem)
    h1 = re.search(r"^# (.+)$", text, re.MULTILINE)
    if h1:
        return h1.group(1).strip()
    return _title_from_slug(md_path.stem)


def _extract_summary(md_path: Path) -> str:
    """Use the first paragraph after the H1 (or the file's first paragraph)."""
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception:
        return ""
    lines = text.splitlines()
    # Skip the H1 if present
    start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("# "):
            start = i + 1
            break
    # Find first non-blank, non-heading paragraph
    para: list[str] = []
    for line in lines[start:]:
        s = line.strip()
        if not s:
            if para:
                break
            continue
        if s.startswith("#") or s.startswith("- ") or s.startswith("* "):
            if para:
                break
            continue
        para.append(s)
    summary = " ".join(para).strip()
    if len(summary) > 160:
        summary = summary[:157] + "…"
    return summary


def rebuild(wiki_root: Path) -> str:
    out: list[str] = []
    out.append("# Amos Wiki — Index")
    out.append("")
    out.append(
        "The curated, interlinked knowledge graph compiled by the ingest agent. "
        "Sources are immutable; this index is the entry point."
    )
    out.append("")

    pages_root = wiki_root / "pages"
    for cat_dir, cat_label, cat_desc in CATEGORIES:
        out.append(f"## {cat_label}")
        out.append("")
        out.append(f"_{cat_desc}_")
        out.append("")
        cat_path = pages_root / cat_dir
        entries: list[tuple[str, str, str]] = []
        if cat_path.exists():
            for md in sorted(cat_path.glob("*.md")):
                title = _extract_title(md)
                summary = _extract_summary(md)
                rel = str(md.relative_to(wiki_root)).replace("\\", "/")
                entries.append((title, summary, rel))
        if entries:
            for title, summary, rel in entries:
                if summary:
                    out.append(f"- [{title}]({rel}) — {summary}")
                else:
                    out.append(f"- [{title}]({rel})")
        else:
            out.append("_No pages yet in this category._")
        out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild wiki index.md from the filesystem.")
    parser.add_argument("--wiki", type=Path, required=True, help="Wiki root directory (e.g., wiki-public).")
    args = parser.parse_args()

    if not args.wiki.exists():
        print(f"wiki dir not found: {args.wiki}")
        return 1
    content = rebuild(args.wiki)
    (args.wiki / "index.md").write_text(content, encoding="utf-8")
    page_count = sum(1 for _ in (args.wiki / "pages").rglob("*.md")) if (args.wiki / "pages").exists() else 0
    print(f"Wrote {args.wiki / 'index.md'} with {page_count} pages indexed.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
