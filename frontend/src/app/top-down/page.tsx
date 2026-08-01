import { api } from "@/lib/apiClient";
import type {
  BigPictureSummary,
  IntermediateSummary,
  ShortTermSummary,
} from "@/types";

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const BIAS_COLOR: Record<string, string> = {
  bullish: "text-positive",
  bearish: "text-negative",
  neutral: "text-muted",
};

const REGIME_COPY: Record<string, string> = {
  inflationary: "Inflationary — CPI growth accelerating",
  disinflationary: "Disinflationary — CPI positive but slowing",
  deflationary: "Deflationary — CPI falling year over year",
  higher_rates_expected: "Higher rates expected",
  lower_rates_expected: "Lower rates expected",
  unexpected_change: "Unexpected change — the Fed just moved against what was priced in",
  steady: "Steady — no strong directional pricing",
};

export default async function TopDownPage() {
  const [goldBig, nqBig, goldMid, nqMid, goldShort, nqShort] = await Promise.all([
    api.topDown.bigPicture("XAUUSD"),
    api.topDown.bigPicture("NQ"),
    api.topDown.intermediate("XAUUSD"),
    api.topDown.intermediate("NQ"),
    api.topDown.shortTerm("XAUUSD"),
    api.topDown.shortTerm("NQ"),
  ]);

  return (
    <div className="space-y-10">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">Top-down analysis</h1>
        <p className="mt-1 text-sm text-muted">
          The classic three-perspective framework — Big Picture narrows into Intermediate,
          which narrows into Short-Term. Read top to bottom, same as it's taught.
        </p>
      </div>

      <PerspectiveSection number={1} title="Big picture" accent="gold">
        <MacroRegimeCard regime={goldBig?.macro_regime ?? nqBig?.macro_regime ?? null} />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <SeasonalityCard title="Gold (XAU/USD) seasonality" data={goldBig} />
          <SeasonalityCard title="Nasdaq (QQQ proxy) seasonality" data={nqBig} />
        </div>
      </PerspectiveSection>

      <PerspectiveSection number={2} title="Intermediate" accent="steel">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <TopDownBiasCard title="Gold (XAU/USD)" data={goldMid} />
          <TopDownBiasCard title="Nasdaq (QQQ proxy)" data={nqMid} />
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <SentimentCard title="Gold (XAU/USD)" data={goldMid} />
          <SentimentCard title="Nasdaq (QQQ proxy)" data={nqMid} />
        </div>
      </PerspectiveSection>

      <PerspectiveSection number={3} title="Short-term" accent="ink">
        <CorrelationCard data={goldShort} />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <TimePriceIpdaCard title="Gold (XAU/USD)" data={goldShort} />
          <TimePriceIpdaCard title="Nasdaq (QQQ proxy)" data={nqShort} />
        </div>
      </PerspectiveSection>
    </div>
  );
}

// ---------------------------------------------------------------------------

function PerspectiveSection({
  number,
  title,
  accent,
  children,
}: {
  number: number;
  title: string;
  accent: "gold" | "steel" | "ink";
  children: React.ReactNode;
}) {
  const borderColor = accent === "gold" ? "border-l-gold" : accent === "steel" ? "border-l-steel" : "border-l-muted";
  return (
    <section className={`space-y-4 border-l-2 ${borderColor} pl-5`}>
      <h2 className="font-display text-xl font-medium text-ink">
        <span className="text-muted">{number}.</span> {title}
      </h2>
      {children}
    </section>
  );
}

