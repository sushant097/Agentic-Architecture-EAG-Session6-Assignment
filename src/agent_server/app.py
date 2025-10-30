import os
import logging
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import AgentRequest, AgentResponse, Turn
from .memory import memory as memory_store
from .decision import plan_next_step, force_finalize
from .action import run_tool

os.makedirs("logs", exist_ok=True)

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
handlers = [
    logging.StreamHandler(),
    RotatingFileHandler("logs/agent.log", maxBytes=1_000_000, backupCount=3)
]
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=handlers)
logger = logging.getLogger("agent_app")


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

MAX_STEPS = 8              # planner iterations
MAX_TOOL_CALLS = 12         # hard cap on tool use per request
TRUNCATE_TOOL_LINES = 12   # show only first N lines in transcript

@app.post("/agent", response_model=AgentResponse)
def agent(req: AgentRequest):
    # Load existing state
    turns = memory_store.get_turns(req.session_id)
    # Save/refresh prefs (optional UI later)
    if req.prefs:
        memory_store.set_prefs(req.session_id, req.prefs)
    prefs = memory_store.get_prefs(req.session_id)

    # Append user turn
    user_turn = Turn(role="user", content=req.query)
    memory_store.add_turn(req.session_id, user_turn)
    logger.info("TURN ADDED: %s %s%s",
            t.role if (t:=user_turn) else "",  # for user_turn block
            t.tool_name or "",
            f" | {t.content[:200]}...")
    turns.append(user_turn)
    
    # >>> NEW: continue-only mode (no new tools)
    if req.continue_only or not req.allow_tools:
        final_answer = force_finalize(turns, req.ticker, req.days, prefs)
        assistant_turn = Turn(role="assistant", content=final_answer)
        memory_store.add_turn(req.session_id, assistant_turn)
        turns.append(assistant_turn)

        # build transcript & return
        lines = ["# Agent Transcript"]
        for t in turns:
            if t.role == "user":
                lines.append(f"**User:** {t.content}")
            elif t.role == "assistant":
                lines.append(f"**Assistant:** {t.content}")
            elif t.role == "tool":
                body = t.content.splitlines()
                trunc = "\n".join(body[:TRUNCATE_TOOL_LINES])
                if len(body) > TRUNCATE_TOOL_LINES:
                    trunc += "\n... (truncated)"
                lines.append(f"**Tool `{t.tool_name}` Result:**\n\n```\n{trunc}\n```")
        return AgentResponse(pretty="\n\n".join(lines), turns=turns)
    else:
        tool_calls = 0
        final_answer = None

        for _ in range(MAX_STEPS):
            step = plan_next_step(turns, req.ticker, req.days, prefs)

            if step.tool_call:
                if tool_calls >= MAX_TOOL_CALLS:
                    final_answer = "Reached tool-call limit. Providing best effort summary."
                    break
                name = step.tool_call.name
                args = step.tool_call.args
                # Ensure default args are present
                if "ticker" not in args:
                    args["ticker"] = req.ticker
                if "days" not in args and name in ("ticker_info", "news_vs_price"):
                    args["days"] = req.days

                logging.info(f"Calling tool: {name} args={args}")
                out = run_tool(name, args)
                # Add tool turn (truncated in transcript)
                tool_turn = Turn(role="tool", tool_name=name, content=out)
                memory_store.add_turn(req.session_id, tool_turn)
                turns.append(tool_turn)
                tool_calls += 1
                continue

            if step.final_answer is not None:
                final_answer = step.final_answer
                assistant_turn = Turn(role="assistant", content=final_answer)
                memory_store.add_turn(req.session_id, assistant_turn)
                turns.append(assistant_turn)
                break

        # If loop ended without final answer, force one
        if final_answer is None:
            final_answer = force_finalize(turns, req.ticker, req.days, prefs)
            assistant_turn = Turn(role="assistant", content=final_answer)
            memory_store.add_turn(req.session_id, assistant_turn)
            turns.append(assistant_turn)

        # Build pretty transcript
        lines = ["# Agent Transcript"]
        for t in turns:
            if t.role == "user":
                lines.append(f"**User:** {t.content}")
            elif t.role == "assistant":
                lines.append(f"**Assistant:** {t.content}")
            elif t.role == "tool":
                body = t.content.splitlines()
                trunc = "\n".join(body[:TRUNCATE_TOOL_LINES])
                if len(body) > TRUNCATE_TOOL_LINES:
                    trunc += "\n... (truncated)"
                lines.append(f"**Tool `{t.tool_name}` Result:**\n\n```\n{trunc}\n```")

        return AgentResponse(pretty="\n\n".join(lines), turns=turns)

@app.get("/health")
def health_check():
    return {"status": "ok"}

def main():
    # allows: uv run agent-server
    import uvicorn
    uvicorn.run("agent_server.app:app", host="127.0.0.1", port=8080, reload=True)
