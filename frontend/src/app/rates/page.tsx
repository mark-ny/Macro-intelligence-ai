import { api } from "@/lib/apiClient";
import { YieldCurveChart } from "@/components/charts/YieldCurveChart";

const EXPECTATION_LABEL: Record<string, string> = {
  cuts_expected: "Market is pricing in net rate cuts",
  hikes_expected: "Market is pricing in net rate hikes",
  steady: "Market expects rates to hold roughly steady",
};

export default async function RatesPage() {
  const [snapshot, history] = await Promise.all([
    api.rates.snapshot(),
    api.rates.history("FEDFUNDS", 365),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">Interest rate intelligence</h1>
        <p className="mt-1 text-sm text-muted">
          Fed funds rate and SOFR from FRED, plus a 2Y-yield-derived expectation signal.
        </p>
      </div>

      {!snapshot ? (
        <div className="rounded border border-border bg-panel p-5 text-sm text-muted">
          No data yet — run <code className="font-mono text-ink">POST /api/rates/refresh</code> once
          to seed Supabase.
        </div>
      ) : (
        <section className="rounded border border-border bg-panel p-5">
          <h2 className="font-display text-lg font-medium text-ink">Current rates</h2>
          <div className="mt-4 grid grid-cols-2 gap-4 font-mono tabular sm:grid-cols-3">
            <Stat label="Fed funds rate" value={snapshot.fed_funds_rate} />
            <Stat label="SOFR" value={snapshot.sofr} />
            <Stat label="2Y Treasury" value={snapshot.two_year_yield} />
          </div>
          {snapshot.expectation && (
            <p className="mt-4 border-t border-border pt-4 text-sm text-ink">
              {EXPECTATION_LABEL[snapshot.expectation]}
            </p>
          )}
          <p className="mt-1 text-xs text-muted">As of {snapshot.as_of ?? "unknown"}.</p>
        </section>
      )}

      {history && history.length > 0 && (
        <section className="rounded border border-border bg-panel p-5">
          <h2 className="font-display text-lg font-medium text-ink">Fed funds rate, past year</h2>
          <div className="mt-4">
            <YieldCurveChart data={history} />
          </div>
        </section>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="text-lg text-ink">{typeof value === "number" ? `${value.toFixed(2)}%` : "—"}</div>
    </div>
  );
}
