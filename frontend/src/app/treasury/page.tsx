import { api } from "@/lib/apiClient";
import { YieldCurveChart } from "@/components/charts/YieldCurveChart";

const MATURITIES: { key: string; label: string }[] = [
  { key: "3M", label: "3 month" },
  { key: "2Y", label: "2 year" },
  { key: "5Y", label: "5 year" },
  { key: "10Y", label: "10 year" },
  { key: "30Y", label: "30 year" },
];

export default async function TreasuryPage() {
  const [curve, history] = await Promise.all([
    api.treasury.yieldCurve(),
    api.treasury.history("10Y", 365),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">Treasury intelligence</h1>
        <p className="mt-1 text-sm text-muted">
          Par yields and curve spreads from FRED, refreshed a few times daily.
        </p>
      </div>

      {!curve && (
        <div className="rounded border border-border bg-panel p-5 text-sm text-muted">
          No data yet. Set <code className="font-mono text-ink">FRED_API_KEY</code> in the
          backend, then call{" "}
          <code className="font-mono text-ink">POST /api/treasury/refresh</code> once to
          seed Supabase — see README &gt; Local development.
        </div>
      )}

      {curve && (
        <section className="rounded border border-border bg-panel p-5">
          <h2 className="font-display text-lg font-medium text-ink">Yield curve</h2>
          <div className="mt-4 grid grid-cols-2 gap-4 font-mono tabular sm:grid-cols-5">
            {MATURITIES.map(({ key, label }) => (
              <div key={key}>
                <div className="text-xs text-muted">{label}</div>
                <div className="text-lg text-ink">
                  {curve.yield_curve[key]?.toFixed(2) ?? "—"}%
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex gap-6 border-t border-border pt-4 font-mono tabular text-sm">
            <div>
              <span className="text-muted">10Y–2Y spread </span>
              <span className={curve.inverted ? "text-negative" : "text-ink"}>
                {curve.spreads["10Y2Y"]?.toFixed(2) ?? "—"}
              </span>
            </div>
            <div>
              <span className="text-muted">10Y–3M spread </span>
              <span className="text-ink">{curve.spreads["10Y3M"]?.toFixed(2) ?? "—"}</span>
            </div>
          </div>
          {curve.inverted && (
            <p className="mt-3 text-xs text-negative">
              The 10Y–2Y spread is negative — the curve is currently inverted.
            </p>
          )}
        </section>
      )}

      {history && history.length > 0 && (
        <section className="rounded border border-border bg-panel p-5">
          <h2 className="font-display text-lg font-medium text-ink">10 year yield, past year</h2>
          <div className="mt-4">
            <YieldCurveChart data={history} />
          </div>
        </section>
      )}
    </div>
  );
}
