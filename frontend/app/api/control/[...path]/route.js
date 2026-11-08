import { NextResponse } from "next/server";
import { allowedPath, backendURL, configReady, sameOrigin, SESSION_COOKIE, verifySession } from "../../../../lib/security.mjs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(req, { params }) {
  const { path: segments } = await params;
  const path = allowedPath(req.method, segments);
  if (!path) return NextResponse.json({ error: "Route not allowed" }, { status: 404 });
  if (!configReady()) return NextResponse.json({ error: "Server not configured" }, { status: 503 });
  if (!verifySession(req.cookies.get(SESSION_COOKIE)?.value, process.env.CONTROL_SESSION_SECRET))
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (req.method !== "GET" && !sameOrigin(req))
    return NextResponse.json({ error: "Origin rejected" }, { status: 403 });
  let target;
  try { target = backendURL(path, new URL(req.url).searchParams); }
  catch { return NextResponse.json({ error: "Backend config invalid" }, { status: 503 }); }
  const headers = { Authorization: "Bearer " + process.env.AGENCY_API_TOKEN };
  const init = { method: req.method, headers, cache: "no-store", signal: req.signal };
  if (req.method === "POST") {
    if (path.endsWith("/attachments")) {
      const form = await req.formData();
      const file = form.get("file");
      if (!file || typeof file.arrayBuffer !== "function" || file.size > 25 * 1024 * 1024)
        return NextResponse.json({ error: "Invalid or oversized file" }, { status: 413 });
      const body = new FormData();
      body.append("file", file);
      init.body = body;
    } else {
      const raw = await req.text();
      if (raw.length > 12000) return NextResponse.json({ error: "Payload too large" }, { status: 413 });
      init.body = raw;
      headers["Content-Type"] = "application/json";
    }
  }
  if (path.endsWith("/events")) {
    headers.Accept = "text/event-stream";
    const last = req.headers.get("last-event-id");
    if (last && /^\d{1,12}$/.test(last)) headers["Last-Event-ID"] = last;
  }
  try {
    const upstream = await fetch(target, init);
    if (path.endsWith("/events") && upstream.ok) {
      return new Response(upstream.body, {
        status: 200, headers: { "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no" }
      });
    }
    const buffer = await upstream.arrayBuffer();
    if (buffer.byteLength > 2 * 1024 * 1024)
      return NextResponse.json({ error: "Upstream response too large" }, { status: 502 });
    return new Response(buffer, {
      status: upstream.status, headers: { "Content-Type": "application/json",
        "Cache-Control": "no-store" }
    });
  } catch {
    return NextResponse.json({ error: "Backend disconnected" }, { status: 502 });
  }
}
export const GET = proxy;
export const POST = proxy;
