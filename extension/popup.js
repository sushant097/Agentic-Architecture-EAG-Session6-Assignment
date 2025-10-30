const els = {
  serverUrl: document.getElementById("serverUrl"),
  sessionId: document.getElementById("sessionId"),
  prefTickers: document.getElementById("prefTickers"),
  agentTicker: document.getElementById("agentTicker"),
  agentDays: document.getElementById("agentDays"),
  agentQuery: document.getElementById("agentQuery"),
  runAgent: document.getElementById("runAgent"),
  runAgentAgain: document.getElementById("runAgentAgain"),
  resetTranscript: document.getElementById("resetTranscript"),
  status: document.getElementById("status"),
  output: document.getElementById("output"),
};

let agentTurns = []; // transcript memory (kept in chrome.storage.local per session)
let lastBody = null; // last request body (to “continue”)

function setStatus(msg, type="") {
  els.status.textContent = msg;
  els.status.className = type;
}

function mdToHtml(md) {
  // super-lightweight markdown-ish rendering
  return md
    .replace(/^# (.*)$/gm, "<h3>$1</h3>")
    .replace(/\*\*(.*?)\*\*/g, "<b>$1</b>")
    .replace(/```([\s\S]*?)```/g, "<pre>$1</pre>")
    .replace(/\n/g, "<br>");
}
function render(pretty) { els.output.innerHTML = mdToHtml(pretty || ""); }

async function saveSettings() {
  const serverUrl = els.serverUrl.value.trim();
  const sessionId = (els.sessionId.value || "default").trim();
  const prefTickers = (els.prefTickers.value || "")
    .split(",")
    .map(s => s.trim().toUpperCase())
    .filter(Boolean);

  await chrome.storage.local.set({ serverUrl, sessionId, prefTickers });
  return { serverUrl, sessionId, prefTickers };
}

async function loadSettings() {
  const data = await chrome.storage.local.get(["serverUrl", "sessionId", "prefTickers", "turnsBySession"]);
  if (data.serverUrl) els.serverUrl.value = data.serverUrl;
  if (data.sessionId) els.sessionId.value = data.sessionId;
  if (Array.isArray(data.prefTickers)) els.prefTickers.value = data.prefTickers.join(", ");
  // restore transcript for current session
  const sid = (els.sessionId.value || "default").trim();
  const map = data.turnsBySession || {};
  agentTurns = Array.isArray(map[sid]) ? map[sid] : [];
}

async function persistTranscript(sessionId) {
  const data = await chrome.storage.local.get(["turnsBySession"]);
  const map = data.turnsBySession || {};
  map[sessionId] = agentTurns;
  await chrome.storage.local.set({ turnsBySession: map });
}

function buildBody({ query, ticker, days, prefs, sessionId, turns }) {
  return {
    query,
    ticker,
    days,
    prefs: { tickers: prefs || [] },
    session_id: sessionId,
    turns: turns || [],
  };
}

async function runAgent({ continueRun = false } = {}) {
  try {
    setStatus("Calling agent…");
    const { serverUrl, sessionId, prefTickers } = await saveSettings();
    const base = serverUrl.replace(/\/+$/, "");

    const ticker = (els.agentTicker.value || "AAPL").toUpperCase();
    const days = parseInt(els.agentDays.value || "30", 10);
    const queryDefault = `Find the news about ${ticker} in the last ${days} days and link it with daily stock price changes.`;
    const query = (els.agentQuery.value || queryDefault).trim();

    // Always rebuild the body so updated query is respected
    const body = buildBody({
      query, ticker, days, prefs: prefTickers, sessionId, turns: agentTurns
    });

    // >>> NEW: when continuing, instruct server to skip tools and just answer
    if (continueRun) {
      body.continue_only = true;
      body.allow_tools = false;
    }

    const res = await fetch(base + "/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Agent error ${res.status}`);

    const data = await res.json();
    agentTurns = data.turns || [];
    lastBody = body; // keep for visibility/history; no longer reused verbatim
    await persistTranscript(body.session_id || "default");

    render(data.pretty || "");
    setStatus("Done.", "ok");
  } catch (e) {
    console.error(e);
    setStatus(e.message || String(e), "err");
  }
}


async function resetTranscript() {
  const { sessionId } = await saveSettings();
  agentTurns = [];
  await persistTranscript(sessionId);
  render("# Agent Transcript\n\n**Assistant:** Transcript cleared.");
  setStatus("Transcript cleared.", "warn");
}

els.runAgent.addEventListener("click", () => runAgent({ continueRun:false }));
els.runAgentAgain.addEventListener("click", () => runAgent({ continueRun:true }));
els.resetTranscript.addEventListener("click", resetTranscript);

loadSettings().then(() => render("")); // init
