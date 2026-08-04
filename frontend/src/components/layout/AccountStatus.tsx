"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LogIn, LogOut } from "lucide-react";
import type { User } from "@supabase/supabase-js";

import { createClient } from "@/lib/supabase/client";

export function AccountStatus() {
  const [user, setUser] = useState<User | null | undefined>(undefined); // undefined = still loading
  const supabase = createClient();

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setUser(data.user));

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });
    return () => subscription.subscription.unsubscribe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleLogout() {
    await supabase.auth.signOut();
    window.location.href = "/";
  }

  if (user === undefined) {
    return <div className="border-t border-border px-3 py-3 text-xs text-muted">…</div>;
  }

  if (!user) {
    return (
      <div className="border-t border-border px-3 py-3">
        <Link
          href="/login"
          className="flex items-center gap-3 rounded px-3 py-2 text-sm text-muted transition-colors hover:bg-white/5 hover:text-ink"
        >
          <LogIn size={16} aria-hidden="true" />
          Log in
        </Link>
      </div>
    );
  }

  return (
    <div className="border-t border-border px-3 py-3">
      <div className="flex items-center justify-between gap-2 px-3">
        <span className="min-w-0 truncate text-xs text-muted" title={user.email ?? undefined}>
          {user.email}
        </span>
        <button
          type="button"
          onClick={handleLogout}
          aria-label="Log out"
          className="shrink-0 text-muted transition-colors hover:text-ink"
        >
          <LogOut size={16} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
