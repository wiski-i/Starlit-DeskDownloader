import {canSend, sendLink, statusText} from "./bridge.js";

const button = document.querySelector("#send");
const page = document.querySelector("#page");
const status = document.querySelector("#status");
const setup = document.querySelector("#setup");
const unsupportedTab = "Bu sekme gönderilemiyor. Bir web sitesi açıp eklentiyi tekrar aç.";

async function init() {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  if (!canSend(tab?.url)) {
    status.textContent = unsupportedTab;
    return;
  }

  page.textContent = new URL(tab.url).hostname;
  page.title = page.textContent;
  page.hidden = false;
  status.textContent = "";
  button.disabled = false;
  button.addEventListener("click", async () => {
    button.disabled = true;
    setup.hidden = true;
    status.textContent = "Hızlı İndir’e bağlanılıyor…";
    const result = await sendLink(tab.url);
    status.textContent = statusText[result];
    setup.hidden = result !== "desktop_unavailable";
    button.disabled = result === "accepted";
  });
}

init().catch(() => {
  status.textContent = unsupportedTab;
});
