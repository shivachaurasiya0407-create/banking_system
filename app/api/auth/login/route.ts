import { NextRequest, NextResponse } from "next/server";
import { hasValidRequestOrigin } from "../../request-origin";

const API_URL = (process.env.BANKING_API_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const SESSION_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export async function POST(request: NextRequest) {
  if (!hasValidRequestOrigin(request)) {
    return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
  }
  const sessionId = request.headers.get("x-banking-session");
  if (sessionId && !SESSION_ID.test(sessionId)) {
    return NextResponse.json({ detail: "Invalid staff session selector." }, { status: 400 });
  }

  let credentials: unknown;
  try {
    credentials = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON request." }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Banking-Session": sessionId ?? "",
        "User-Agent": request.headers.get("user-agent") ?? "",
      },
      body: JSON.stringify(credentials),
      cache: "no-store",
    });
    const payload = (await upstream.json()) as {
      access_token?: string;
      expires_in?: number;
      role?: string;
      detail?: string;
    };
    if (!upstream.ok) {
      return NextResponse.json(
        { detail: payload.detail ?? "Sign in failed." },
        { status: upstream.status, headers: { "Cache-Control": "no-store" } },
      );
    }
    if (!payload.access_token || !payload.expires_in || !payload.role) {
      return NextResponse.json({ detail: "The authentication service returned an invalid response." }, { status: 502 });
    }

    const response = NextResponse.json(
      { expires_in: payload.expires_in, role: payload.role },
      { headers: { "Cache-Control": "no-store" } },
    );
    response.cookies.set(sessionId ? `banking_session_${sessionId}` : "banking_session", payload.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      path: "/api/banking",
      maxAge: payload.expires_in,
    });
    return response;
  } catch {
    return NextResponse.json({ detail: "Banking API is unavailable." }, { status: 503 });
  }
}
