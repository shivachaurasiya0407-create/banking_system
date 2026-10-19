import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  if (request.headers.get("origin") !== request.nextUrl.origin) {
    return NextResponse.json({ detail: "Invalid request origin." }, { status: 403 });
  }
  const response = NextResponse.json({ status: "signed out" });
  response.cookies.set("banking_session", "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/api/banking",
    maxAge: 0,
  });
  return response;
}
