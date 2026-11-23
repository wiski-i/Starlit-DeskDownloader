import {canSend, getProfiles, sendLink, statusText} from "./bridge.js";

const button = document.querySelector("#send");
const page = document.querySelector("#page");
const status = document.querySelector("#status");
const setup = document.querySelector("#setup");
const panel = document.querySelector("#profiles");
const format = document.querySelector("#format");
const quality = document.querySelector("#quality");
const unsupportedTab = "Bu sekme gönderilemiyor. Bir web sitesi açıp eklentiyi tekrar aç.";
const groupNames = {video: "Video", audio: "Ses", legacy: "Eski cihazlar"};

function showProfiles(catalog) {
  const formats = new Map(catalog.formats.map(item => [item.key, item]));
  if (!formats.has(catalog.selected.format)) return false;
  const groups = new Map();
  const picked = new Map([[catalog.selected.format, catalog.selected.quality]]);
  for (const item of formats.values()) {
    if (Object.hasOwn(groupNames, item.group) && !groups.has(item.group)) {
      const group = document.createElement("optgroup");
      group.label = groupNames[item.group];
      format.append(group);
      groups.set(item.group, group);
    }
    const container = groups.get(item.group) ?? format;
    container.append(new Option(item.label, item.key));
  }
  function updateQuality() {
    const item = formats.get(format.value);
    quality.replaceChildren(...item.qualities.map(option => new Option(option.label, option.key)));
    quality.value = picked.get(item.key) ?? item.quality;
  }
  format.value = catalog.selected.format;
  updateQuality();
  format.addEventListener("change", updateQuality);
  quality.addEventListener("change", () => picked.set(format.value, quality.value));
  panel.hidden = false;
  return true;
}

function showStatus(result) {
  status.textContent = statusText[result] ?? "";
  status.dataset.state = result;
  setup.hidden = result !== "desktop_unavailable" && result !== "upgrade_required";
}

async function init() {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  if (!canSend(tab?.url)) {
    status.textContent = unsupportedTab;
    return;
  }

  page.textContent = tab.url;
  page.title = tab.url;
  page.hidden = false;
  status.textContent = "İndirme seçenekleri yükleniyor…";
  const catalog = await getProfiles();
  if (catalog.status === "profiles" && showProfiles(catalog)) {
    showStatus("");
  } else {
    showStatus(catalog.status === "profiles" ? "desktop_unavailable" : catalog.status);
    button.textContent = "Masaüstü ayarıyla gönder";
  }
  button.disabled = false;
  button.addEventListener("click", async () => {
    button.disabled = true;
    panel.disabled = true;
    setup.hidden = true;
    status.textContent = "Hızlı İndir’e bağlanılıyor…";
    const profile = panel.hidden ? undefined : {format: format.value, quality: quality.value};
    const result = await sendLink(tab.url, profile);
    showStatus(result);
    button.disabled = result === "accepted";
    panel.disabled = result === "accepted";
  });
}

init().catch(() => {
  showStatus("desktop_unavailable");
});
