(() => {
  if (window.__TABGIST_CS_LOADED__) return;  // prevent double listeners
  window.__TABGIST_CS_LOADED__ = true;

  const parseYouTube = () => {
  try {
    const u = new URL(window.location.href);
    const host = u.hostname;
    const isYT = host.includes("youtube.com") || host.includes("youtu.be") || host.includes("music.youtube.com");
    if (!isYT) return { isYouTube: false, videoId: null };

    // watch?v=ID
    const vid = u.searchParams.get("v");
    if (vid) return { isYouTube: true, videoId: vid };

    // youtu.be/ID
    if (host.includes("youtu.be")) {
      const id = u.pathname.split("/").filter(Boolean)[0];
      if (id) return { isYouTube: true, videoId: id };
    }

    // /shorts/ID
    const parts = u.pathname.split("/").filter(Boolean);
    const si = parts.indexOf("shorts");
    if (si >= 0 && parts[si + 1]) return { isYouTube: true, videoId: parts[si + 1] };

    return { isYouTube: true, videoId: null };
  } catch {
    return { isYouTube: false, videoId: null };
  }
};

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "EXTRACT") {
    const yt = parseYouTube();
    sendResponse({
      url: window.location.href,
      title: document.title || "",
      isYouTube: yt.isYouTube,
      videoId: yt.videoId,
      text: yt.isYouTube ? "" : (document.body?.innerText || "").trim()
    });
  }
  return true;
});

})();
