import { api } from "@/lib/apiClient";
import type { IctSignal } from "@/types";

const SIGNAL_LABEL: Record<string, string> = {
  swing_high: "Swing high",
  swing_low: "Swing low",
  fair_value_gap: "Fair value gap",
  liquidity_sweep: "Liquidity sweep",
  market_structure_shift: "Market structure shift",
  order_block: "Order block",
};

const BIAS_COLOR: Record<string, string> = {
  BUY: "text-positive",
  SELL: "text-negative",
  WAIT: "text-muted",
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
          Daily order blocks, fair value gaps, liquidity sweeps, and structure shifts, plus
          institutional bias and OTE zones. NQ is proxied with QQQ — free tiers don&apos;t carry
          the futures contract itself.
        </p>
      </div>

      <SignalPanel title="Gold (XAU/USD)" signals={gold} />
      <SignalPanel title="Nasdaq (proxied via QQQ)" signals={nasdaq} />
    </div>
  );
}

function SignalPanel({ title, signals }: { title: string; signals: IctSignal[] | null }) {
  const latest = signals && signals.length > 0 ? signals[0] : null;

  return (
    <section className="rounded border border-border bg-panel p-5">
      <h2 className="font-display text-lg font-medium text-ink">{title}</h2>

      {!signals || signals.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          No signals yet — run <code className="font-mono text-ink">POST /api/ict/refresh</code>.
        </p>
      ) : (
        <>
          {latest && <BiasSummary signal={latest} />}

          <ul className="mt-4 space-y-2">
            {signals.map((s) => (
              <li
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-border/60 pb-2 text-sm last:border-0 last:pb-0"
              >
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
        </>
      )}
    </section>
  );
}

function BiasSummary({ signal }: { signal: IctSignal }) {
  const hasOte =
    signal.buy_ote_low !== null &&
    signal.buy_ote_high !== null &&
    signal.sell_ote_low !== null &&
    signal.sell_ote_high !== null;

  return (
    <div className="mt-3 grid grid-cols-2 gap-3 rounded border border-border bg-bg/40 p-4 sm:grid-cols-4">
      <Stat label="Institutional bias">
        <span className={BIAS_COLOR[signal.institutional_bias ?? ""] ?? "text-muted"}>
          {signal.institutional_bias ?? "—"}
        </span>
        {signal.confidence !== null && (
          <span className="ml-1 text-xs text-muted">({signal.confidence}%)</span>
        )}
      </Stat>
      <Stat label="Trend">
        {signal.market_trend ?? "—"}
        {signal.trend_strength !== null && (
          <span className="ml-1 text-xs text-muted">({signal.trend_strength})</span>
        )}
      </Stat>
      <Stat label="Price location">{signal.premium_discount ?? "—"}</Stat>
      <Stat label="OTE (buy / sell)">
        {hasOte ? (
          <span className="font-mono text-xs tabular">
            {signal.buy_ote_low?.toFixed(2)}–{signal.buy_ote_high?.toFixed(2)} /{" "}
            {signal.sell_ote_low?.toFixed(2)}–{signal.sell_ote_high?.toFixed(2)}
          </span>
        ) : (
          "—"
        )}
      </Stat>
    </div>
  );
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-0.5 truncate text-sm text-ink">{children}</div>
    </div>
  );
}
