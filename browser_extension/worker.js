import {sendLink, statusText} from "./bridge.js";

const LINK_MENU = "download-link";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: LINK_MENU,
    title: "Bu bağlantıyı Hızlı İndir’e gönder",
    contexts: ["link"],
    targetUrlPatterns: ["http://*/*", "https://*/*"],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== LINK_MENU || tab?.id == null) return;
  void dispatch(info.linkUrl, tab.id);
});

async function dispatch(url, tabId) {
  try {
    await chrome.action.setBadgeText({tabId, text: "…"});
  } catch {
    return;
  }
  const result = await sendLink(url);
  try {
    await chrome.action.setBadgeBackgroundColor({tabId, color: result === "accepted" ? "#22694f" : "#812543"});
    await chrome.action.setBadgeText({tabId, text: result === "accepted" ? "✓" : "!"});
    await chrome.action.setTitle({tabId, title: statusText[result]});
  } catch {
    // The original tab may have closed before the desktop replied.
  }
}
