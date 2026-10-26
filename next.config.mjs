import os from "node:os";

const privateIpv4Hosts = Object.values(os.networkInterfaces())
  .flatMap((interfaces) => interfaces ?? [])
  .filter((entry) => {
    if ((entry.family !== "IPv4" && entry.family !== 4) || entry.internal) return false;
    const [first, second] = entry.address.split(".").map(Number);
    return (
      first === 10 ||
      (first === 172 && second >= 16 && second <= 31) ||
      (first === 192 && second === 168)
    );
  })
  .map((entry) => entry.address);

const nextConfig = {
  poweredByHeader: false,
  allowedDevOrigins: ["127.0.0.1", ...privateIpv4Hosts],
  async redirects() {
    return [{ source: "/admin", destination: "/", permanent: false }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig
