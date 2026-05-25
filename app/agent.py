"""OpenAI function-calling agent loop for Amos.

Caps iterations at MAX_ITERATIONS to prevent the model spinning on `read_wiki_page`
for missing pages. Returns the final assistant message text plus a list of tool
calls performed (for logging/observability).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.tools import TOOL_SCHEMAS, dispatch


CHAT_MODEL = os.environ.get("CHAT_MODEL", "gpt-4o")
MAX_ITERATIONS = 5

_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "amos_system.md").read_text(encoding="utf-8")


@dataclass
class AgentResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


def _client() -> OpenAI:
    return OpenAI()


def run(history: list[dict], user_message: str, on_tool_call=None) -> AgentResult:
    """Run the agent for one user turn.

    `history` is a list of previous OpenAI messages (excluding the new user message).
    `on_tool_call(name, args)` is an optional callback (used by Chainlit to surface
    a status indicator while tools run).
    """
    client = _client()
    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}, *history, {"role": "user", "content": user_message}]

    tool_log: list[dict] = []
    total_in = 0
    total_out = 0

    for iteration in range(MAX_ITERATIONS):
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.3,
        )
        usage = getattr(resp, "usage", None)
        if usage:
            total_in += usage.prompt_tokens
            total_out += usage.completion_tokens

        choice = resp.choices[0]
        msg = choice.message
        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in (msg.tool_calls or [])
                ],
            }
        )

        if not msg.tool_calls:
            # Final answer reached.
            return AgentResult(text=msg.content or "", tool_calls=tool_log, input_tokens=total_in, output_tokens=total_out)

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if on_tool_call:
                try:
                    on_tool_call(name, args)
                except Exception:
                    pass
            try:
                result = dispatch(name, args)
                if not isinstance(result, str):
                    result_str = json.dumps(result, ensure_ascii=False, default=str)
                else:
                    result_str = result
                # Cap tool result size for context safety.
                if len(result_str) > 12000:
                    result_str = result_str[:12000] + "\n\n[... truncated]"
            except Exception as e:
                result_str = f"ERROR: {type(e).__name__}: {e}"

            tool_log.append({"name": name, "args": args, "result_preview": result_str[:300]})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})

    # Iteration cap hit — make one more non-tool call to coax a final answer.
    messages.append(
        {
            "role": "system",
            "content": "You have reached the tool-call limit. Produce your best final answer now using the information already gathered. Cite sources from the tool outputs above.",
        }
    )
    resp = client.chat.completions.create(model=CHAT_MODEL, messages=messages, temperature=0.3)
    usage = getattr(resp, "usage", None)
    if usage:
        total_in += usage.prompt_tokens
        total_out += usage.completion_tokens
    return AgentResult(
        text=resp.choices[0].message.content or "",
        tool_calls=tool_log,
        input_tokens=total_in,
        output_tokens=total_out,
    )
