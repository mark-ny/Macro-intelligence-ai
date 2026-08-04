import { api } from "@/lib/apiClient";

const OUTCOME_COLOR: Record<string, string> = {
  win: "text-positive",
  loss: "text-negative",
  neutral: "text-muted",
};

export default async function HistoryPage() {
  const [goldRate, nasdaqRate, goldOutcomes] = await Promise.all([
    api.history.winRate("XAUUSD"),
    api.history.winRate("NQ"),
    api.history.outcomes("XAUUSD", 20),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">Historical learning</h1>
        <p className="mt-1 text-sm text-muted">
          Past AI decisions, graded against what price actually did afterward.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <WinRateCard title="Gold (XAU/USD)" data={goldRate} />
        <WinRateCard title="Nasdaq (NQ)" data={nasdaqRate} />
      </div>

      <section className="rounded border border-border bg-panel p-5">
        <h2 className="font-display text-lg font-medium text-ink">Recent gold outcomes</h2>
        {!goldOutcomes || goldOutcomes.length === 0 ? (
          <p className="mt-3 text-sm text-muted">
            No graded decisions yet — decisions are evaluated 5 days after they're made, via{" "}
            <code className="font-mono text-ink">POST /api/history/refresh</code>.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {goldOutcomes.map((o) => (
              <li
                key={o.id}
                className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-border/60 pb-2 text-sm last:border-0 last:pb-0"
              >
                <span className={OUTCOME_COLOR[o.outcome]}>{o.outcome}</span>
                <span className="font-mono tabular text-ink">
                  {o.pnl_pct !== null ? `${o.pnl_pct.toFixed(2)}%` : "—"}
                </span>
                <span className="text-xs text-muted">{o.evaluated_at?.slice(0, 10)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function WinRateCard({ title, data }: { title: string; data: Awaited<ReturnType<typeof api.history.winRate>> }) {
  return (
    <div className="rounded border border-border bg-panel p-5">
      <h3 className="font-display text-sm font-medium text-ink">{title}</h3>
      <div className="mt-2 font-mono text-2xl tabular text-ink">
        {data?.win_rate !== null && data?.win_rate !== undefined
          ? `${Math.round(data.win_rate * 100)}%`
          : "—"}
      </div>
      <p className="mt-1 text-xs text-muted">
        {data ? `${data.wins}W / ${data.losses}L / ${data.neutral} neutral, of ${data.total} graded` : "No data"}
      </p>
    </div>
  );
}
