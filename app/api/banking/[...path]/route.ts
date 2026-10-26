import { NextRequest, NextResponse } from "next/server";
import { hasValidRequestOrigin } from "../../request-origin";

const API_URL = (process.env.BANKING_API_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const UUID = "[0-9a-fA-F-]{36}";
const ACCOUNT = "[0-9]{10}";
const SESSION_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isAllowed(path: string, method: string) {
  if (method === "GET") {
    return (
      path === "auth/me" ||
      path === "dashboard/summary" ||
      path === "branches" ||
      path === "metadata/india-states" ||
      path === "accounts" ||
      new RegExp(`^accounts/${ACCOUNT}(?:$|/balance|/transactions|/statement|/statement\\.csv)$`).test(path) ||
      path === "admin/reconciliation" ||
      path === "admin/audit-logs" ||
      path === "admin/notifications" ||
      path === "staff/audit-logs" ||
      path === "staff" ||
      path === "loans" ||
      path === "fixed-deposits" ||
      new RegExp(`^loans/${UUID}$`).test(path)
    );
  }
  if (method === "POST") {
    return (
      path === "accounts" ||
      path === "branches" ||
      path === "transfers" ||
      path === "loans" ||
      path === "fixed-deposits" ||
      path === "auth/logout" ||
      path === "auth/change-password" ||
      path === "staff" ||
      new RegExp(`^accounts/${ACCOUNT}/(?:deposits|withdrawals|status)$`).test(path) ||
      new RegExp(`^accounts/${ACCOUNT}/interest$`).test(path) ||
      new RegExp(`^transactions/${UUID}/reversals$`).test(path) ||
      new RegExp(`^staff/${UUID}/password-reset$`).test(path) ||
      new RegExp(`^loans/${UUID}/(?:action|repayments)$`).test(path) ||
      new RegExp(`^fixed-deposits/${UUID}/close$`).test(path) ||
      new RegExp(`^staff/${UUID}/session-revoke$`).test(path)
    );
  }
  return (
    method === "PATCH" &&
    (new RegExp(`^staff/${UUID}$`).test(path) ||
      new RegExp(`^customers/${UUID}/(?:kyc|profile)$`).test(path))
  );
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const method = request.method;
  if (method !== "GET" && !hasValidRequestOrigin(request)) {
    return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
  }

  const { path: segments } = await context.params;
  if (!segments.every((segment) => /^[A-Za-z0-9._-]+$/.test(segment))) {
    return NextResponse.json({ detail: "Not found." }, { status: 404 });
  }
  const path = segments.join("/");
  if (!isAllowed(path, method)) {
    return NextResponse.json({ detail: "Not found." }, { status: 404 });
  }

  const sessionId = request.headers.get("x-banking-session");
  if (sessionId && !SESSION_ID.test(sessionId)) {
    return NextResponse.json({ detail: "Invalid staff session selector." }, { status: 400 });
  }
  const cookieName = sessionId ? `banking_session_${sessionId}` : "banking_session";
  const token = request.cookies.get(cookieName)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Authentication required." }, { status: 401 });
  }

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const contentType = request.headers.get("content-type");
  const idempotencyKey = request.headers.get("idempotency-key");
  if (contentType) headers["Content-Type"] = contentType;
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

  try {
    const upstream = await fetch(
      `${API_URL}/${segments.map(encodeURIComponent).join("/")}${request.nextUrl.search}`,
      {
        method,
        headers,
        body: method === "GET" ? undefined : await request.arrayBuffer(),
        cache: "no-store",
      },
    );
    const responseHeaders = new Headers({ "Cache-Control": "no-store" });
    for (const name of ["content-type", "content-disposition", "x-request-id"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    const response = new NextResponse(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
    if (upstream.status === 401) {
      response.cookies.set(cookieName, "", {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "strict",
        path: "/api/banking",
        maxAge: 0,
      });
    }
    return response;
  } catch {
    return NextResponse.json({ detail: "Banking API is unavailable." }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
