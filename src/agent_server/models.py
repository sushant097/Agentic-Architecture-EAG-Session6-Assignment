from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, List, Dict, Any

# --- Conversation / Agent Models ---
class Turn(BaseModel):
    role: str # "user" | "assistant" | "tool"
    content: str
    tool_name: Optional[str] = None

class UserPrefs(BaseModel):
    # keep simple for now, can extend later (sources, thresholds, etc.)
    tickers : List[str] = Field(default_factory=list)


class AgentRequest(BaseModel):
    query: str
    ticker: str = "AAPL"
    days: int = 30
    turns: List[Turn] = Field(default_factory=list)
    prefs: Optional[UserPrefs] = None
    session_id: str = "default"

    # NEW:
    continue_only: bool = False    # If True, do NOT call tools; just finalize using history
    allow_tools: bool = True       # If False, same as above (kept for flexibility)


class AgentResponse(BaseModel):
    pretty: str
    turns: List[Turn]


# --- Planner Protocol ----
class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any] = Field(default_factory=dict)

class PlanStep(BaseModel):
    # Exactly one of these should be set
    tool_call: Optional[ToolCall] = None
    final_answer: Optional[str] = None


# --- Tool I/O Models ---
class TickerInfoIn(BaseModel):
    ticker: str
    days: int = 30

class TickerInfoOut(BaseModel):
    summary: str

class NewsVsPriceIn(BaseModel):
    ticker: str
    days: int = 30

class NewsVsPriceOut(BaseModel):
    markdown_table: str

class SummarizedNewsIn(BaseModel):
    headline: str

class SummarizedNewsOut(BaseModel):
    summary: str