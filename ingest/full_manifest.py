"""Auto-generate the 'full' manifest as the union of data/predictant/ and data/academic/.

The internal/full deployment uses this — no manual editing required when new docs are
dropped into either subfolder.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


SUPPORTED_SUFFIXES = {".pdf", ".pptx", ".md", ".markdown", ".txt"}


def _stable_id(filename: str) -> str:
    """Derive a stable, filesystem-safe ID from a filename."""
    stem = Path(filename).stem
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()
    return slug[:80] or "untitled"


def _scan(folder: Path, kind: str) -> list[dict]:
    if not folder.exists():
        return []
    entries: list[dict] = []
    for f in sorted(folder.iterdir()):
        if f.is_file() and f.suffix.lower() in SUPPORTED_SUFFIXES:
            entries.append(
                {
                    "id": _stable_id(f.name),
                    "filename": f.name,
                    "title": f.stem,
                    "kind": kind,
                    "path": str(f.relative_to(folder.parent.parent)).replace("\\", "/"),
                }
            )
    return entries


def build(data_root: Path) -> dict:
    return {
        "description": (
            "Auto-generated full manifest = data/predictant/* + data/academic/*. "
            "Do not edit manually; drop new docs into the right subfolder instead."
        ),
        "documents": _scan(data_root / "predictant", kind="predictant")
        + _scan(data_root / "academic", kind="academic"),
    }


def main() -> None:
    data_root = Path(__file__).resolve().parents[1] / "data"
    out = Path(__file__).resolve().parent / "manifest_full.generated.json"
    manifest = build(data_root)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out} with {len(manifest['documents'])} documents.")


if __name__ == "__main__":
    main()