function EmptyNote({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-muted">{children}</p>;
}

function MacroRegimeCard({ regime }: { regime: BigPictureSummary["macro_regime"] }) {
  if (!regime) {
    return (
      <div className="rounded border border-border bg-panel p-5">
        <EmptyNote>
          No macro regime yet — run <code className="font-mono text-ink">POST /api/top-down/refresh</code>.
        </EmptyNote>
      </div>
    );
  }
  return (
    <div className="rounded border border-border bg-panel p-5">
      <h3 className="font-display text-sm font-medium text-ink">
        Macro market &amp; interest rate regime
      </h3>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <div className="text-xs text-muted">Macro market analysis</div>
          <div className="text-sm text-ink">
            {regime.inflation_regime ? REGIME_COPY[regime.inflation_regime] : "Not enough CPI history yet"}
            {regime.cpi_yoy_pct !== null && (
              <span className="font-mono tabular text-muted"> ({regime.cpi_yoy_pct.toFixed(1)}% YoY)</span>
            )}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted">Interest rate analysis</div>
          <div className="text-sm text-ink">
            {regime.rate_regime ? REGIME_COPY[regime.rate_regime] : "No data yet"}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted">Inter-market — commodities (CRB proxy)</div>
          <div className="text-sm text-ink capitalize">{regime.commodity_trend ?? "No data yet"}</div>
        </div>
        <div>
          <div className="text-xs text-muted">Inter-market — USDX</div>
          <div className="text-sm text-ink capitalize">{regime.usdx_trend ?? "No data yet"}</div>
        </div>
      </div>
    </div>
  );
}

function SeasonalityCard({ title, data }: { title: string; data: BigPictureSummary | null }) {
  const rows = data?.seasonality_by_month ?? [];
  return (
    <div className="rounded border border-border bg-panel p-5">
      <h3 className="font-display text-sm font-medium text-ink">{title}</h3>
      {rows.length === 0 ? (
        <EmptyNote>Not enough price history yet for seasonality.</EmptyNote>
      ) : (
        <div className="mt-3 grid grid-cols-6 gap-2 font-mono text-xs tabular sm:grid-cols-12">
          {rows.map((m) => (
            <div key={m.month} className="text-center">
              <div className="text-muted">{MONTH_NAMES[m.month - 1]}</div>
              <div className={m.avg_return_pct >= 0 ? "text-positive" : "text-negative"}>
                {m.avg_return_pct.toFixed(1)}%
              </div>
            </div>
          ))}
        </div>
      )}
      {data?.current_month_seasonality && (
        <p className="mt-3 border-t border-border pt-3 text-xs text-muted">
          This month, historically: {data.current_month_seasonality.win_rate_pct.toFixed(0)}% of days
          positive across {data.current_month_seasonality.years_sampled} year
          {data.current_month_seasonality.years_sampled === 1 ? "" : "s"} of data.
        </p>
      )}
    </div>
  );
}

function TopDownBiasCard({ title, data }: { title: string; data: IntermediateSummary | null }) {
  const bias = data?.top_down_bias;
  return (
    <div className="rounded border border-border bg-panel p-5">
      <h3 className="font-display text-sm font-medium text-ink">{title} — top-down bias</h3>
      {!bias ? (
        <EmptyNote>No bias data yet.</EmptyNote>
      ) : (
        <ul className="mt-3 space-y-2">
          {(["1M", "1W", "1D"] as const).map((tf) => {
            const entry = bias[tf];
            const label = tf === "1M" ? "Monthly" : tf === "1W" ? "Weekly" : "Daily";
            return (
              <li key={tf} className="flex items-start justify-between gap-3 text-sm">
                <span className="text-muted">{label}</span>
                {entry ? (
                  <span className="text-right">
                    <span className={`font-medium uppercase ${BIAS_COLOR[entry.bias]}`}>{entry.bias}</span>
                    <span className="block text-xs text-muted">{entry.notes}</span>
                  </span>
                ) : (
                  <span className="text-muted">—</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function SentimentCard({ title, data }: { title: string; data: IntermediateSummary | null }) {
  const sentiment = data?.sentiment;
  const counts = sentiment?.news_sentiment_counts;
  const cot = sentiment?.cot_positioning;
  return (
    <div className="rounded border border-border bg-panel p-5">
      <h3 className="font-display text-sm font-medium text-ink">{title} — market sentiment</h3>
      <div className="mt-3 space-y-3 text-sm">
        <div>
          <div className="text-xs text-muted">News sentiment (last 20 headlines)</div>
          {counts ? (
            <div className="flex gap-4 font-mono tabular">
              <span className="text-positive">{counts.positive} pos</span>
              <span className="text-muted">{counts.neutral} neu</span>
              <span className="text-negative">{counts.negative} neg</span>
            </div>
          ) : (
            <span className="text-muted">No headlines yet</span>
          )}
        </div>
        <div className="border-t border-border pt-3">
          <div className="text-xs text-muted">COT positioning (CFTC, non-commercial / speculators)</div>
          {cot ? (
            <div>
              <span className="text-ink">{cot.positioning}</span>{" "}
              <span className="font-mono text-xs text-muted tabular">
                (net {cot.net_noncommercial.toLocaleString()}
                {cot.net_noncommercial_pct !== null ? `, ${cot.net_noncommercial_pct}%` : ""}) — report {cot.report_date}
              </span>
            </div>
          ) : (
            <span className="text-muted">No COT data yet</span>
          )}
        </div>
      </div>
    </div>
  );
}

function CorrelationCard({ data }: { data: ShortTermSummary | null }) {
  const rows = data?.correlations ?? [];
  return (
    <div className="rounded border border-border bg-panel p-5">
      <h3 className="font-display text-sm font-medium text-ink">Correlation analysis (60-day returns)</h3>
      {rows.length === 0 ? (
        <EmptyNote>
          No correlation data yet — needs market-data, DXY, and Treasury history first.
        </EmptyNote>
      ) : (
        <ul className="mt-3 grid grid-cols-1 gap-2 font-mono text-sm tabular sm:grid-cols-2">
          {rows.map((r, i) => (
            <li key={i} className="flex justify-between">
              <span className="text-muted">
                {r.asset_a} vs {r.asset_b}
              </span>
              <span className={r.correlation >= 0 ? "text-positive" : "text-negative"}>
                {r.correlation.toFixed(2)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TimePriceIpdaCard({ title, data }: { title: string; data: ShortTermSummary | null }) {
  const levels = data?.time_and_price?.price_levels;
  const tendency = data?.time_and_price?.day_of_week_tendency;
  const ranges = data?.ipda_ranges ?? [];

  return (
    <div className="rounded border border-border bg-panel p-5">
      <h3 className="font-display text-sm font-medium text-ink">{title} — time, price &amp; IPDA</h3>

      <div className="mt-3">
        <div className="text-xs text-muted">Reference levels (price theory)</div>
        {levels ? (
          <div className="mt-1 space-y-1 font-mono text-sm tabular">
            <LevelRow label="Prev day" level={levels.previous_day} />
            <LevelRow label="Prev week" level={levels.previous_week} />
            <LevelRow label="Prev month" level={levels.previous_month} />
          </div>
        ) : (
          <EmptyNote>Not enough history yet.</EmptyNote>
        )}
      </div>

      {tendency && tendency.length > 0 && (
        <div className="mt-4 border-t border-border pt-3">
          <div className="text-xs text-muted">Day-of-week tendency (time theory)</div>
          <div className="mt-1 grid grid-cols-5 gap-1 font-mono text-xs tabular">
            {tendency.map((t) => (
              <div key={t.day} className="text-center">
                <div className="text-muted">{t.day.slice(0, 3)}</div>
                <div className={t.avg_return_pct >= 0 ? "text-positive" : "text-negative"}>
                  {t.avg_return_pct.toFixed(2)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 border-t border-border pt-3">
        <div className="text-xs text-muted">IPDA ranges</div>
        {ranges.length === 0 ? (
          <EmptyNote>Not enough history yet.</EmptyNote>
        ) : (
          <ul className="mt-1 space-y-1 text-sm">
            {ranges.map((r) => (
              <li key={r.range_days} className="flex justify-between">
                <span className="text-muted">{r.range_days}-day range</span>
                <span className="text-ink">
                  {r.position.replace("_", " ")}{" "}
                  <span className="font-mono text-xs text-muted tabular">
                    ({r.range_low.toFixed(2)}–{r.range_high.toFixed(2)})
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function LevelRow({ label, level }: { label: string; level: { high: number; low: number } | null | undefined }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span className="text-ink">{level ? `${level.low.toFixed(2)} – ${level.high.toFixed(2)}` : "—"}</span>
    </div>
  );
}
