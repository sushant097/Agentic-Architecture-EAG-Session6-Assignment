chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(["serverUrl"], ({ serverUrl }) => {
    if (!serverUrl) chrome.storage.sync.set({ serverUrl: "http://localhost:8080" });
  });

  try {
    chrome.contextMenus.create({
      id: "agentic_research",
      title: "Agentic: Run stock research",
      contexts: ["page"]
    });
  } catch (e) {
    console.warn("contextMenus.create failed:", e);
  }
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "agentic_research") {
    chrome.action.openPopup().catch(err => console.warn("openPopup failed:", err));
  }
});
