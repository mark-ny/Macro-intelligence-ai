import { api } from "@/lib/apiClient";
import { YieldCurveChart } from "@/components/charts/YieldCurveChart";

const TREND_LABEL: Record<string, string> = {
  up: "Trending stronger",
  down: "Trending weaker",
  flat: "Roughly flat",
};

export default async function DxyPage() {
  const [snapshot, history] = await Promise.all([api.dxy.snapshot(), api.dxy.history(365)]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">DXY forecast</h1>
        <p className="mt-1 text-sm text-muted">
          FRED's broad trade-weighted dollar index, with a disclosed OLS trend forecast — not a
          proprietary model, and not a guarantee.
        </p>
      </div>

      {!snapshot?.latest_value ? (
        <div className="rounded border border-border bg-panel p-5 text-sm text-muted">
          No data yet — run <code className="font-mono text-ink">POST /api/dxy/refresh</code> once
          to seed Supabase.
        </div>
      ) : (
        <section className="rounded border border-border bg-panel p-5">
          <h2 className="font-display text-lg font-medium text-ink">Current index</h2>
          <div className="mt-4 font-mono text-2xl tabular text-ink">
            {snapshot.latest_value.toFixed(2)}
          </div>
          <p className="text-xs text-muted">As of {snapshot.latest_date}</p>

          {snapshot.forecast && (
            <div className="mt-4 border-t border-border pt-4">
              <div className="text-sm text-ink">
                {TREND_LABEL[snapshot.forecast.trend]} — {snapshot.forecast.horizon_days}-day
                projection: <span className="font-mono tabular">{snapshot.forecast.predicted_value.toFixed(2)}</span>
                {" "}
                <span className="text-muted">
                  (range {snapshot.forecast.lower_bound.toFixed(2)}–{snapshot.forecast.upper_bound.toFixed(2)})
                </span>
              </div>
              <p className="mt-1 text-xs text-muted">
                Fit quality (R²): {(snapshot.forecast.r_squared * 100).toFixed(0)}% · generated{" "}
                {new Date(snapshot.forecast.generated_at).toLocaleString()}
              </p>
            </div>
          )}
        </section>
      )}

      {history && history.length > 0 && (
        <section className="rounded border border-border bg-panel p-5">
          <h2 className="font-display text-lg font-medium text-ink">Index, past year</h2>
          <div className="mt-4">
            <YieldCurveChart data={history} />
          </div>
        </section>
      )}
    </div>
  );
}
