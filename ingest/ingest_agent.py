"""Wiki ingest agent — runs gpt-4o-mini over each source document to curate the wiki.

Usage:
    python -m ingest.ingest_agent \
        --manifest ingest/manifest_public.json \
        --wiki-out wiki-public \
        --data-root data/predictant \
        --new-only

The agent calls OpenAI with a strict JSON schema for actions and applies them to the
local wiki directory. Idempotent: --new-only skips sources already listed in log.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Iterable

from openai import OpenAI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from tenacity import retry, stop_after_attempt, wait_exponential

from ingest.extract import extract
from ingest.full_manifest import build as build_full_manifest


console = Console()

INGEST_MODEL = os.environ.get("INGEST_MODEL", "gpt-4o-mini")
MAX_SOURCE_TOKENS = 90_000  # gpt-4o-mini context is 128k; leave room for prompt + relevant pages


SEED_INDEX_MD = """# Amos Wiki — Index

The curated, interlinked knowledge graph compiled by the ingest agent. Sources are immutable; this index is the entry point.

## Concepts

_Pages on physical/scientific concepts will appear here._

## Products

_Pages on Predictant Bolt iQ and related products will appear here._

## Standards

_Pages on certifications and standards (DNV, ISO, ASTM…) will appear here._

## Applications

_Pages on practical applications (wind-turbine fasteners, flange connections…) will appear here._

## Sources

_One page per ingested document — see `pages/sources/`._
"""

SEED_LOG_MD = """# Amos Wiki — Ingest Log

Chronological, append-only ledger. One entry per ingest run.

"""

SEED_CONTRADICTIONS_MD = """# Amos Wiki — Contradictions

Cross-source conflicts flagged by the ingest agent. Each entry preserves both sides with citations.

