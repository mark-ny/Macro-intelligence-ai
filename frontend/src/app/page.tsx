import Link from "next/link";

import { api } from "@/lib/apiClient";

function formatPct(value: number | null | undefined, digits = 2) {
  return typeof value === "number" ? `${value.toFixed(digits)}%` : "—";
}

const DECISION_COLOR: Record<string, string> = {
  long: "text-positive",
  short: "text-negative",
  neutral: "text-muted",
};

export default async function DashboardPage() {
  const [curve, rates, dxy, goldDecision, nqDecision, headlines] = await Promise.all([
    api.treasury.yieldCurve(),
    api.rates.snapshot(),
    api.dxy.snapshot(),
    api.aiDecision.latest("XAUUSD"),
    api.aiDecision.latest("NQ"),
    api.news.headlines(3),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">Dashboard</h1>
        <p className="mt-1 text-sm text-muted">
          Gold (XAU/USD) and Nasdaq (NQ) macro intelligence, all modules live.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <DecisionCard title="Gold (XAU/USD)" href="/ai-decision" decision={goldDecision} />
        <DecisionCard title="Nasdaq (NQ)" href="/ai-decision" decision={nqDecision} />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link href="/treasury" className="rounded border border-border bg-panel p-4 hover:border-steel/50">
          <div className="text-xs text-muted">Treasury — 10Y-2Y spread</div>
          <div className={`mt-1 font-mono text-lg tabular ${curve?.inverted ? "text-negative" : "text-ink"}`}>
            {formatPct(curve?.spreads?.["10Y2Y"])}
          </div>
        </Link>
        <Link href="/rates" className="rounded border border-border bg-panel p-4 hover:border-steel/50">
          <div className="text-xs text-muted">Fed funds rate</div>
          <div className="mt-1 font-mono text-lg tabular text-ink">{formatPct(rates?.fed_funds_rate)}</div>
        </Link>
        <Link href="/dxy" className="rounded border border-border bg-panel p-4 hover:border-steel/50">
          <div className="text-xs text-muted">DXY (broad index)</div>
          <div className="mt-1 font-mono text-lg tabular text-ink">
            {dxy?.latest_value?.toFixed(2) ?? "—"}
          </div>
        </Link>
      </div>

      <section className="rounded border border-border bg-panel p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-medium text-ink">Latest headlines</h2>
          <Link href="/news" className="text-xs text-gold hover:underline">
            Open module →
          </Link>
        </div>
        {!headlines || headlines.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No headlines yet.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {headlines.map((h) => (
              <li key={h.id} className="text-sm text-ink">
                {h.headline}
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <NavCard href="/top-down" label="Top-down analysis" />
        <NavCard href="/ict" label="ICT analysis" />
        <NavCard href="/history" label="Historical learning" />
        <NavCard href="/performance" label="Performance analytics" />
        <NavCard href="/notifications" label="Notifications" />
      </div>
    </div>
  );
}

function DecisionCard({
  title,
  href,
  decision,
}: {
  title: string;
  href: string;
  decision: Awaited<ReturnType<typeof api.aiDecision.latest>>;
}) {
  return (
    <Link href={href} className="block rounded border border-border bg-panel p-5 hover:border-steel/50">
      <div className="flex items-center justify-between">
        <div className="font-display text-sm font-medium text-ink">{title}</div>
        {decision && (
          <span className={`text-sm font-medium uppercase ${DECISION_COLOR[decision.decision]}`}>
            {decision.decision}
          </span>
        )}
      </div>
      <p className="mt-2 text-xs text-muted">
        {decision ? decision.rationale : "No decision yet — run the refresh chain."}
      </p>
    </Link>
  );
}

function NavCard({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="block rounded border border-border bg-panel p-4 text-sm text-ink transition-colors hover:border-steel/50"
    >
      {label} →
    </Link>
  );
}
