import { api } from "@/lib/apiClient";

const SIGNAL_LABEL: Record<string, string> = {
  swing_high: "Swing high",
  swing_low: "Swing low",
  fair_value_gap: "Fair value gap",
  liquidity_sweep: "Liquidity sweep",
  market_structure_shift: "Market structure shift",
  order_block: "Order block",
};

export default async function IctPage() {
  const [gold, nasdaq] = await Promise.all([
    api.ict.signals("XAUUSD", 15),
    api.ict.signals("NQ", 15),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">ICT analysis</h1>
        <p className="mt-1 text-sm text-muted">
          Daily order blocks, fair value gaps, liquidity sweeps, and structure shifts. NQ is
          proxied with QQQ — free tiers don't carry the futures contract itself.
        </p>
      </div>

      <SignalPanel title="Gold (XAU/USD)" signals={gold} />
      <SignalPanel title="Nasdaq (proxied via QQQ)" signals={nasdaq} />
    </div>
  );
}

function SignalPanel({ title, signals }: { title: string; signals: Awaited<ReturnType<typeof api.ict.signals>> }) {
  return (
    <section className="rounded border border-border bg-panel p-5">
      <h2 className="font-display text-lg font-medium text-ink">{title}</h2>
      {!signals || signals.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          No signals yet — run <code className="font-mono text-ink">POST /api/ict/refresh</code>.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {signals.map((s) => (
            <li key={s.id} className="flex items-center justify-between text-sm">
              <span className="text-ink">{SIGNAL_LABEL[s.signal_type] ?? s.signal_type}</span>
              <span className={s.direction === "bullish" ? "text-positive" : "text-negative"}>
                {s.direction}
              </span>
              <span className="font-mono text-xs text-muted tabular">
                {s.price_level?.toFixed(2) ?? "—"}
              </span>
              <span className="text-xs text-muted">{s.detected_at?.slice(0, 10)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
