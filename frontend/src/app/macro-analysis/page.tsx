import { api } from "@/lib/apiClient";
import type { OpenFloatAnalysis, OpenFloatLevel } from "@/types";

const DOMINANCE_LABEL: Record<string, string> = {
  BUY_SIDE: "Buy-side",
  SELL_SIDE: "Sell-side",
  BALANCED: "Balanced",
};

const DOMINANCE_COLOR: Record<string, string> = {
  BUY_SIDE: "text-positive",
  SELL_SIDE: "text-negative",
  BALANCED: "text-muted",
};

const DIRECTION_COLOR: Record<string, string> = {
  bullish: "text-positive",
  bearish: "text-negative",
  neutral: "text-muted",
};

export default async function MacroAnalysisPage() {
  const [gold, nasdaq] = await Promise.all([
    api.macroAnalysis.openFloat("XAUUSD"),
    api.macroAnalysis.openFloat("NQ"),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-wide text-muted">Macro Analysis</p>
        <h1 className="font-display text-2xl font-medium text-ink">Quarterly Shift &amp; Open Float</h1>
        <p className="mt-1 text-sm text-muted">
          Open Float is the study of how the market reaches for buy-side or sell-side liquidity. Below:
          the current quarterly structural bias, and where protective buy stops and sell stops currently
          sit relative to price — never guaranteed orders, just levels where liquidity is likely to rest.
        </p>
      </div>

      <AssetPanel title="Gold (XAU/USD)" data={gold} />
      <AssetPanel title="Nasdaq (proxied via QQQ)" data={nasdaq} />
    </div>
  );
}

function AssetPanel({ title, data }: { title: string; data: OpenFloatAnalysis | null }) {
  if (!data || data.error) {
    return (
      <section className="rounded border border-border bg-panel p-5">
        <h2 className="font-display text-lg font-medium text-ink">{title}</h2>
        <p className="mt-3 text-sm text-muted">{data?.error ?? "Data unavailable."}</p>
      </section>
    );
  }

  return (
    <section className="space-y-4 rounded border border-border bg-panel p-5">
      <h2 className="font-display text-lg font-medium text-ink">{title}</h2>

      {/* Current State */}
      <div className="grid grid-cols-2 gap-3 rounded border border-border bg-bg/40 p-4 sm:grid-cols-4">
        <Stat label="Current price">
          <span className="font-mono tabular">{data.current_price}</span>
        </Stat>
        <Stat label="Quarterly shift">
          <span className={DIRECTION_COLOR[data.quarterly_shift.direction] ?? "text-muted"}>
            {data.quarterly_shift.direction}
          </span>
          <span className="ml-1 text-xs text-muted">({data.quarterly_shift.price_position})</span>
        </Stat>
        <Stat label="Dominant open float">
          <span className={DOMINANCE_COLOR[data.dominant_liquidity_side] ?? "text-muted"}>
            {DOMINANCE_LABEL[data.dominant_liquidity_side] ?? data.dominant_liquidity_side}
          </span>
        </Stat>
        <Stat label="Nearest liquidity">
          {data.nearest_buy_side && data.nearest_sell_side
            ? Math.abs(data.nearest_buy_side.pct_distance) < Math.abs(data.nearest_sell_side.pct_distance)
              ? `${data.nearest_buy_side.label ?? "Buy-side"} (${data.nearest_buy_side.pct_distance.toFixed(2)}%)`
              : `${data.nearest_sell_side.label ?? "Sell-side"} (${data.nearest_sell_side.pct_distance.toFixed(2)}%)`
            : "—"}
        </Stat>
      </div>

      {/* Buy-side / Sell-side cards */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <LiquidityCard
          title="Short Protective Liquidity — Buy Stops"
          rows={[
            ["Last Bearish Shift", data.buy_side.last_bearish_shift],
            ...data.buy_side.short_term_highs.map(
              (lvl, i): [string, OpenFloatLevel] => [`Short-Term High ${i + 1}`, lvl]
            ),
            ["3M High", data.buy_side.three_month_high],
            ["6M High", data.buy_side.six_month_high],
            ["12M High", data.buy_side.twelve_month_high],
          ]}
        />
        <LiquidityCard
          title="Long Protective Liquidity — Sell Stops"
          rows={[
            ["Last Bullish Shift", data.sell_side.last_bullish_shift],
            ...data.sell_side.short_term_lows.map(
              (lvl, i): [string, OpenFloatLevel] => [`Short-Term Low ${i + 1}`, lvl]
            ),
            ["3M Low", data.sell_side.three_month_low],
            ["6M Low", data.sell_side.six_month_low],
            ["12M Low", data.sell_side.twelve_month_low],
          ]}
        />
      </div>

      {/* Liquidity map */}
      <LiquidityMap data={data} />

      {/* AI Interpretation */}
      <div className="rounded border border-border bg-bg/40 p-4">
        <div className="text-xs uppercase tracking-wide text-muted">AI Interpretation</div>
        <p className="mt-1 text-sm text-ink">{data.interpretation}</p>
      </div>
    </section>
  );
}

function LiquidityCard({ title, rows }: { title: string; rows: [string, OpenFloatLevel | "Data unavailable"][] }) {
  return (
    <div className="rounded border border-border p-4">
      <h3 className="text-sm font-medium text-ink">{title}</h3>
      <ul className="mt-3 space-y-2">
        {rows.map(([label, level]) => (
          <li
            key={label}
            className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-border/60 pb-2 text-sm last:border-0 last:pb-0"
          >
            <span className="text-muted">{label}</span>
            {level === "Data unavailable" ? (
              <span className="text-xs text-muted">Data unavailable</span>
            ) : (
              <span className="flex items-center gap-2">
                <span className={`font-mono text-xs tabular ${level.sweep_status === "SWEPT" ? "text-muted line-through" : "text-ink"}`}>
                  {level.price}
                </span>
                <span className="text-xs text-muted">
                  {level.pct_distance > 0 ? "+" : ""}
                  {level.pct_distance.toFixed(2)}%
                </span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] uppercase ${
                    level.sweep_status === "SWEPT" ? "bg-muted/20 text-muted" : "bg-gold/10 text-gold"
                  }`}
                >
                  {level.sweep_status}
                </span>
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function LiquidityMap({ data }: { data: OpenFloatAnalysis }) {
  const buyLevels: { label: string; level: OpenFloatLevel }[] = [
    data.buy_side.last_bearish_shift !== "Data unavailable" && {
      label: "Bearish Shift",
      level: data.buy_side.last_bearish_shift,
    },
    ...data.buy_side.short_term_highs.map((level) => ({ label: "ST High", level })),
    data.buy_side.three_month_high !== "Data unavailable" && { label: "3M High", level: data.buy_side.three_month_high },
    data.buy_side.six_month_high !== "Data unavailable" && { label: "6M High", level: data.buy_side.six_month_high },
    data.buy_side.twelve_month_high !== "Data unavailable" && {
      label: "12M High",
      level: data.buy_side.twelve_month_high,
    },
  ].filter(Boolean) as { label: string; level: OpenFloatLevel }[];

  const sellLevels: { label: string; level: OpenFloatLevel }[] = [
    data.sell_side.last_bullish_shift !== "Data unavailable" && {
      label: "Bullish Shift",
      level: data.sell_side.last_bullish_shift,
    },
    ...data.sell_side.short_term_lows.map((level) => ({ label: "ST Low", level })),
    data.sell_side.three_month_low !== "Data unavailable" && { label: "3M Low", level: data.sell_side.three_month_low },
    data.sell_side.six_month_low !== "Data unavailable" && { label: "6M Low", level: data.sell_side.six_month_low },
    data.sell_side.twelve_month_low !== "Data unavailable" && {
      label: "12M Low",
      level: data.sell_side.twelve_month_low,
    },
  ].filter(Boolean) as { label: string; level: OpenFloatLevel }[];

  // Sorted by actual price — highest first above the current-price line,
  // lowest last below it — rather than pixel-proportional distance, which
  // gets unreadable when a 3M high sits at 30% away and a 12M high at 65%.
  buyLevels.sort((a, b) => b.level.price - a.level.price);
  sellLevels.sort((a, b) => b.level.price - a.level.price);

  return (
    <div className="rounded border border-border p-4">
      <div className="text-xs uppercase tracking-wide text-muted">Open Float Liquidity Map</div>
      <div className="mt-3 space-y-1">
        <div className="mb-1 text-center text-[10px] uppercase tracking-wide text-muted">
          Buy-side / protective liquidity
        </div>
        {buyLevels.map((item, i) => (
          <MapRow key={`buy-${i}`} label={item.label} level={item.level} />
        ))}

        <div className="my-2 rounded bg-gold/10 py-2 text-center font-mono text-sm font-medium text-gold tabular">
          {data.current_price} — current market price
        </div>

        {sellLevels.map((item, i) => (
          <MapRow key={`sell-${i}`} label={item.label} level={item.level} />
        ))}
        <div className="mt-1 text-center text-[10px] uppercase tracking-wide text-muted">
          Sell-side / protective liquidity
        </div>
      </div>
    </div>
  );
}

function MapRow({ label, level }: { label: string; level: OpenFloatLevel }) {
  return (
    <div
      className={`flex items-center justify-between rounded px-2 py-1 text-xs ${
        level.sweep_status === "SWEPT" ? "opacity-40" : ""
      }`}
    >
      <span className="text-muted">{label}</span>
      <span className="font-mono tabular text-ink">{level.price}</span>
      <span className="text-muted">
        {level.pct_distance > 0 ? "+" : ""}
        {level.pct_distance.toFixed(2)}%
      </span>
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
