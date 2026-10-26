export function hasValidRequestOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host) return false;

  const forwardedProtocol = request.headers
    .get("x-forwarded-proto")
    ?.split(",")[0]
    ?.trim();
  const protocol = forwardedProtocol || new URL(request.url).protocol.slice(0, -1);
  if (protocol !== "http" && protocol !== "https") return false;

  try {
    const expectedOrigin = new URL(`${protocol}://${host}`).origin;
    return new URL(origin).origin === expectedOrigin;
  } catch {
    return false;
  }
}
