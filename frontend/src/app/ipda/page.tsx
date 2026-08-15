import { api } from "@/lib/apiClient";
import type { IpdaDataRanges, IpdaLevel, IpdaSmartMoneyPattern, IpdaWindow } from "@/types";

export default async function IpdaPage() {
  const [gold, nasdaq] = await Promise.all([
    api.ipda.dataRanges("XAUUSD"),
    api.ipda.dataRanges("NQ"),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-wide text-muted">Macro Analysis</p>
        <h1 className="font-display text-2xl font-medium text-ink">IPDA Data Ranges</h1>
        <p className="mt-1 text-sm text-muted">
          The institutional ~3-4 month price range, smart-money accumulation/distribution vs. a
          benchmark, quarterly structure at 20/40/60-day windows, key reference levels, and
          projected time windows. Levels are potential liquidity, not guaranteed orders.
        </p>
      </div>

      <AssetPanel title="Gold (XAU/USD)" data={gold} />
      <AssetPanel title="Nasdaq (proxied via QQQ)" data={nasdaq} />
    </div>
  );
}

function AssetPanel({ title, data }: { title: string; data: IpdaDataRanges | null }) {
  if (!data || data.error) {
    return (
      <section className="rounded border border-border bg-panel p-5">
        <h2 className="font-display text-lg font-medium text-ink">{title}</h2>
        <p className="mt-3 text-sm text-muted">{data?.error ?? "Data unavailable."}</p>
      </section>
    );
  }

  const buyPatterns = Array.isArray(data.smart_money.buy_program) ? data.smart_money.buy_program : [];
  const sellPatterns = Array.isArray(data.smart_money.sell_program) ? data.smart_money.sell_program : [];
  const benchmarkUnavailable = !Array.isArray(data.smart_money.buy_program);

  return (
    <section className="space-y-4 rounded border border-border bg-panel p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-lg font-medium text-ink">{title}</h2>
        <span className="text-xs text-muted">Benchmark: {data.benchmark}</span>
      </div>

      {/* Current state */}
      <div className="grid grid-cols-2 gap-3 rounded border border-border bg-bg/40 p-4 sm:grid-cols-4">
        <Stat label="Current price">
          <span className="font-mono tabular">{data.current_price}</span>
        </Stat>
        <Stat label="IPDA range ({'>'}=3mo)">
          <span className="font-mono text-xs tabular">
            {data.ipda_range.low} – {data.ipda_range.high}
          </span>
        </Stat>
        <Stat label="Previous major shift">
          {data.previous_market_shift ? (
            <span className={data.previous_market_shift.direction === "bullish" ? "text-positive" : "text-negative"}>
              {data.previous_market_shift.direction} @ {data.previous_market_shift.price}
            </span>
          ) : (
            "None confirmed yet"
          )}
        </Stat>
        <Stat label="Next cast-forward window">
          {typeof data.cast_forward["20d"] === "object" ? (data.cast_forward["20d"] as { estimated_date: string }).estimated_date : "—"}
        </Stat>
      </div>

      {/* Smart money */}
      <div className="rounded border border-border p-4">
        <h3 className="text-sm font-medium text-ink">Smart Money — Accumulation / Distribution</h3>
        {benchmarkUnavailable ? (
          <p className="mt-2 text-xs text-muted">Benchmark data unavailable — patterns can&apos;t be computed.</p>
        ) : buyPatterns.length === 0 && sellPatterns.length === 0 ? (
          <p className="mt-2 text-xs text-muted">No accumulation/distribution pattern currently confirmed against the benchmark.</p>
        ) : (
          <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <PatternList label="Buy program" patterns={buyPatterns} tone="text-positive" />
            <PatternList label="Sell program" patterns={sellPatterns} tone="text-negative" />
          </div>
        )}
      </div>

      {/* Quarterly shift 20/40/60D */}
      <div className="rounded border border-border p-4">
        <h3 className="text-sm font-medium text-ink">Quarterly Shift</h3>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <WindowCard label="20 trading days" w={data.quarterly_shift["20d"]} />
          <WindowCard label="40 trading days" w={data.quarterly_shift["40d"]} />
          <WindowCard label="60 trading days" w={data.quarterly_shift["60d"]} />
        </div>
      </div>

      {/* Institutional reference points */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <LevelCard title="Old Highs / Bearish Order Blocks" levels={data.institutional_reference_points.old_highs} order_blocks={data.institutional_reference_points.bearish_order_blocks} />
        <LevelCard title="Old Lows / Bullish Order Blocks" levels={data.institutional_reference_points.old_lows} order_blocks={data.institutional_reference_points.bullish_order_blocks} />
      </div>

      {/* Open Float 20/40/60D */}
      <div className="rounded border border-border p-4">
        <h3 className="text-sm font-medium text-ink">Open Float — 20 / 40 / 60 Day</h3>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {(["near_term_20d", "short_term_40d", "intermediate_60d"] as const).map((key) => {
            const w = data.open_float[key];
            return (
              <div key={key} className="rounded border border-border p-3 text-xs">
                <div className="text-muted">{key.replace(/_/g, " ")}</div>
                {w.buy_stops && w.sell_stops ? (
                  <>
                    <div className="mt-1 flex justify-between">
                      <span className="text-muted">Buy stops</span>
                      <span className="font-mono tabular text-ink">{w.buy_stops.price ?? w.buy_stops.level}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted">Sell stops</span>
                      <span className="font-mono tabular text-ink">{w.sell_stops.price ?? w.sell_stops.level}</span>
                    </div>
                  </>
                ) : (
                  <div className="mt-1 text-muted">Data unavailable</div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Interpretation */}
      <div className="rounded border border-border bg-bg/40 p-4">
        <div className="text-xs uppercase tracking-wide text-muted">Interpretation</div>
        <p className="mt-1 text-sm text-ink">{data.interpretation}</p>
      </div>
    </section>
  );
}

function PatternList({ label, patterns, tone }: { label: string; patterns: IpdaSmartMoneyPattern[]; tone: string }) {
  if (patterns.length === 0) {
    return (
      <div>
        <div className="text-xs text-muted">{label}</div>
        <p className="mt-1 text-xs text-muted">None</p>
      </div>
    );
  }
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <ul className="mt-1 space-y-1">
        {patterns.map((p, i) => (
          <li key={i} className="text-xs">
            <span className={tone}>{p.classification}</span>
            <span className="ml-1 text-muted">(Pattern {p.pattern})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function WindowCard({ label, w }: { label: string; w: IpdaWindow }) {
  if (w.status === "INSUFFICIENT DATA") {
    return (
      <div className="rounded border border-border p-3 text-xs">
        <div className="text-muted">{label}</div>
        <div className="mt-1 text-muted">Data unavailable</div>
      </div>
    );
  }
  return (
    <div className="rounded border border-border p-3 text-xs">
      <div className="text-muted">{label}</div>
      <div className="mt-1 font-mono tabular text-ink">
        {w.low} – {w.high}
      </div>
      <div className="mt-1 text-muted">Structure: <span className="text-ink">{w.structure}</span></div>
      {w.most_recent_shift && (
        <div className="mt-1 text-muted">
          Last shift: <span className={w.most_recent_shift.direction === "bullish" ? "text-positive" : "text-negative"}>{w.most_recent_shift.direction}</span>
        </div>
      )}
    </div>
  );
}

function LevelCard({ title, levels, order_blocks }: { title: string; levels: IpdaLevel[]; order_blocks: IpdaLevel[] }) {
  const rows = [...levels, ...order_blocks];
  return (
    <div className="rounded border border-border p-4">
      <h3 className="text-sm font-medium text-ink">{title}</h3>
      {rows.length === 0 ? (
        <p className="mt-2 text-xs text-muted">Data unavailable</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {rows.map((lvl, i) => (
            <li key={i} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-border/60 pb-2 text-sm last:border-0 last:pb-0">
              <span className="font-mono text-xs tabular text-ink">{lvl.price}</span>
              {typeof lvl.pct_distance === "number" && (
                <span className="text-xs text-muted">
                  {lvl.pct_distance > 0 ? "+" : ""}
                  {lvl.pct_distance.toFixed(2)}%
                </span>
              )}
              <span className="rounded bg-muted/10 px-1.5 py-0.5 text-[10px] uppercase text-muted">
                {lvl.status ?? lvl.mitigation_status ?? (lvl.filled ? "FILLED" : "OPEN")}
              </span>
            </li>
          ))}
        </ul>
      )}
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
