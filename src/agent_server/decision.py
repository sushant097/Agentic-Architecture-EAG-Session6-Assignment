import os
import re
import logging
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

from .models import PlanStep, ToolCall, Turn, UserPrefs

load_dotenv()
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY")

try:
    _client = genai.Client()
except Exception:
    _client = None

SYSTEM = """You are an agentic planner.

OUTPUT FORMAT (MANDATORY):
- Respond with exactly ONE SINGLE LINE with NO extra text, NO markdown, NO code fences.
- The line must be either:
  FUNCTION_CALL: <tool_name>|key1=value1|key2=value2
  or
  FINAL_ANSWER: <your concise analysis>

Available tools:
- ticker_info(ticker, days)
- news_vs_price(ticker, days)
- summarize_news(headline)

Preference context:
- If user preferences are provided (PREFS), bias tool choices and summaries toward them. If not, proceed normally.

Strategy:
- Step 1: If ticker is missing or invalid → FINAL_ANSWER: ask only for the missing ticker (keep it short). If days is missing, default days=30; clamp to 1–90 if outside.
- Step 2: FUNCTION_CALL: ticker_info|ticker=<T>|days=<D>
- Step 3: If news correlation is requested or useful → FUNCTION_CALL: news_vs_price|ticker=<T>|days=<D>
- Step 4: If headlines are provided or obtainable, summarize up to 3:
         FUNCTION_CALL: summarize_news|headline="<headline>"
- Step 5: After up to 3 summaries (or near budget), output FINAL_ANSWER with concise, factual findings.

Failure & Fallbacks (MANDATORY):
- If any tool call times out, errors, or returns empty data:
  - Retry that tool ONCE with the same args if safe; otherwise skip it.
  - If essential data (e.g., ticker prices) is still unavailable → FINAL_ANSWER: state the issue briefly and suggest one next step (e.g., “try another ticker”).
- If inputs are ambiguous/conflicting (e.g., multiple tickers) → FINAL_ANSWER: ask for exactly one required clarification.
- If headlines are unavailable, skip summarize_news and proceed with available results; do not fail the whole flow.
- If you reach an iteration or token budget limit, produce the best possible FINAL_ANSWER with what you have so far.

Quality & Safety Checks:
- Before emitting, self-check: exactly one line, correct prefix, correct pipe-delimited args, no tables, no extra prose.
- Never repeat full tables; keep answers short and factual.
- If a request is unsupported by the tools, FINAl_ANSWER a brief limitation + one actionable alternative.

DO NOT output anything except the single required line. If Explanation required, at most 3 lines.

"""

def _latest_user_message(turns: list[Turn]) -> str:
    for t in reversed(turns):
        if t.role == "user" and (t.content or "").strip():
            return t.content.strip()
    return ""


def _extract_command_line(text: str) -> str | None:
    """Return the first line that starts with FUNCTION_CALL: or FINAL_ANSWER:.
    Tolerates code fences and extra chatter."""
    if not text:
        return None
    # strip code fences if any
    text = re.sub(r"^\s*```(?:[a-zA-Z]+)?\s*|\s*```\s*$", "", text, flags=re.MULTILINE)
    # split into lines and scan
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("FUNCTION_CALL:") or s.startswith("FINAL_ANSWER:"):
            return s
    # try to find anywhere in body
    m = re.search(r"(FUNCTION_CALL:[^\n\r]+|FINAL_ANSWER:[^\n\r]+)", text)
    return m.group(1).strip() if m else None

def _count_tools(turns: list[Turn]) -> dict[str, int]:
    c = {"ticker_info": 0, "news_vs_price": 0, "summarize_news": 0}
    for t in turns:
        if t.role == "tool" and t.tool_name in c:
            c[t.tool_name] += 1
    return c

def _llm(text: str, max_chars: int = 3500) -> str:
    if not _client:
        return "FINAL_ANSWER: [LLM disabled]"
    safe = text[-max_chars:]
    try:
        r = _client.models.generate_content(
            model="gemini-2.0-flash",
            contents=safe,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            ),
        )
        return (r.text or "").strip()
    except Exception as e:
        logging.exception("LLM call failed")
        return "FINAL_ANSWER: [LLM error or busy]"

def _pack_history(turns: list[Turn], clip: int = 400) -> str:
    # truncate each content to avoid token bloat
    lines = []
    for t in turns:
        role = t.role.upper()
        content = (t.content or "")[:clip]
        if t.tool_name:
            role = f"TOOL {t.tool_name.upper()}"
        lines.append(f"{role}: {content}")
    return "\n".join(lines)

def plan_next_step(turns, ticker, days, prefs) -> PlanStep:
    history = _pack_history(turns)
    counts = _count_tools(turns)
    prompt = (
        f"{SYSTEM}\n\n"
        f"Context:\n- ticker={ticker} days={days}\n"
        f"- prefs={prefs.dict() if prefs else {}}\n"
        f"- tool_counts={counts}\n\n"
        f"Conversation so far:\n{history}\n\n"
        "Your turn:"
    )
    out = _llm(prompt)

    cmd = _extract_command_line(out)
    if not cmd:
        logging.warning("Planner returned unparseable output: %r", out)
        return PlanStep(final_answer="[Planner protocol error: produced unparseable output]")

    if cmd.startswith("FUNCTION_CALL:"):
        payload = cmd[len("FUNCTION_CALL:"):].strip()
        parts = [p.strip() for p in payload.split("|") if p.strip()]
        name = parts[0]
        args = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                args[k.strip()] = v.strip().strip('"')
        return PlanStep(tool_call=ToolCall(name=name, args=args))

    if cmd.startswith("FINAL_ANSWER:"):
        return PlanStep(final_answer=cmd[len("FINAL_ANSWER:"):].strip())

    # Fallback: if unparseable, force a safe final
    return PlanStep(final_answer="[Planner protocol error: produced unparseable output]")

def force_finalize(turns: list[Turn], ticker: str, days: int, prefs: Optional[UserPrefs]) -> str:
    """Coerces a FINAL_ANSWER grounded in current transcript (no tools)."""
    history = _pack_history(turns, clip=320)  # modest clip to fit context
    counts = _count_tools(turns)
    latest_user = _latest_user_message(turns)  # NEW

    prompt = (
        f"{SYSTEM}\n\n"
        "FINALIZATION INSTRUCTIONS:\n"
        "- You must output exactly one line: FINAL_ANSWER: <analysis>\n"
        "- Do NOT restate the question. Do NOT ask questions. Do NOT call tools.\n"
        "- Prioritize the LATEST USER MESSAGE below. If it narrows or changes the focus, treat it as authoritative.\n"
        "- Use ONLY information already present in the transcript/tools (no web/browsing/tools now).\n"
        "- Be concise; reference dates/numbers already shown if helpful. If evidence is insufficient, say so briefly.\n"
        "- If headlines look unrelated to the requested ticker/focus, acknowledge that.\n\n"
        f"LATEST USER MESSAGE:\n{latest_user}\n\n"  # NEW (center the new prompt)
        f"Context:\n- ticker={ticker} days={days}\n- prefs={prefs.dict() if prefs else {}}\n- tool_counts={counts}\n\n"
        f"Conversation so far:\n{history}\n\n"
        "Your turn:"
    )

    out = _llm(prompt)
    cmd = _extract_command_line(out)
    if cmd and cmd.startswith("FINAL_ANSWER:"):
        return cmd[len("FINAL_ANSWER:"):].strip()
    return (out.strip() or "[Finalization failed]")
