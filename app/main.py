"""Chainlit entry point for Amos."""

from __future__ import annotations

import os
import time
from typing import Optional

import chainlit as cl
from dotenv import load_dotenv

from app import agent, budget, rate_limit, turn_log


load_dotenv()

CORPUS_VARIANT = os.environ.get("CORPUS_VARIANT", "public")
ENABLE_PASSWORD_GATE = os.environ.get("ENABLE_PASSWORD_GATE", "false").lower() == "true"
AMOS_PASSWORD = os.environ.get("AMOS_PASSWORD", "")


# --- Optional password gate (internal deployment only) ----------------------

if ENABLE_PASSWORD_GATE:

    @cl.password_auth_callback
    def auth(username: str, password: str) -> Optional[cl.User]:
        if AMOS_PASSWORD and password == AMOS_PASSWORD:
            return cl.User(identifier=username or "internal-user", metadata={"role": "internal"})
        return None


# --- Chat session lifecycle -------------------------------------------------


@cl.on_chat_start
async def on_chat_start() -> None:
    # Welcome message is injected into the empty-state DOM by public/custom.js
    # so it coexists with the starter buttons (sending a cl.Message here would
    # suppress starters in Chainlit 1.3).
    cl.user_session.set("history", [])


@cl.set_starters
async def starters() -> list[cl.Starter]:
    # No icons — the cards are text-only to keep them clean.
    return [
        cl.Starter(
            label="What is Bolt iQ?",
            message="What is Bolt iQ and how does it work?",
        ),
        cl.Starter(
            label="Why choose Predictant?",
            message="Why choose Predictant for bolt-tension measurement?",
        ),
        cl.Starter(
            label="Bi-wave vs. single-wave",
            message="Compare the bi-wave method to single-wave time-of-flight for bolt preload.",
        ),
        cl.Starter(
            label="DNV-certified accuracy",
            message="What's the DNV-certified accuracy of Bolt iQ?",
        ),
    ]


# --- Per-message handler ----------------------------------------------------


def _client_ip() -> str:
    try:
        ws = cl.context.session.client_type  # may be 'webapp' etc.
        # Chainlit hides the raw Starlette request inside context.session.user_env in newer versions;
        # we fall back to a placeholder so rate-limit still buckets sessions distinctly.
        return str(cl.context.session.id) or "unknown"
    except Exception:
        return "unknown"


@cl.on_message
async def on_message(msg: cl.Message) -> None:
    started = time.time()
    ip_token = _client_ip()

    # --- Budget gate
    if budget.is_over_budget():
        await cl.Message(
            content=(
                "I'm taking a nap — this month's demo budget has been reached. "
                "Please check back next month, or email Ashtad if you need access sooner."
            )
        ).send()
        return

    # --- Rate-limit gate
    allowed, reason = rate_limit.check_and_consume(ip_token)
    if not allowed:
        await cl.Message(content=f"Sorry, I have to slow you down — {reason}").send()
        return

    history: list[dict] = cl.user_session.get("history") or []

    # Step indicator while tools run.
    step = cl.Step(name="Amos is checking the wiki...", type="tool")
    tools_seen: list[str] = []

    def _on_tool(name: str, args: dict) -> None:
        tools_seen.append(name)
        step.output = f"Called {name}({list(args.keys())})"

    await step.send()
    try:
        result = agent.run(history, msg.content, on_tool_call=_on_tool)
    except Exception as e:
        await cl.Message(content=f"Something went wrong on my end: {type(e).__name__}: {e}").send()
        return
    finally:
        step.output = f"Tools used: {tools_seen or ['(none)']}"
        await step.update()

    # Update history
    history.append({"role": "user", "content": msg.content})
    history.append({"role": "assistant", "content": result.text})
    cl.user_session.set("history", history[-20:])  # cap to last 10 turns

    await cl.Message(content=result.text).send()

    # --- Accounting + logging
    cost = budget.cost_for(agent.CHAT_MODEL, result.input_tokens, result.output_tokens)
    budget.record_turn(agent.CHAT_MODEL, result.input_tokens, result.output_tokens)
    turn_log.log_turn(
        user_msg=msg.content,
        assistant_msg=result.text,
        tool_calls=result.tool_calls,
        latency_ms=int((time.time() - started) * 1000),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=cost,
        ip_hash=rate_limit.hash_ip(ip_token),
        variant=CORPUS_VARIANT,
    )
