"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { createClient } from "@/lib/supabase/client";

interface UserSettings {
  risk_tolerance: string;
  watchlist: string[];
  theme: string;
}

/**
 * Direct Supabase CRUD, same reasoning as the Notifications page: RLS
 * already scopes user_settings to auth.uid() (see migration 0001), so
 * there's no correctness or security benefit to routing this through the
 * backend's service-role client — only extra latency and a JWT-passthrough
 * to build for no gain.
 */
export default function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();

    supabase.auth.getUser().then(async ({ data, error: userError }) => {
      if (userError || !data.user) {
        setNeedsLogin(true);
        return;
      }
      setUserId(data.user.id);

      const { data: row } = await supabase
        .from("user_settings")
        .select("risk_tolerance, watchlist, theme")
        .eq("user_id", data.user.id)
        .maybeSingle();

      setSettings(
        row ?? { risk_tolerance: "moderate", watchlist: ["XAUUSD", "NQ"], theme: "dark" }
      );
    });
  }, []);

  async function save() {
    if (!userId || !settings) return;
    setSaving(true);
    const supabase = createClient();
    await supabase.from("user_settings").upsert({ user_id: userId, ...settings });
    setSaving(false);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">Settings</h1>
        <p className="mt-1 text-sm text-muted">Risk tolerance, watchlist, and theme.</p>
      </div>

      <section className="max-w-md space-y-4 rounded border border-border bg-panel p-5">
        {needsLogin && (
          <p className="text-sm text-muted">
            <Link href="/login" className="text-gold hover:underline">
              Log in
            </Link>{" "}
            to manage your settings.
          </p>
        )}
        {error && <p className="text-sm text-negative">{error}</p>}

        {!needsLogin && !error && !settings && <p className="text-sm text-muted">Loading…</p>}

        {!needsLogin && !error && settings && (
          <>
            <label className="block">
              <span className="text-sm text-muted">Risk tolerance</span>
              <select
                value={settings.risk_tolerance}
                onChange={(e) => setSettings({ ...settings, risk_tolerance: e.target.value })}
                className="mt-1 w-full rounded border border-border bg-bg px-3 py-2 text-sm text-ink"
              >
                <option value="conservative">Conservative</option>
                <option value="moderate">Moderate</option>
                <option value="aggressive">Aggressive</option>
              </select>
            </label>

            <label className="block">
              <span className="text-sm text-muted">Watchlist (comma-separated)</span>
              <input
                type="text"
                value={settings.watchlist.join(", ")}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    watchlist: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                  })
                }
                className="mt-1 w-full rounded border border-border bg-bg px-3 py-2 text-sm text-ink"
              />
            </label>

            <button
              onClick={save}
              disabled={saving}
              className="rounded bg-gold px-4 py-2 text-sm font-medium text-bg transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save settings"}
            </button>
          </>
        )}
      </section>
    </div>
  );
}
