import { api } from "@/lib/apiClient";

const DECISION_COLOR: Record<string, string> = {
  long: "text-positive",
  short: "text-negative",
  neutral: "text-muted",
};

export default async function AiDecisionPage() {
  const [gold, nasdaq] = await Promise.all([
    api.aiDecision.latest("XAUUSD"),
    api.aiDecision.latest("NQ"),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">AI decision engine</h1>
        <p className="mt-1 text-sm text-muted">
          A transparent, rules-based synthesis of every module above — not a black box, and not
          financial advice.
        </p>
      </div>

      <DecisionCard title="Gold (XAU/USD)" decision={gold} />
      <DecisionCard title="Nasdaq (NQ)" decision={nasdaq} />
    </div>
  );
}

function DecisionCard({
  title,
  decision,
}: {
  title: string;
  decision: Awaited<ReturnType<typeof api.aiDecision.latest>>;
}) {
  return (
    <section className="rounded border border-border bg-panel p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-medium text-ink">{title}</h2>
        {decision && (
          <span className={`text-lg font-medium uppercase ${DECISION_COLOR[decision.decision]}`}>
            {decision.decision}
          </span>
        )}
      </div>

      {!decision ? (
        <p className="mt-3 text-sm text-muted">
          No decision yet — run{" "}
          <code className="font-mono text-ink">POST /api/ai-decision/refresh</code> (after the
          other modules have data).
        </p>
      ) : (
        <>
          <div className="mt-3 h-1.5 w-full rounded-full bg-bg">
            <div
              className="h-1.5 rounded-full bg-gold"
              style={{ width: `${Math.round(decision.confidence * 100)}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-muted">
            Confidence: {Math.round(decision.confidence * 100)}%
          </p>
          <p className="mt-3 text-sm text-ink">{decision.rationale}</p>
        </>
      )}
    </section>
  );
}
