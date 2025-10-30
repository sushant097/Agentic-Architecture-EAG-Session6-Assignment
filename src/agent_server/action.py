import os
import math
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

import pandas as pd
import yfinance as yf
from google import genai
from google.genai import types
from mcp.server.fastmcp import FastMCP

from dotenv import load_dotenv

from .models import (
    TickerInfoIn, TickerInfoOut,
    NewsVsPriceIn, NewsVsPriceOut,
    SummarizedNewsIn, SummarizedNewsOut
)

load_dotenv()
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")


# ---------------- MCP server wrapper ----------------
mcp = FastMCP("ticker-tools")  # server name shown to clients


# init Gemini client (safe reuse)
try:
    _client = genai.Client()
except Exception:
    _client = None

def _llm_small(text: str, max_chars: int = 3500) -> str:
    """Token-safe LLM call with truncation + graceful errors."""
    if not _client:
        return f"[LLM disabled] {text[:500]}"
    safe_text = text[-max_chars:]
    try:
        r = _client.models.generate_content(
            model="gemini-2.0-flash",
            contents=safe_text,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            ),
        )
        return (r.text or "").strip()
    except Exception as e:
        if "UNAVAILABLE" in str(e) or "503" in str(e):
            return "[LLM busy] Gemini service is overloaded. Please retry in a minute."
        return f"[LLM error] {e}"
    
# ---------- Tools ----------
def tool_ticker_info(inp: TickerInfoIn) -> TickerInfoOut:
    t = yf.Ticker(inp.ticker)
    start = (datetime.utcnow() - timedelta(days=inp.days)).date()
    end = datetime.utcnow().date()
    hist = t.history(start=str(start), end=str(end), auto_adjust=False)
    if hist.empty:
        return TickerInfoOut(summary=f"No price data available for {inp.ticker}.")

    closes = hist["Close"]
    closes.index = closes.index.tz_localize(None)  # drop tz
    latest = closes.iloc[-1]
    change_pct = (latest - closes.iloc[0]) / closes.iloc[0] * 100
    high, low = closes.max(), closes.min()

    summary = (
        f"{inp.ticker.upper()} Price Info (last {inp.days}d):\n"
        f"- Latest close: {latest:.2f}\n"
        f"- Change over {inp.days}d: {change_pct:+.2f}%\n"
        f"- High: {high:.2f}, Low: {low:.2f}"
    )
    return TickerInfoOut(summary=summary)


def _fetch_company_news(symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Normalize Yahoo Finance news across versions."""
    try:
        t = yf.Ticker(symbol)
        raw = t.news or []
        items: List[Dict[str, Any]] = []
        for it in raw:
            c = it.get("content") or {}
            title = c.get("title") or it.get("title") or c.get("summary")
            url = (
                (c.get("clickThroughUrl") or {}).get("url")
                or (c.get("canonicalUrl") or {}).get("url")
                or it.get("link")
                or it.get("url")
            )
            provider = (
                (c.get("provider") or {}).get("displayName")
                or it.get("publisher")
                or (it.get("provider") or {}).get("name")
                or ""
            )
            pub = (
                c.get("pubDate")
                or c.get("displayTime")
                or it.get("providerPublishTime")
                or it.get("published_at")
            )
            dt = None
            if isinstance(pub, (int, float)):
                try:
                    dt = datetime.utcfromtimestamp(int(pub)).date()
                except Exception:
                    pass
            elif isinstance(pub, str):
                try:
                    dt = datetime.fromisoformat(pub.replace("Z", "")).date()
                except Exception:
                    pass
            if title and url:
                items.append({"title": title, "url": url, "provider": provider, "date": dt})
        return items[:limit]
    except Exception as e:
        return [{"title": f"[news fetch error] {e}", "url": "", "provider": "", "date": None}]
    


def tool_news_vs_price(inp: NewsVsPriceIn) -> NewsVsPriceOut:
    """Get news + link to nearest trading day close & % change. Returns markdown."""
    news_items = _fetch_company_news(inp.ticker, limit=15)

    t = yf.Ticker(inp.ticker)
    start = (datetime.utcnow() - timedelta(days=inp.days + 3)).date()
    end = datetime.utcnow().date()
    hist = t.history(start=str(start), end=str(end), auto_adjust=False)

    closes = hist["Close"].round(2)
    closes.index = closes.index.tz_localize(None)  # normalize tz
    pct = closes.pct_change().round(2) * 100

    rows = []
    for it in news_items:
        d = it.get("date")
        close, change = float("nan"), float("nan")
        if d:
            dt = pd.to_datetime(str(d))
            # map to nearest trading day to avoid weekends/holidays
            idx = closes.index.get_indexer([dt], method="nearest")[0]
            if idx != -1:
                close = float(closes.iloc[idx])
                change = float(pct.iloc[idx]) if idx < len(pct) else 0.0
        rows.append((str(d) if d else "-", it["title"], close, change, it.get("url")))

    out = [
        f"# News vs Price — {inp.ticker.upper()} (last {inp.days}d)",
        "Date | Close | % Change | Headline",
        "--- | ---:| ---:| ---",
    ]
    for d, title, close, change, url in rows:
        cs = "" if math.isnan(close) else f"{close:.2f}"
        ch = "" if math.isnan(change) else f"{change:.2f}%"
        link = f"[{title}]({url})" if url else title
        out.append(f"{d} | {cs} | {ch} | {link}")

    return NewsVsPriceOut(markdown_table="\n".join(out))

def tool_summarize_news(inp: SummarizedNewsIn) -> SummarizedNewsOut:
    """Expand a headline into 1–2 sentence summary via LLM (no scraping)."""
    prompt = f"Expand this headline into a 1-2 sentence, factual summary. Avoid hype:\n\n{inp.headline}"
    summary = _llm_small(prompt, max_chars=1500)
    return SummarizedNewsOut(summary=summary)

# public dispatch (string name -> callable)
TOOLS = {
    "ticker_info": tool_ticker_info,
    "news_vs_price": tool_news_vs_price,
    "summarize_news": tool_summarize_news,
}

def run_tool(name: str, args: dict) -> str:
    """Execute a tool by name with dict args and return a DISPLAY string."""
    try:
        if name == "ticker_info":
            out = tool_ticker_info(TickerInfoIn(**args)).summary
            return out
        if name == "news_vs_price":
            out = tool_news_vs_price(NewsVsPriceIn(**args)).markdown_table
            return out
        if name == "summarize_news":
            out = tool_summarize_news(SummarizedNewsIn(**args)).summary
            return out
        return f"[tool error] Unknown tool: {name}"
    except Exception as e:
        logging.exception("Tool execution failed")
        return f"[tool error] {type(e).__name__}: {e}"
    


@mcp.tool()
def ticker_info(ticker: str, days: int = 30) -> dict:
    """Return price summary for a ticker (MCP shape: plain JSON)."""
    out = tool_ticker_info(TickerInfoIn(ticker=ticker, days=days))
    return out.model_dump()  # {"summary": ...}

@mcp.tool()
def news_vs_price(ticker: str, days: int = 30) -> dict:
    """Return markdown table mapping news to nearest close."""
    out = tool_news_vs_price(NewsVsPriceIn(ticker=ticker, days=days))
    return out.model_dump()  # {"markdown_table": ...}

@mcp.tool()
def summarize_news(headline: str) -> dict:
    """LLM summary for a headline (1–2 sentences)."""
    out = tool_summarize_news(SummarizedNewsIn(headline=headline))
    return out.model_dump()  # {"summary": ...}

def run_mcp():
    """Entry point so `uv run mcp-server` starts the MCP server."""
    mcp.run()