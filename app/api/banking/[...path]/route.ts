import { NextRequest, NextResponse } from "next/server";

const API_URL = (process.env.BANKING_API_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const UUID = "[0-9a-fA-F-]{36}";
const ACCOUNT = "[0-9]{10}";

function isAllowed(path: string, method: string) {
  if (method === "GET") {
    return (
      path === "auth/me" ||
      path === "dashboard/summary" ||
      path === "branches" ||
      path === "metadata/india-states" ||
      path === "accounts" ||
      new RegExp(`^accounts/${ACCOUNT}(?:/balance|/transactions|/statement|/statement\\.csv)?$`).test(path) ||
      path === "admin/reconciliation" ||
      path === "admin/audit-logs" ||
      path === "staff"
    );
  }
  if (method === "POST") {
    return (
      path === "accounts" ||
      path === "transfers" ||
      path === "auth/change-password" ||
      new RegExp(`^accounts/${ACCOUNT}/(?:deposits|withdrawals|status)$`).test(path) ||
      new RegExp(`^transactions/${UUID}/reversals$`).test(path) ||
      new RegExp(`^staff/${UUID}/password-reset$`).test(path) ||
      path === "staff"
    );
  }
  return method === "PATCH" && new RegExp(`^staff/${UUID}$`).test(path);
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const method = request.method;
  if (method !== "GET" && request.headers.get("origin") !== request.nextUrl.origin) {
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

  const token = request.cookies.get("banking_session")?.value;
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
      response.cookies.set("banking_session", "", {
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
