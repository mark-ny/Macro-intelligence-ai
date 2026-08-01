import { api } from "@/lib/apiClient";

const SENTIMENT_COLOR: Record<string, string> = {
  positive: "text-positive",
  negative: "text-negative",
  neutral: "text-muted",
};

export default async function NewsPage() {
  const [headlines, calendar] = await Promise.all([
    api.news.headlines(15),
    api.news.calendar(21),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">Economic news intelligence</h1>
        <p className="mt-1 text-sm text-muted">
          Headlines from Currents, plus the FRED release calendar for high-impact data.
        </p>
      </div>

      <section className="rounded border border-border bg-panel p-5">
        <h2 className="font-display text-lg font-medium text-ink">Upcoming releases</h2>
        {!calendar || calendar.length === 0 ? (
          <p className="mt-3 text-sm text-muted">
            No calendar data yet — run <code className="font-mono text-ink">POST /api/news/refresh</code>.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {calendar.map((event, i) => (
              <li key={i} className="flex items-center justify-between text-sm">
                <span className="text-ink">{event.release_name}</span>
                <span className="font-mono text-xs text-muted tabular">{event.scheduled_at}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded border border-border bg-panel p-5">
        <h2 className="font-display text-lg font-medium text-ink">Recent headlines</h2>
        {!headlines || headlines.length === 0 ? (
          <p className="mt-3 text-sm text-muted">
            No headlines yet — run <code className="font-mono text-ink">POST /api/news/refresh</code>.
          </p>
        ) : (
          <ul className="mt-3 space-y-3">
            {headlines.map((item) => (
              <li key={item.id} className="border-b border-border pb-3 last:border-0">
                <a
                  href={item.url ?? undefined}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-ink hover:text-gold hover:underline"
                >
                  {item.headline}
                </a>
                <div className="mt-1 flex gap-3 text-xs text-muted">
                  <span>{item.source}</span>
                  <span className={SENTIMENT_COLOR[item.sentiment]}>{item.sentiment}</span>
                  <span>{item.related_asset}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
