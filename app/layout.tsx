import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Banking Operations",
  description: "Secure staff banking operations dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
