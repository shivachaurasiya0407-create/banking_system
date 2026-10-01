import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = { title: "northstar | Personal banking", description: "A clear view of your money, accounts, and everyday banking." }
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html> }
