const HOST = "com.starlit.deskdownloader";

export const statusText = Object.freeze({
  accepted: "Hızlı İndir’e gönderildi. İlerlemeyi uygulamada görebilirsin.",
  busy: "Bir indirme devam ediyor. Tamamlanınca tekrar dene.",
  invalid_url: "Bu sekme veya bağlantı gönderilemiyor. Bir HTTP veya HTTPS adresi aç.",
  desktop_unavailable: "Hızlı İndir’e bağlanılamadı. Windows kurulumunu kontrol et.",
});

export function canSend(url) {
  if (typeof url !== "string" || new TextEncoder().encode(url).byteLength > 8192) return false;
  try {
    const parsed = new URL(url);
    return /^https?:\/\//i.test(url) && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

export async function sendLink(url) {
  if (!canSend(url)) return "invalid_url";
  try {
    const reply = await chrome.runtime.sendNativeMessage(HOST, {action: "download", url});
    if (Object.hasOwn(statusText, reply?.status)) return reply.status;
  } catch {
    // The local app might not be installed, registered or reachable.
  }
  return "desktop_unavailable";
}