"""


# --- JSON schema for OpenAI structured output -----------------------------------

ACTIONS_SCHEMA = {
    "name": "wiki_actions",
    "schema": {
        "type": "object",
        "properties": {
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "create_page",
                                "update_page",
                                "append_log",
                                "flag_contradiction",
                            ],
                        },
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "mode": {
                            "type": "string",
                            "enum": ["append", "overwrite"],
                        },
                    },
                    "required": ["type", "path", "content", "mode"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["actions"],
        "additionalProperties": False,
    },
    "strict": True,
}


def _seed_wiki(wiki_out: Path) -> None:
    wiki_out.mkdir(parents=True, exist_ok=True)
    for subdir in ("pages/concepts", "pages/products", "pages/standards", "pages/applications", "pages/sources"):
        (wiki_out / subdir).mkdir(parents=True, exist_ok=True)
    if not (wiki_out / "index.md").exists():
        (wiki_out / "index.md").write_text(SEED_INDEX_MD, encoding="utf-8")
    if not (wiki_out / "log.md").exists():
        (wiki_out / "log.md").write_text(SEED_LOG_MD, encoding="utf-8")
    if not (wiki_out / "contradictions.md").exists():
        (wiki_out / "contradictions.md").write_text(SEED_CONTRADICTIONS_MD, encoding="utf-8")


def _already_ingested(wiki_out: Path) -> set[str]:
    log_path = wiki_out / "log.md"
    if not log_path.exists():
        return set()
    seen: set[str] = set()
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## [") and " ingest | " in line:
            try:
                source_id = line.split(" ingest | ", 1)[1].split(" — ", 1)[0].strip()
                seen.add(source_id)
            except IndexError:
                continue
    return seen


def _load_manifest(path: Path, data_root: Path) -> list[dict]:
    if path.name.startswith("manifest_full") or path.name == "AUTO":
        return build_full_manifest(data_root.parent)["documents"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    docs = manifest["documents"]
    for d in docs:
        d.setdefault("path", str((data_root / d["filename"]).relative_to(data_root.parent.parent)).replace("\\", "/"))
    return docs


def _build_user_message(doc: dict, source_text: str, index_md: str, source_page_path: Path) -> str:
    return (
        f"# Source to ingest\n\n"
        f"- source_id: `{doc['id']}`\n"
        f"- title: {doc['title']}\n"
        f"- kind: {doc['kind']}\n"
        f"- filename: {doc['filename']}\n"
        f"- date: {date.today().isoformat()}\n\n"
        f"## Current index.md\n\n```markdown\n{index_md}\n```\n\n"
        f"## Source text\n\n"
        f"The full extracted text follows. Read it carefully, then produce the JSON action list "
        f"according to the system prompt. Always include:\n"
        f"- exactly one `create_page` for `pages/sources/{doc['id']}.md`\n"
        f"- exactly one `append_log` for `log.md`\n"
        f"- `update_page` against `index.md` if you add/update any page\n\n"
        f"<<<SOURCE>>>\n{source_text}\n<<<END SOURCE>>>\n"
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
def _call_openai(client: OpenAI, system_prompt: str, user_message: str) -> dict:
    resp = client.chat.completions.create(
        model=INGEST_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_schema", "json_schema": ACTIONS_SCHEMA},
        temperature=0.2,
    )
    return json.loads(resp.choices[0].message.content)


def _apply_actions(wiki_out: Path, actions: list[dict]) -> None:
    for a in actions:
        target = wiki_out / a["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        content = a["content"].rstrip() + "\n"

        if a["type"] == "create_page":
            if target.exists():
                console.print(f"  [yellow]already exists, switching to append-update[/]: {a['path']}")
                with target.open("a", encoding="utf-8") as f:
                    f.write("\n\n---\n\n" + content)
            else:
                target.write_text(content, encoding="utf-8")
        elif a["type"] == "update_page":
            mode = a.get("mode", "append")
            if mode == "overwrite":
                target.write_text(content, encoding="utf-8")
            else:
                with target.open("a", encoding="utf-8") as f:
                    f.write("\n\n" + content)
        elif a["type"] == "append_log":
            with (wiki_out / "log.md").open("a", encoding="utf-8") as f:
                f.write("\n" + content)
        elif a["type"] == "flag_contradiction":
            with (wiki_out / "contradictions.md").open("a", encoding="utf-8") as f:
                f.write("\n- " + content)


def ingest_document(client: OpenAI, system_prompt: str, doc: dict, data_root: Path, wiki_out: Path) -> int:
    """Returns number of actions applied."""
    pdf_path = data_root / doc["filename"]
    if not pdf_path.exists():
        console.print(f"  [red]MISSING file[/]: {pdf_path}")
        return 0

    source_text = extract(pdf_path)
    # Crude token guard — gpt-4o-mini tokenizer is roughly 4 chars/token for English.
    if len(source_text) > MAX_SOURCE_TOKENS * 4:
        console.print(f"  [yellow]truncating large source[/]: {doc['filename']}")
        source_text = source_text[: MAX_SOURCE_TOKENS * 4]

    index_md = (wiki_out / "index.md").read_text(encoding="utf-8")
    source_page_path = wiki_out / "pages" / "sources" / f"{doc['id']}.md"
    user_message = _build_user_message(doc, source_text, index_md, source_page_path)

    result = _call_openai(client, system_prompt, user_message)
    actions = result.get("actions", [])
    _apply_actions(wiki_out, actions)
    return len(actions)


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    parser = argparse.ArgumentParser(description="Run the wiki ingest agent over a manifest.")
    parser.add_argument("--manifest", type=Path, required=True, help="Path to manifest_public.json, or 'AUTO' for full.")
    parser.add_argument("--wiki-out", type=Path, required=True, help="Directory to write wiki/ into.")
    parser.add_argument("--data-root", type=Path, required=True, help="Directory containing source files referenced by the manifest.")
    parser.add_argument("--new-only", action="store_true", help="Skip sources already in log.md.")
    args = parser.parse_args()

    if "OPENAI_API_KEY" not in os.environ:
        console.print("[red]OPENAI_API_KEY not set in environment[/]")
        return 2

    client = OpenAI()
    system_prompt = (Path(__file__).parent / "prompts" / "ingest_system.md").read_text(encoding="utf-8")

    _seed_wiki(args.wiki_out)
    already = _already_ingested(args.wiki_out) if args.new_only else set()

    docs = _load_manifest(args.manifest, args.data_root)
    todo = [d for d in docs if d["id"] not in already]

    console.print(f"[bold]Ingest:[/] manifest={args.manifest.name} variant={args.wiki_out.name}")
    console.print(f"  manifest docs: {len(docs)}; already ingested: {len(already)}; to ingest: {len(todo)}")

    if not todo:
        console.print("[green]Nothing to do.[/]")
        return 0

    total_actions = 0
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TextColumn("{task.completed}/{task.total}")) as p:
        task = p.add_task("Ingesting…", total=len(todo))
        for doc in todo:
            p.update(task, description=f"  {doc['id'][:48]}")
            n = ingest_document(client, system_prompt, doc, args.data_root, args.wiki_out)
            total_actions += n
            p.advance(task)

    console.print(f"[green]Done.[/] Applied {total_actions} actions across {len(todo)} sources.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
