"use client";

import {
  BarChart3,
  Bell,
  BrainCircuit,
  CandlestickChart,
  History,
  Landmark,
  LayoutDashboard,
  Newspaper,
  Percent,
  Settings,
  Banknote,
  Telescope,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/top-down", label: "Top-down analysis", icon: Telescope },
  { href: "/treasury", label: "Treasury", icon: Landmark },
  { href: "/rates", label: "Interest rates", icon: Percent },
  { href: "/news", label: "Economic news", icon: Newspaper },
  { href: "/dxy", label: "DXY forecast", icon: Banknote },
  { href: "/ict", label: "ICT analysis", icon: CandlestickChart },
  { href: "/ai-decision", label: "AI decision", icon: BrainCircuit },
  { href: "/history", label: "Historical learning", icon: History },
  { href: "/performance", label: "Performance", icon: BarChart3 },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <nav className="flex w-60 shrink-0 flex-col border-r border-border bg-panel">
      <div className="flex items-center gap-2 border-b border-border px-5 py-5">
        <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
          <polyline
            points="1,16 6,10 10,13 15,5 21,8"
            fill="none"
            stroke="#C9A227"
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
    </nav>
  );
}
