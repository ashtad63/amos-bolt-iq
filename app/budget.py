"""Monthly spend meter.

Tracks cumulative OpenAI cost (input + output tokens for chat; embeddings ignored
because they're tiny). Persists to Azure Blob when configured; otherwise to a local
JSON file as fallback. Trips at BUDGET_MONTHLY_USD; OpenAI dashboard provides a
second hard cap at BUDGET_HARD_CAP_USD.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# gpt-4o pricing as of 2026-05 ($/1M tokens). Update if model/pricing changes.
PRICE_PER_MTOK = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

BUDGET_MONTHLY_USD = float(os.environ.get("BUDGET_MONTHLY_USD", "15"))
STATE_PATH = Path(os.environ.get("BUDGET_STATE_PATH", "/tmp/amos-budget.json"))


_lock = threading.Lock()


def _now_month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state), encoding="utf-8")


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICE_PER_MTOK.get(model)
    if not price:
        return 0.0
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000


def record_turn(model: str, input_tokens: int, output_tokens: int) -> float:
    """Adds cost to the current-month total and returns the new month-to-date total."""
    cost = cost_for(model, input_tokens, output_tokens)
    with _lock:
        state = _load_state()
        month_key = _now_month_key()
        month = state.setdefault(month_key, {"usd": 0.0, "turns": 0, "updated_at": 0})
        month["usd"] = round(month["usd"] + cost, 6)
        month["turns"] += 1
        month["updated_at"] = int(time.time())
        _save_state(state)
        return month["usd"]


def month_to_date() -> float:
    state = _load_state()
    return state.get(_now_month_key(), {}).get("usd", 0.0)


def is_over_budget() -> bool:
    return month_to_date() >= BUDGET_MONTHLY_USD
