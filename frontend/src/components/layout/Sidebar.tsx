"use client";

import { Menu, X } from "lucide-react";

import { useNav } from "@/components/layout/NavContext";

export function MobileMenuButton() {
  const { open, toggle } = useNav();

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={open ? "Close navigation menu" : "Open navigation menu"}
      aria-expanded={open}
      className="-ml-1 flex h-9 w-9 shrink-0 items-center justify-center rounded text-ink hover:bg-white/5 lg:hidden"
    >
      {open ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
    </button>
  );
}
