
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

| Layer           | File             | Description                                                                 |
| --------------- | ---------------- | --------------------------------------------------------------------------- |
| **Perception**  | `app.py`         | FastAPI orchestrator — receives user query, preferences, and triggers flow. |
| **Memory**      | `memory.py`      | Caches user sessions, turns, and preferences.                               |
| **Decision**    | `decision.py`    | Planner using Gemini — produces FUNCTION_CALL or FINAL_ANSWER.              |
| **Action**      | `action.py`      | MCP tool layer — runs stock/news/summarization tools.                       |
| **Schemas**     | `models.py`      | Pydantic I/O models defining all data contracts.                            |
| **Prompt Eval** | `prompt_eval.py` | Runs Gemini-based evaluation on the system prompt.                          |

---

## 🧱 Cognitive Architecture (4 Layers)

```bash
👁️ Perceive → 🧠 Remember → 🧭 Decide → 🎯 Act
```

| Layer             | Cognitive Role                  | Implementation | Key Behavior                                                       |
| ----------------- | ------------------------------- | -------------- | ------------------------------------------------------------------ |
| 🧩 **Perception** | Understands user intent + query | `app.py`       | Parses JSON input, merges preferences, initiates loop              |
| 💭 **Memory**     | Stores past reasoning turns     | `memory.py`    | Maintains transcript + prefs per session                           |
| 🧠 **Decision**   | Plans next step or final answer | `decision.py`  | Uses Gemini with structured “FUNCTION_CALL / FINAL_ANSWER” outputs |
| ⚙️ **Action**     | Executes real-world functions   | `action.py`    | Runs MCP tools for stock, news, summarization                      |

---


## ⚙️ Setup (via **uv**)

### 1️⃣ Install dependencies

```bash
uv sync
```

### 2️⃣ Add your Gemini API key

Create a `.env` file:

```
GEMINI_API_KEY=your_api_key_here
```

### 3️⃣ Verify the system prompt

Run the Gemini verifier to ensure compliance:

```bash
uv run prompt-verify
```

Generates `prompt_evaluation.json`.

### 4️⃣ Start servers

```bash
uv run agent-server
# or start MCP tools for other agents
uv run mcp-server
```

---

## 🧠 Agent Flow (Step-by-Step)

1. **User Input:** Chrome extension sends query + preferences (likes, location, interests).
2. **Perception:** `app.py` merges prefs + query and creates a new session.
3. **Decision:** Gemini reads context and outputs one line:

   * `FUNCTION_CALL: ticker_info|ticker=AAPL|days=30`
   * `FUNCTION_CALL: summarize_news|headline="Apple delays iPhone 17"`
   * `FINAL_ANSWER: AAPL remained steady amid mixed news sentiment.`
4. **Action:** Executes tools and stores results.
5. **Memory:** Saves all turns and feedback for next iteration.
6. **Loop:** Repeats until FINAL_ANSWER is produced or limits reached.

---

## 🧰 MCP Tool Layer

`action.py` now doubles as an **MCP server**, exposing tools for both internal and external agent access.

| Tool                          | Description                                        |
| ----------------------------- | -------------------------------------------------- |
| `ticker_info(ticker, days)`   | Fetches price data using yfinance                  |
| `news_vs_price(ticker, days)` | Correlates latest news headlines with price change |
| `summarize_news(headline)`    | Uses Gemini to summarize a news headline concisely |

Run independently:

```bash
uv run mcp-server
```

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

| Component         | Technology                              |
| ----------------- | --------------------------------------- |
| **Language**      | Python 3.13+                            |
| **Environment**   | uv package manager                      |
| **Framework**     | FastAPI                                 |
| **LLM**           | Gemini 2.0 Flash                        |
| **Data**          | yfinance, pandas                        |
| **Validation**    | Pydantic                                |
| **Orchestration** | MCP tools + Agent loop                  |
| **Infra**         | Local backend / Chrome extension bridge |

---

## 🧩 Next Steps (Planned)

* Integrate with Chrome extension popup to pass ticker + prefs.
* Allow multiple tickers comparison.
* Store transcript history in a small SQLite or DynamoDB table.
* Add continuous monitoring mode (price alert triggers).

---



## 🏁 Summary

The **Agentic Ticker Research** backend demonstrates a verified, modular **Agentic Cognitive Architecture** with full **Gemini prompt validation**, **MCP tool exposure**, and **Pydantic-typed cognitive layers**.

It’s not just a stock summarizer — it’s a **self-checking, multi-step reasoning agent** that meets the standards of **explicit reasoning, structured output, and fallback robustness**.