import { api } from "@/lib/apiClient";

export default async function PerformancePage() {
  const [gold, nasdaq] = await Promise.all([
    api.performance.summary("XAUUSD"),
    api.performance.summary("NQ"),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">Performance analytics</h1>
        <p className="mt-1 text-sm text-muted">
          Win rate, average PnL, and drawdown, recomputed daily from graded AI decisions.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <SummaryCard title="Gold (XAU/USD)" data={gold} />
        <SummaryCard title="Nasdaq (NQ)" data={nasdaq} />
      </div>
    </div>
  );
}

function SummaryCard({ title, data }: { title: string; data: Awaited<ReturnType<typeof api.performance.summary>> }) {
  return (
    <section className="rounded border border-border bg-panel p-5">
      <h2 className="font-display text-lg font-medium text-ink">{title}</h2>
      {!data || data.total_decisions === 0 ? (
        <p className="mt-3 text-sm text-muted">
          No graded decisions yet — this fills in once the Historical Learning Engine has
          evaluated a few AI decisions.
        </p>
      ) : (
        <div className="mt-3 grid grid-cols-3 gap-4 font-mono tabular">
          <div>
            <div className="text-xs text-muted">Win rate</div>
            <div className="text-lg text-ink">
              {data.win_rate !== null ? `${Math.round(data.win_rate * 100)}%` : "—"}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted">Avg PnL</div>
            <div className={`text-lg ${(data.avg_pnl_pct ?? 0) >= 0 ? "text-positive" : "text-negative"}`}>
              {data.avg_pnl_pct !== null ? `${data.avg_pnl_pct.toFixed(2)}%` : "—"}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted">Graded</div>
            <div className="text-lg text-ink">{data.total_decisions}</div>
          </div>
        </div>
      )}
    </section>
  );
}
