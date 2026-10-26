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
  const cookieName = sessionId ? `banking_session_${sessionId}` : "banking_session";
  const token = request.cookies.get(cookieName)?.value;
  if (token) {
    try {
      const upstream = await fetch(`${API_URL}/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!upstream.ok && upstream.status !== 401) {
        return NextResponse.json({ detail: "Could not sign out. Please try again." }, { status: 503 });
      }
    } catch {
      return NextResponse.json({ detail: "Banking API is unavailable. Please try again." }, { status: 503 });
    }
  }
  const response = NextResponse.json({ status: "signed out" });
  response.cookies.set(cookieName, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/api/banking",
    maxAge: 0,
  });
  return response;
}
