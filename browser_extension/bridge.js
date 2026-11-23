const HOST = "com.starlit.deskdownloader";

export const statusText = Object.freeze({
  accepted: "Hızlı İndir’e gönderildi. İlerlemeyi uygulamada görebilirsin.",
  busy: "Bir indirme devam ediyor. Tamamlanınca tekrar dene.",
  invalid_url: "Bu sekme veya bağlantı gönderilemiyor. Bir HTTP veya HTTPS adresi aç.",
  invalid_profile: "Bu biçim ve kalite birlikte kullanılamıyor. Eklentiyi tekrar açıp seçimini kontrol et.",
  upgrade_required: "Chrome’dan biçim ve kalite seçmek için Hızlı İndir’i güncelle.",
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

export async function getProfiles() {
  try {
    const reply = await chrome.runtime.sendNativeMessage(HOST, {action: "get_profiles"});
    if (reply?.status === "profiles" && reply.selected && Array.isArray(reply.formats)) return reply;
    if (reply?.status === "invalid_url") return {status: "upgrade_required"};
  } catch {
    // The Windows app may be missing or its local connection unavailable.
  }
  return {status: "desktop_unavailable"};
}

export async function sendLink(url, profile) {
  if (!canSend(url)) return "invalid_url";
  try {
    const request = {action: "download", url};
    if (profile) request.profile = profile;
    const reply = await chrome.runtime.sendNativeMessage(HOST, request);
    if (Object.hasOwn(statusText, reply?.status)) return reply.status;
  } catch {
    // The local app might not be installed, registered or reachable.
  }
  return "desktop_unavailable";
}
