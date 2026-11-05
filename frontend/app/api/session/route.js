import { NextResponse } from "next/server";
import { configReady, newSession, safeEqual, sameOrigin, SESSION_COOKIE, verifySession } from "../../../lib/security.mjs";

export const runtime = "nodejs";

export async function GET(req) {
  const valid = verifySession(req.cookies.get(SESSION_COOKIE)?.value, process.env.CONTROL_SESSION_SECRET);
  return NextResponse.json({ authenticated: valid, configured: configReady() });
}
export async function POST(req) {
  if (!sameOrigin(req)) return NextResponse.json({ error: "Origin rejected" }, { status: 403 });
  if (!configReady()) return NextResponse.json({ error: "Server configuration missing" }, { status: 503 });
  const raw = await req.text();
  if (raw.length > 1024) return NextResponse.json({ error: "Invalid input" }, { status: 413 });
  let password;
  try { password = JSON.parse(raw)?.password; } catch {}
  if (!safeEqual(password, process.env.CONTROL_CENTER_PASSWORD))
    return NextResponse.json({ error: "Invalid credentials" }, { status: 401 });
  const response = NextResponse.json({ authenticated: true });
  response.cookies.set(SESSION_COOKIE, newSession(process.env.CONTROL_SESSION_SECRET), {
    httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production",
    path: "/", maxAge: 8 * 60 * 60
  });
  return response;
}
export async function DELETE(req) {
  if (!sameOrigin(req)) return NextResponse.json({ error: "Origin rejected" }, { status: 403 });
  const response = NextResponse.json({ authenticated: false });
  response.cookies.set(SESSION_COOKIE, "", { httpOnly: true, sameSite: "strict", path: "/", maxAge: 0 });
  return response;
}
