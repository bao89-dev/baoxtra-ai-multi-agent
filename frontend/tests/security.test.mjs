import { test } from "node:test";
import assert from "node:assert/strict";
import { allowedPath, backendURL, configReady, newSession, safeEqual, sameOrigin, verifySession } from "../lib/security.mjs";

const id = "12345678-1234-4234-a234-1234567890ab";
const secret = "x".repeat(48);

test("session expiry enforced", () => {
  const start = 1_700_000_000_000;
  const token = newSession(secret, start);
  assert.equal(verifySession(token, secret, start + 1000), true);
  assert.equal(verifySession(token, secret, start + 9 * 60 * 60 * 1000), false);
});

test("session tampering rejected", () => {
  const token = newSession(secret);
  assert.equal(verifySession(token.slice(0, -1) + (token.at(-1) === "0" ? "1" : "0"), secret), false);
  assert.equal(verifySession(token, "y".repeat(48)), false);
  assert.equal(verifySession("not-a-session", secret), false);
});

test("compare passwords safely", () => {
  assert.equal(safeEqual("abc", "abc"), true);
  assert.equal(safeEqual("abc", "ab"), false);
  assert.equal(safeEqual(null, "abc"), false);
});

test("required configuration fail-closed", () => {
  assert.equal(configReady({}), false);
  assert.equal(configReady({ CONTROL_CENTER_PASSWORD: "x".repeat(16),
    CONTROL_SESSION_SECRET: secret, AGENCY_API_TOKEN: "y".repeat(24), AGENCY_API_URL: "http://localhost:8000" }), true);
});

test("route allowlist rejects arbitrary operations", () => {
  assert.equal(allowedPath("POST", ["conversations"]), "/conversations");
  assert.equal(allowedPath("GET", ["conversations", id, "events"]), "/conversations/" + id + "/events");
  assert.equal(allowedPath("POST", ["conversations", id, "attachments"]), "/conversations/" + id + "/attachments");
  assert.equal(allowedPath("GET", ["summary"]), "/summary");
  for (const parts of [
    ["tasks",id], ["conversations","../../admin","messages"],
    ["conversations",id,"approve"], ["trading","orders"], ["admin"],
    ["conversations",id,"messages","danger"]
  ]) assert.equal(allowedPath("POST", parts), null);
  assert.equal(allowedPath("PATCH", ["tasks"]), null);
});

test("allowed read and write methods remain distinct", () => {
  assert.equal(allowedPath("GET", ["conversations",id,"attachments"]), "/conversations/" + id + "/attachments");
  assert.equal(allowedPath("DELETE", ["conversations",id,"attachments"]), null);
  assert.equal(allowedPath("POST", ["summary"]), null);
});

test("backend HTTPS enforcement rejects external HTTP", () => {
  assert.throws(() => backendURL("/summary", new URLSearchParams(), { AGENCY_API_URL: "http://example.com" }));
  assert.equal(backendURL("/summary", new URLSearchParams(), { AGENCY_API_URL: "http://127.0.0.1:8000" }).href,
    "http://127.0.0.1:8000/api/v1/summary");
});

test("backend query filters only numeric event cursors", () => {
  const url = backendURL("/conversations/" + id + "/events",
    new URLSearchParams("after=2&token=secret"), { AGENCY_API_URL: "https://api.example.com" });
  assert.equal(url.search, "?after=2");
  assert.equal(url.pathname, "/api/v1/conversations/" + id + "/events");
  const bad = backendURL("/conversations/" + id + "/events",
    new URLSearchParams("after=abc"), { AGENCY_API_URL: "https://api.example.com" });
  assert.equal(bad.search, "");
});

test("cross-site mutation origin rejected", () => {
  const mock = (origin) => ({ url: "https://agency.example.com/api/session",
    headers: { get: (name) => name === "origin" ? origin : null } });
  assert.equal(sameOrigin(mock("https://agency.example.com")), true);
  assert.equal(sameOrigin(mock("https://evil.example.com")), false);
  assert.equal(sameOrigin(mock(null)), false);
});


test("analysis routes are read/submit only and cannot escalate", () => {
  assert.equal(allowedPath("GET", ["conversations",id,"analysis-jobs"]),
    "/conversations/"+id+"/analysis-jobs");
  assert.equal(allowedPath("POST", ["conversations",id,"analysis-jobs"]),
    "/conversations/"+id+"/analysis-jobs");
  assert.equal(allowedPath("GET", ["analysis-jobs",id]), "/analysis-jobs/"+id);
  assert.equal(allowedPath("POST", ["analysis-jobs",id]), null);
  assert.equal(allowedPath("PATCH", ["analysis-jobs",id]), null);
  assert.equal(allowedPath("DELETE", ["analysis-jobs",id]), null);
  assert.equal(allowedPath("POST", ["analysis-jobs",id,"run"]), null);
  assert.equal(allowedPath("POST", ["conversations",id,"approve"]), null);
});


test("proposal review routes are tightly allowlisted", () => {
  assert.equal(allowedPath("POST", ["proposals"]), "/proposals");
  assert.equal(allowedPath("GET", ["conversations",id,"proposals"]),
    "/conversations/"+id+"/proposals");
  assert.equal(allowedPath("GET", ["proposals",id]), "/proposals/"+id);
  assert.equal(allowedPath("POST", ["proposals",id,"revisions"]),
    "/proposals/"+id+"/revisions");
  assert.equal(allowedPath("POST", ["proposals",id,"decision"]),
    "/proposals/"+id+"/decision");
  for(const [method,parts] of [
    ["POST",["proposals",id,"execute"]],
    ["PATCH",["proposals",id]],
    ["DELETE",["proposals",id]],
    ["GET",["proposals",id,"decision"]],
    ["POST",["proposals","../../main","decision"]],
    ["POST",["trading","live"]]
  ]) assert.equal(allowedPath(method,parts),null);
});
