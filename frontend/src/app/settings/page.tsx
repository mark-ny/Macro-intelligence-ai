"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { createClient } from "@/lib/supabase/client";
import { applyTheme, getStoredTheme, type Theme } from "@/lib/theme";

interface NotificationPrefs {
  curve_inversion?: boolean;
  ai_decision_changes?: boolean;
  calendar_events?: boolean;
}

interface UserSettings {
  risk_tolerance: string;
  watchlist: string[];
  theme: Theme;
  notification_prefs: NotificationPrefs;
}

const DEFAULT_SETTINGS: UserSettings = {
  risk_tolerance: "moderate",
  watchlist: ["XAUUSD", "NQ"],
  theme: "dark",
  notification_prefs: {},
};

/**
 * Direct Supabase CRUD, same reasoning as the Notifications page: RLS
 * already scopes user_settings to auth.uid() (see migration 0001), so
 * there's no correctness or security benefit to routing this through the
 * backend's service-role client — only extra latency and a JWT-passthrough
 * to build for no gain.
 *
 * Theme is the one field here that also applies without an account —
 * see src/lib/theme.ts. Logged-out visitors can still switch it; logging
 * in additionally syncs whatever they'd previously saved to their account.
 */
export default function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();

    supabase.auth.getUser().then(async ({ data, error: userError }) => {
      if (userError || !data.user) {
        // Not logged in — theme still works from localStorage, everything
        // else needs an account.
        setNeedsLogin(true);
        setSettings({ ...DEFAULT_SETTINGS, theme: getStoredTheme() });
        return;
      }
      setUserId(data.user.id);

      const { data: row } = await supabase
        .from("user_settings")
        .select("risk_tolerance, watchlist, theme, notification_prefs")
        .eq("user_id", data.user.id)
        .maybeSingle();

      const loaded: UserSettings = row
        ? { ...DEFAULT_SETTINGS, ...row, notification_prefs: row.notification_prefs ?? {} }
        : { ...DEFAULT_SETTINGS, theme: getStoredTheme() };

      setSettings(loaded);
      applyTheme(loaded.theme); // sync this device to the account's saved choice
    });
  }, []);

  function setTheme(theme: Theme) {
    if (!settings) return;
    setSettings({ ...settings, theme });
    applyTheme(theme); // live preview, and works even when logged out
  }

  function setNotificationPref(key: keyof NotificationPrefs, value: boolean) {
    if (!settings) return;
    setSettings({
      ...settings,
      notification_prefs: { ...settings.notification_prefs, [key]: value },
    });
  }

  async function save() {
    if (!settings) return;
    if (!userId) {
      // Logged out: theme is already applied/persisted to localStorage by
      // setTheme() above, and the rest of the form isn't shown, so there's
      // nothing account-side to save.
      return;
    }
    setSaving(true);
    const supabase = createClient();
    await supabase.from("user_settings").upsert({ user_id: userId, ...settings });
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">Settings</h1>
        <p className="mt-1 text-sm text-muted">Theme, risk tolerance, watchlist, and notifications.</p>
      </div>

      <section className="max-w-md space-y-4 rounded border border-border bg-panel p-5">
        {error && <p className="text-sm text-negative">{error}</p>}
        {!error && !settings && <p className="text-sm text-muted">Loading…</p>}

        {!error && settings && (
          <>
            <label className="block">
              <span className="text-sm text-muted">Theme</span>
              <select
                value={settings.theme}
                onChange={(e) => setTheme(e.target.value as Theme)}
                className="mt-1 w-full rounded border border-border bg-bg px-3 py-2 text-sm text-ink"
              >
                <option value="dark">Dark</option>
                <option value="light">Light</option>
              </select>
            </label>

            {needsLogin && (
              <p className="text-sm text-muted">
                Theme applies right away and is remembered on this device.{" "}
                <Link href="/login" className="text-gold hover:underline">
                  Log in
                </Link>{" "}
                to also set risk tolerance, watchlist, and notification preferences.
              </p>
            )}

            {!needsLogin && (
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

                <fieldset className="space-y-2">
                  <legend className="text-sm text-muted">Notify me about</legend>
                  <label className="flex items-center gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      checked={settings.notification_prefs.curve_inversion !== false}
                      onChange={(e) => setNotificationPref("curve_inversion", e.target.checked)}
                      className="accent-gold"
                    />
                    Yield curve inversions
                  </label>
                  <label className="flex items-center gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      checked={settings.notification_prefs.ai_decision_changes !== false}
                      onChange={(e) => setNotificationPref("ai_decision_changes", e.target.checked)}
                      className="accent-gold"
                    />
                    AI decision changes
                  </label>
                  <label className="flex items-center gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      checked={settings.notification_prefs.calendar_events !== false}
                      onChange={(e) => setNotificationPref("calendar_events", e.target.checked)}
                      className="accent-gold"
                    />
                    Upcoming high-impact releases
                  </label>
                </fieldset>
              </>
            )}

            <div className="flex items-center gap-3">
              <button
                onClick={save}
                disabled={saving || needsLogin}
                className="rounded bg-gold px-4 py-2 text-sm font-medium text-bg transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save settings"}
              </button>
              {saved && <span className="text-sm text-positive">Saved</span>}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
