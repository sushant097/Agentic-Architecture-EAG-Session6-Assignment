
# 🧠 Agentic Ticker Research — Multi-Step AI Stock Analyst

A lightweight **Agentic AI backend** built using **FastAPI**, **Gemini LLM**, and **uv** package manager.
It powers a Chrome Extension that can perform **multi-step, reasoning-based stock research**, combining **news, prices, and analysis** through an agentic feedback loop.

---

## ⚡ Overview

This backend runs an **agentic workflow** for stock tickers (AAPL, TSLA, NVDA, etc.).
Given a query like:

> “Find the latest news about AAPL and link it with its price changes in the last 30 days.”

The system doesn’t just summarize — it acts like an **autonomous financial analyst**:

1. Collects the stock’s recent **price trend**
2. Fetches and links **recent news headlines** from Yahoo Finance
3. Summarizes those headlines one by one
4. Links them to the stock’s movement
5. Returns a final reasoning-based analysis

---

## 🧩 Project Structure

The architecture follows the classic **Agentic 4-layer design**:

| Layer          | File          | Description                                                                            |
| -------------- | ------------- | -------------------------------------------------------------------------------------- |
| **Perception** | `app.py`      | The main FastAPI orchestrator. Receives queries, manages steps, and builds transcript. |
| **Memory**     | `memory.py`   | Stores ongoing conversation history (turns) and user preferences per session.          |
| **Decision**   | `decision.py` | Uses Gemini as the planner. Decides whether to call a tool or finalize an answer.      |
| **Action**     | `action.py`   | Houses tools: `ticker_info`, `news_vs_price`, `summarize_news`, and LLM utility.       |
| **Schemas**    | `models.py`   | Defines all Pydantic I/O models for typed communication between layers.                |

---

## ⚙️ Setup with **uv**

### 1. Initialize and sync dependencies

```bash
uv sync
```

### 2. Add the Gemini API key

```
GEMINI_API_KEY=your_api_key_here
```

inside `.env`

### 3. Run the API

```bash
uv run agent-server
```

or directly:

```bash
uv run uvicorn agent_server.app:app --reload --port 8080
```

---

## 🧠 Agent Flow (Step-by-Step)

### 1. User Query

The extension sends a POST request to `/agent` with fields like:

```json
{
  "query": "Find the news about AAPL in the last 30 days and link it with price changes.",
  "ticker": "AAPL",
  "days": 30,
  "session_id": "demo"
}
```

### 2. Decision Layer (Planner)

Gemini reads the context and decides one of:

* `FUNCTION_CALL: ticker_info|ticker=AAPL|days=30`
* `FUNCTION_CALL: news_vs_price|ticker=AAPL|days=30`
* `FUNCTION_CALL: summarize_news|headline="Apple delays iPhone 17"`
* `FINAL_ANSWER: <text>`

This is the **core reasoning loop** — each decision is recorded as a conversation “turn”.

---

### 3. Tools in Action

#### 🪙 `ticker_info`

Fetches recent stock data:

```
AAPL Price Info (last 30d):
- Latest close: 255.46
- Change over 30d: -1.12%
- High: 263.10, Low: 249.32
```

#### 📰 `news_vs_price`

Collects the latest news headlines and aligns them with trading dates:

```
# News vs Price — AAPL (last 30d)
Date | Close | % Change | Headline
--- | ---:| ---:| ---
2025-09-26 | 255.46 | -1.00% | [UBS reiterates Neutral, $220 PT on iPhone 17 data](...)
2025-09-27 | 255.46 | -1.00% | [AI Semiconductor Stock May Join Nvidia, Apple in $2T Club](...)
```

#### ✍️ `summarize_news`

For each headline, the agent expands the meaning:

```
UBS reiterates Neutral... → UBS expects stable performance; no major upside projected for AAPL.
AI Semiconductor... → Market optimism in AI sector indirectly includes Apple.
```

---

### 4. Feedback Loop

Each tool result is fed back into Gemini.
The LLM sees both *data* and *its past reasoning*, allowing multi-turn improvement.

Typical loop:

```
Step 1 → Call ticker_info
Step 2 → Call news_vs_price
Step 3 → Call summarize_news (multiple times)
Step 4 → Generate FINAL_ANSWER
```

Capped at **MAX_STEPS = 3** and **MAX_TOOL_CALLS = 6**.

---

## 🧾 Sample Output

### Input

```
Find the news about AAPL in the last 30 days and link it with daily stock price changes.
```

### Output

