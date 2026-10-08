import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Shiv Bank | Operations Console",
  description: "Secure internal banking operations workspace for branch employees.",
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>
}
