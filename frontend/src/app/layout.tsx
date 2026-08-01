import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter, Source_Serif_4 } from "next/font/google";

import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

import "./globals.css";

const display = Source_Serif_4({
  subsets: ["latin"],
  weight: ["500", "600"],
  variable: "--font-display",
});
const sans = Inter({ subsets: ["latin"], variable: "--font-sans" });
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Macro Intelligence AI",
  description: "Institutional-grade macro intelligence for Gold (XAU/USD) and Nasdaq (NQ).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body className="font-sans antialiased">
        <div className="flex min-h-screen bg-bg text-ink">
          <Sidebar />
          <div className="flex flex-1 flex-col">
            <Topbar />
            <main className="flex-1 p-6">{children}</main>
            <footer className="border-t border-border px-6 py-3 text-xs text-muted">
              Macro Intelligence AI — for informational and educational purposes only. Not financial advice.
            </footer>
          </div>
        </div>
      </body>
    </html>
  );
}
