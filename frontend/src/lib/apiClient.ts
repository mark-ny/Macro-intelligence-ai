import type {
  AiDecision,
  BigPictureSummary,
  CalendarEvent,
  DxySnapshot,
  HistoricalOutcome,
  IctSignal,
  IntermediateSummary,
  IpdaDataRanges,
  NewsHeadline,
  OpenFloatAnalysis,
  PerformanceSummary,
  RateSnapshot,
  ShortTermSummary,
  WinRateSummary,
  YieldCurveResponse,
  YieldHistoryPoint,
} from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Thin fetch wrapper shared by Server Components and Client Components.
 * Returns null instead of throwing on failure so pages can render a
 * friendly "backend not reachable" state.
 */
async function apiGet<T>(path: string, revalidateSeconds = 60): Promise<T | null> {
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      next: { revalidate: revalidateSeconds },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export const api = {
  health: () => apiGet<{ status: string }>("/api/health", 0),

  treasury: {
    yieldCurve: () => apiGet<YieldCurveResponse>("/api/treasury/yield-curve"),
    history: (series: string, days = 180) =>
      apiGet<YieldHistoryPoint[]>(`/api/treasury/history?series=${series}&days=${days}`),
  },

  rates: {
    snapshot: () => apiGet<RateSnapshot>("/api/rates/snapshot"),
    history: (series: string, days = 180) =>
      apiGet<YieldHistoryPoint[]>(`/api/rates/history?series=${series}&days=${days}`),
  },

  dxy: {
    snapshot: () => apiGet<DxySnapshot>("/api/dxy/snapshot"),
    history: (days = 180) => apiGet<YieldHistoryPoint[]>(`/api/dxy/history?days=${days}`),
  },

  news: {
    headlines: (limit = 15) => apiGet<NewsHeadline[]>(`/api/news/headlines?limit=${limit}`),
    calendar: (daysAhead = 14) =>
      apiGet<CalendarEvent[]>(`/api/news/calendar?days_ahead=${daysAhead}`),
  },

  ict: {
    signals: (asset: string, limit = 20) =>
      apiGet<IctSignal[]>(`/api/ict/signals?asset=${asset}&limit=${limit}`),
  },

  aiDecision: {
    latest: (asset: string) => apiGet<AiDecision | null>(`/api/ai-decision/latest?asset=${asset}`),
  },

  history: {
    outcomes: (asset: string, limit = 20) =>
      apiGet<HistoricalOutcome[]>(`/api/history/outcomes?asset=${asset}&limit=${limit}`),
    winRate: (asset: string) => apiGet<WinRateSummary>(`/api/history/win-rate?asset=${asset}`),
  },

  // Notifications are intentionally absent here — the frontend reads them
  // directly from Supabase (RLS-scoped to auth.uid()). See
  // frontend/src/app/notifications/page.tsx and
  // backend/app/services/notifications_service.py for why.

  performance: {
    summary: (asset: string) =>
      apiGet<PerformanceSummary>(`/api/performance/summary?asset=${asset}`),
  },

  topDown: {
    bigPicture: (asset: string) =>
      apiGet<BigPictureSummary>(`/api/top-down/big-picture?asset=${asset}`),
    intermediate: (asset: string) =>
      apiGet<IntermediateSummary>(`/api/top-down/intermediate?asset=${asset}`),
    shortTerm: (asset: string) =>
      apiGet<ShortTermSummary>(`/api/top-down/short-term?asset=${asset}`),
  },

  macroAnalysis: {
    openFloat: (asset: string) =>
      apiGet<OpenFloatAnalysis>(`/api/macro-analysis/open-float?asset=${asset}`),
  },

  ipda: {
    dataRanges: (symbol: string) =>
      apiGet<IpdaDataRanges>(`/api/ipda/data-ranges?symbol=${symbol}`),
  },
};
