import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

export const SESSION_COOKIE = "baoxtra_session";
const TTL_SECONDS = 8 * 60 * 60;
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;

export function configReady(env = process.env) {
  return Boolean(
    env.CONTROL_CENTER_PASSWORD?.length >= 16 &&
    env.CONTROL_SESSION_SECRET?.length >= 32 &&
    env.AGENCY_API_TOKEN?.length >= 24 &&
    env.AGENCY_API_URL
  );
}
export function safeEqual(left, right) {
  if (typeof left !== "string" || typeof right !== "string") return false;
  const a = createHash("sha256").update(left).digest();
  const b = createHash("sha256").update(right).digest();
  return timingSafeEqual(a, b);
}
function sign(body, secret) {
  return createHmac("sha256", secret).update(body).digest("hex");
}
export function newSession(secret, now = Date.now()) {
  const payload = Buffer.from(JSON.stringify({
    exp: Math.floor(now / 1000) + TTL_SECONDS,
    nonce: randomBytes(16).toString("hex"),
  })).toString("base64url");
  return payload + "." + sign(payload, secret);
}
export function verifySession(token, secret, now = Date.now()) {
  if (!token || !secret || !token.includes(".")) return false;
  const [body, signature] = token.split(".");
  if (!body || !/^[a-f0-9]{64}$/.test(signature || "")) return false;
  const expected = sign(body, secret);
  if (!timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) return false;
  try {
    const decoded = JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
    return Number.isInteger(decoded.exp) &&
      decoded.exp > Math.floor(now / 1000) &&
      decoded.exp <= Math.floor(now / 1000) + TTL_SECONDS &&
      /^[a-f0-9]{32}$/.test(decoded.nonce);
  } catch { return false; }
}
export function sameOrigin(req) {
  const origin = req.headers.get("origin");
  if (!origin) return false;
  try { return new URL(origin).origin === new URL(req.url).origin; }
  catch { return false; }
}
export function allowedPath(method, parts) {
  if (!Array.isArray(parts) || parts.length < 1) return null;
  if (parts.length === 1 && parts[0] === "summary" && method === "GET") return "/summary";
  if (parts.length === 1 && parts[0] === "tasks" && method === "GET") return "/tasks";
  if (parts.length === 1 && parts[0] === "conversations" && ["GET","POST"].includes(method)) return "/conversations";
  if (parts.length === 1 && parts[0] === "proposals" && method === "POST") return "/proposals";
  if (parts[0] === "proposals" && UUID.test(parts[1] || "")) {
    if (parts.length === 2 && method === "GET") return "/proposals/" + parts[1];
    if (parts.length === 3 && parts[2] === "revisions" && method === "POST")
      return "/proposals/" + parts[1] + "/revisions";
    if (parts.length === 3 && parts[2] === "decision" && method === "POST")
      return "/proposals/" + parts[1] + "/decision";
    return null;
  }
  if (parts[0] === "analysis-jobs" && parts.length === 2 && UUID.test(parts[1] || "") && method === "GET")
    return "/analysis-jobs/" + parts[1];
  if (parts[0] !== "conversations" || !UUID.test(parts[1] || "")) return null;
  if (parts.length === 3 && parts[2] === "proposals" && method === "GET")
    return "/conversations/" + parts[1] + "/proposals";
  if (parts.length === 3 && ["messages","attachments"].includes(parts[2]) &&
      ["GET","POST"].includes(method)) return "/conversations/" + parts[1] + "/" + parts[2];
  if (parts.length === 3 && parts[2] === "analysis-jobs" &&
      ["GET","POST"].includes(method)) return "/conversations/" + parts[1] + "/analysis-jobs";
  if (parts.length === 3 && parts[2] === "events" && method === "GET") return "/conversations/" + parts[1] + "/events";
  return null;
}
export function backendURL(path, params, env = process.env) {
  const base = new URL(env.AGENCY_API_URL);
  if (!["https:","http:"].includes(base.protocol) ||
      (base.protocol === "http:" && !["127.0.0.1","localhost"].includes(base.hostname)) ||
      base.username || base.password || base.search || base.hash) throw Error("Unsafe backend URL");
  const url = new URL("/api/v1" + path, base.origin);
  if (path.endsWith("/events")) {
    const after = params.get("after");
    if (after && /^\d{1,12}$/.test(after)) url.searchParams.set("after", after);
  }
  return url;
}
