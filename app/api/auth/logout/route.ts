import { NextRequest, NextResponse } from "next/server";

const SESSION_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export async function POST(request: NextRequest) {
  if (request.headers.get("origin") !== request.nextUrl.origin) {
    return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
  }
  const sessionId = request.headers.get("x-banking-session");
  if (sessionId && !SESSION_ID.test(sessionId)) {
    return NextResponse.json({ detail: "Invalid staff session selector." }, { status: 400 });
  }
  const response = NextResponse.json({ status: "signed out" });
  response.cookies.set(sessionId ? `banking_session_${sessionId}` : "banking_session", "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/api/banking",
    maxAge: 0,
  });
  return response;
}
