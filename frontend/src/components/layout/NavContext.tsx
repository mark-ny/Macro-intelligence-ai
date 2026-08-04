"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

interface NavContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
}

const NavContext = createContext<NavContextValue | null>(null);

/**
 * Wraps the whole app shell so the mobile hamburger button (rendered in
 * Topbar, a server component) and the Sidebar drawer (a client component)
 * can share one open/closed state without prop-drilling through
 * layout.tsx. Only the toggle button and the drawer itself care about
 * this — everything else in the tree is untouched.
 */
export function NavProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);

  return (
    <NavContext.Provider value={{ open, setOpen, toggle: () => setOpen((v) => !v) }}>
      {children}
    </NavContext.Provider>
  );
}

export function useNav() {
  const ctx = useContext(NavContext);
  if (!ctx) {
    throw new Error("useNav must be used within a NavProvider");
  }
  return ctx;
}