```
# Agent Transcript

**User:** Find the news about AAPL in the last 30 days and link it with daily stock price changes.

**Tool `ticker_info` Result:**
AAPL Price Info (last 30d):
- Latest close: 255.46
- Change over 30d: -1.12%
- High: 263.10, Low: 249.32

**Tool `news_vs_price` Result:**
# News vs Price — AAPL (last 30d)
2025-09-26 | 255.46 | -1.00% | Apple (AAPL) Stock: UBS Reiterates Neutral...
2025-09-27 | 255.46 | -1.00% | AI Semiconductor Stock Will Join Nvidia, Apple...

**Tool `summarize_news` Result:**
Apple (AAPL) Stock... → UBS expects weaker iPhone demand, maintaining neutral outlook.

**Assistant:**
AAPL saw a minor decline around Sep 26–27. The UBS Neutral rating likely caused short-term selling, while positive AI-related headlines offset part of the sentiment. Overall, market confidence remained stable.
```

---

## 🧩 Key Features

| Feature                     | Description                                                                                |
| --------------------------- | ------------------------------------------------------------------------------------------ |
| **Gemini-driven reasoning** | Planner follows a deterministic protocol using `FUNCTION_CALL:` and `FINAL_ANSWER:` lines. |
| **Multi-step loop**         | Planner–tool–planner loop with caps to avoid runaway calls.                                |
| **Tool abstraction**        | Each tool is independent and validated through Pydantic schemas.                           |
| **Transcript memory**       | Every agent turn is stored in memory for feedback and re-prompting.                        |
| **Readable output**         | Markdown transcript built for direct display in Chrome extension.                          |
| **Resilient LLM calls**     | Handles overload errors (503s), truncates long prompts, retries gracefully.                |

---

## 🏗️ File Workflow

```
┌───────────────┐
│ Chrome Popup  │
│ (user query)  │
└──────┬────────┘
       │ POST /agent
       ▼
┌───────────────┐
│ app.py        │  ← Orchestrator (Perception)
│  • Receives request
│  • Loads prefs
│  • Iterates planner loop
└──────┬────────┘
       ▼
┌───────────────┐
│ decision.py   │  ← Decision Layer
│  • LLM Planner
│  • Produces FUNCTION_CALL or FINAL_ANSWER
└──────┬────────┘
       ▼
┌───────────────┐
│ action.py     │  ← Action Layer
│  • Runs tools
│  • Summarize / Fetch news / Price
└──────┬────────┘
       ▼
┌───────────────┐
│ memory.py     │  ← Memory Layer
│  • Stores turns + prefs
└──────┬────────┘
       ▼
📤 Returns → Markdown transcript (displayed in Chrome extension)
```

---

## 🧠 Logging

All server-side operations use structured logging instead of prints:

* Logs LLM calls, tool executions, and outputs (truncated)
* Helps trace reasoning chain
* Simplifies debugging and grading

Example:

```
2025-10-29 21:45:11 INFO Calling tool: news_vs_price args={'ticker': 'AAPL', 'days': 30}
2025-10-29 21:45:17 INFO Planner step decided: summarize_news
```

---

## 🧰 Tech Stack

| Component   | Technology                       |
| ----------- | -------------------------------- |
| Language    | Python 3.11+                     |
| Environment | uv package manager               |
| Framework   | FastAPI                          |
| LLM         | Gemini 2.0 Flash                 |
| Data        | yfinance, pandas                 |
| Validation  | Pydantic                         |
| Infra       | Local / Chrome Extension backend |

---

## 🧩 Next Steps (Planned)

* Integrate with Chrome extension popup to pass ticker + prefs.
* Allow multiple tickers comparison.
* Store transcript history in a small SQLite or DynamoDB table.
* Add continuous monitoring mode (price alert triggers).

---

### 🧱 Folder Layout

```
agentic-ticker-agent/
├─ agent_server/
│  ├─ app.py          # FastAPI entrypoint (Perception)
│  ├─ models.py       # Pydantic models
│  ├─ memory.py       # Memory store
│  ├─ decision.py     # LLM planner (Decision)
│  └─ action.py       # Tool layer (Action)
├─ pyproject.toml
├─ uv.lock
├─ .env
└─ README.md
```

---

## ✅ Summary

This backend demonstrates a **complete agentic reasoning loop** applied to stock research.
Instead of a single LLM call, it uses **multi-turn, feedback-based planning** — fetching, summarizing, and analyzing information step by step.

The result is a transparent, explainable, and extensible **AI financial agent** ready for Chrome extension integration or further autonomous experimentation.