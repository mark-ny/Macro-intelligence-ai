"use client";

import {
  BarChart3,
  Bell,
  Bot,
  BrainCircuit,
  CandlestickChart,
  History,
  Landmark,
  LayoutDashboard,
  Layers,
  Menu,
  Newspaper,
  Percent,
  Settings,
  Banknote,
  Telescope,
  Waves,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useNav } from "@/components/layout/NavContext";
import { AccountStatus } from "@/components/layout/AccountStatus";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/top-down", label: "Top-down analysis", icon: Telescope },
  { href: "/macro-analysis", label: "Macro Analysis", icon: Waves },
  { href: "/ipda", label: "IPDA Data Ranges", icon: Layers },
  { href: "/treasury", label: "Treasury", icon: Landmark },
  { href: "/rates", label: "Interest rates", icon: Percent },
  { href: "/news", label: "Economic news", icon: Newspaper },
  { href: "/dxy", label: "DXY forecast", icon: Banknote },
  { href: "/ict", label: "ICT analysis", icon: CandlestickChart },
  { href: "/ai-decision", label: "AI decision", icon: BrainCircuit },
  { href: "/history", label: "Historical learning", icon: History },
  { href: "/performance", label: "Performance", icon: BarChart3 },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/assistant", label: "AI Assistant", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { open, setOpen } = useNav();

  return (
    <>
      {/* Mobile menu toggle — lives here (not in Topbar) so this button and
          the drawer it controls are compiled as one client component
          instead of two separate files crossing a nested server/client
          boundary. Fixed-positioned to sit visually inside the top bar. */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-label={open ? "Close navigation menu" : "Open navigation menu"}
        aria-expanded={open}
        className="fixed left-4 top-4 z-50 flex h-9 w-9 items-center justify-center rounded text-ink hover:bg-white/5 lg:hidden"
      >
        {open ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
      </button>

      {/* Backdrop — mobile only, closes the drawer on tap outside it */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      <nav
        className={`fixed inset-y-0 left-0 z-40 flex w-60 shrink-0 flex-col border-r border-border bg-panel transition-transform duration-200 ease-out lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center gap-2 border-b border-border px-5 py-5">
          <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
            <polyline
              points="1,16 6,10 10,13 15,5 21,8"
              fill="none"
              stroke="rgb(var(--color-gold))"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="font-display text-[15px] font-medium leading-tight text-ink">
            Macro Intelligence AI
          </span>
        </div>

        <ul className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname?.startsWith(href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  onClick={() => setOpen(false)}
                  className={`flex items-center gap-3 rounded px-3 py-2 text-sm transition-colors ${
                    active
                      ? "bg-gold/10 text-gold"
                      : "text-muted hover:bg-white/5 hover:text-ink"
                  }`}
                >
                  <Icon size={16} aria-hidden="true" />
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>

        <AccountStatus />
      </nav>
    </>
  );
}
