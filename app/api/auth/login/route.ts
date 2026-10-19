import { NextRequest, NextResponse } from "next/server";

const API_URL = (process.env.BANKING_API_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");

export async function POST(request: NextRequest) {
  if (request.headers.get("origin") !== request.nextUrl.origin) {
    return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
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
      headers: { "Content-Type": "application/json" },
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
    response.cookies.set("banking_session", payload.access_token, {
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
