import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Inter, Source_Serif_4 } from "next/font/google";

import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { NavProvider } from "@/components/layout/NavContext";

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

// Explicit, rather than relying on the Next.js default, so the app never
// renders desktop-width on a phone browser while this ships.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body className="overflow-x-hidden font-sans antialiased">
        <NavProvider>
          <div className="flex min-h-screen bg-bg text-ink">
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col">
              <Topbar />
              <main className="min-w-0 flex-1 p-4 sm:p-6">{children}</main>
              <footer className="border-t border-border px-4 py-3 text-xs text-muted sm:px-6">
                Macro Intelligence AI — for informational and educational purposes only. Not financial advice.
              </footer>
            </div>
          </div>
        </NavProvider>
      </body>
    </html>
  );
}
