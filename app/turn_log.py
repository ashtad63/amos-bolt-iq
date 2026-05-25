"""Per-turn conversation logging to Azure Blob (or local file fallback).

Each line is one JSON object per chat turn. Useful for showcasing during the
interview ("here are the kinds of questions Amos got, here's a latency histogram").
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from azure.storage.blob import BlobServiceClient
    _HAS_AZURE = True
except Exception:
    _HAS_AZURE = False


_AZ_CONN = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
_AZ_CONTAINER = os.environ.get("AZURE_LOG_CONTAINER", "amos-conversations")
_LOCAL_DIR = Path(os.environ.get("LOCAL_LOG_DIR", "/tmp/amos-logs"))


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _blob_service() -> Any:
    if not (_HAS_AZURE and _AZ_CONN):
        return None
    return BlobServiceClient.from_connection_string(_AZ_CONN)


def _append_local(entry: dict) -> None:
    _LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    path = _LOCAL_DIR / f"{_today_key()}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _append_blob(entry: dict) -> bool:
    svc = _blob_service()
    if svc is None:
        return False
    try:
        container = svc.get_container_client(_AZ_CONTAINER)
        try:
            container.create_container()
        except Exception:
            pass
        blob_name = f"{_today_key()}.jsonl"
        blob = container.get_blob_client(blob_name)
        # Append-blob: create if missing, then append a line.
        try:
            blob.create_append_blob()
        except Exception:
            pass
        blob.append_block((json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8"))
        return True
    except Exception:
        return False


def log_turn(
    user_msg: str,
    assistant_msg: str,
    tool_calls: list[dict],
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    ip_hash: str,
    variant: str,
) -> None:
    entry = {
        "ts": int(time.time()),
        "iso": datetime.now(timezone.utc).isoformat(),
        "variant": variant,
        "ip_hash": ip_hash,
        "user_msg": user_msg,
        "assistant_msg": assistant_msg,
        "tool_calls": tool_calls,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
    }
    if not _append_blob(entry):
        _append_local(entry)
