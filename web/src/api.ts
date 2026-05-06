/** 与网关同源，开发时 Vite 代理 /api 到后端 */

const prefix = "/api";

/** 与后端 app/http_user_message.MSG_HTML_GATEWAY 语义一致 */
const GATEWAY_ZH =
  "网关暂时无法连接后端服务，请稍后重试；若反复出现请联系管理员检查 API 与 Nginx 状态。";

function looksLikeHtmlGateway(text: string): boolean {
  const t = text.trim();
  if (t.length < 24) return false;
  if (!/<html\b/i.test(t) && !/<!doctype\s+html/i.test(t)) return false;
  const lower = t.toLowerCase();
  if (t.includes("502") || t.includes("504")) return true;
  if (lower.includes("bad gateway") || lower.includes("gateway timeout") || lower.includes("gateway time-out"))
    return true;
  if (lower.includes("nginx/") && (t.includes("502") || t.includes("504"))) return true;
  return false;
}

/** 对外展示的助手正文：屏蔽误混入的网关 HTML 页 */
export function sanitizeAssistantReply(text: string): string {
  if (looksLikeHtmlGateway(text)) return GATEWAY_ZH;
  return text;
}

function humanizeHttpMessage(detail: string, status: number): string {
  if (status === 502 || status === 503 || status === 504) return GATEWAY_ZH;
  if (looksLikeHtmlGateway(detail)) return GATEWAY_ZH;
  return detail;
}

function errDetail(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d))
      return d.map((x) => (typeof x === "object" ? JSON.stringify(x) : String(x))).join("; ");
  }
  return "请求失败";
}

async function parseJson(res: Response): Promise<unknown> {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text || res.statusText };
  }
}

export async function apiRegister(username: string, password: string) {
  const res = await fetch(`${prefix}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ username, password }),
  });
  const data = await parseJson(res);
  if (!res.ok) throw new Error(humanizeHttpMessage(errDetail(data), res.status));
}

export async function apiLogin(username: string, password: string) {
  const res = await fetch(`${prefix}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ username, password }),
  });
  const data = await parseJson(res);
  if (!res.ok) throw new Error(humanizeHttpMessage(errDetail(data), res.status));
  return data;
}

export async function apiLogout() {
  await fetch(`${prefix}/auth/logout`, { method: "POST", credentials: "include" });
}

export async function apiMe(): Promise<{ user_id: number; username: string } | null> {
  const res = await fetch(`${prefix}/auth/me`, { credentials: "include" });
  if (!res.ok) return null;
  return res.json();
}

export async function apiChat(
  message: string,
  sessionId?: string | null
): Promise<{ reply: string; session_id?: string }> {
  const res = await fetch(`${prefix}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      message,
      ...(sessionId ? { session_id: sessionId } : {}),
    }),
  });
  const data = await parseJson(res);
  if (!res.ok) throw new Error(humanizeHttpMessage(errDetail(data), res.status));
  const out = data as { reply: string; session_id?: string };
  const reply = sanitizeAssistantReply(typeof out.reply === "string" ? out.reply : "");
  return { ...out, reply };
}

/** 仅清空当前会话消息（保留会话条目） */
export async function apiClearChat() {
  await fetch(`${prefix}/chat/clear`, { method: "POST", credentials: "include" });
}

export type ChatMessage = { role: string; content: string };

export type ChatSessionMeta = {
  id: string;
  title?: string;
  preview?: string;
  updated?: number;
};

export async function apiChatSessions(): Promise<{
  sessions: ChatSessionMeta[];
  active_session_id: string;
}> {
  const res = await fetch(`${prefix}/chat/sessions`, { credentials: "include" });
  if (!res.ok) return { sessions: [], active_session_id: "" };
  return res.json();
}

export async function apiNewChatSession(): Promise<{ session_id: string }> {
  const res = await fetch(`${prefix}/chat/session/new`, {
    method: "POST",
    credentials: "include",
  });
  const data = await parseJson(res);
  if (!res.ok) throw new Error(humanizeHttpMessage(errDetail(data), res.status));
  return data as { session_id: string };
}

export async function apiSelectChatSession(sessionId: string): Promise<void> {
  const res = await fetch(`${prefix}/chat/session/select`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ session_id: sessionId }),
  });
  const data = await parseJson(res);
  if (!res.ok) throw new Error(humanizeHttpMessage(errDetail(data), res.status));
}

export async function apiChatHistory(): Promise<{
  messages: ChatMessage[];
  session_id: string;
}> {
  const res = await fetch(`${prefix}/chat/history`, { credentials: "include" });
  if (!res.ok) return { messages: [], session_id: "" };
  return res.json();
}
