export interface YieldCurveResponse {
  yield_curve: Record<string, number | null>;
  spreads: Record<string, number | null>;
  inverted: boolean;
  as_of: string | null;
}

export interface YieldHistoryPoint {
  date: string;
  value: number;
}

export interface ModuleStatus {
  module: string;
  status: string;
  implemented: boolean;
}

export interface RateSnapshot {
  fed_funds_rate: number | null;
  sofr: number | null;
  two_year_yield: number | null;
  expectation: "cuts_expected" | "hikes_expected" | "steady" | null;
  as_of: string | null;
}

export interface DxyForecast {
  horizon_days: number;
  predicted_value: number;
  lower_bound: number;
  upper_bound: number;
  trend: "up" | "down" | "flat";
  r_squared: number;
  generated_at: string;
}

export interface DxySnapshot {
  latest_value: number | null;
  latest_date: string | null;
  forecast: DxyForecast | null;
}

export interface NewsHeadline {
  id: string;
  published_at: string;
  source: string;
  headline: string;
  summary: string | null;
  sentiment: "positive" | "neutral" | "negative";
  impact_level: "low" | "medium" | "high";
  related_asset: string;
  url: string | null;
}

export interface CalendarEvent {
  release_name: string;
  scheduled_at: string;
  importance: "high" | "medium";
}

export interface IctSignal {
  id: string;
  asset: string;
  timeframe: string;
  signal_type: "swing_high" | "swing_low" | "fair_value_gap" | "liquidity_sweep" | "market_structure_shift" | "order_block";
  direction: "bullish" | "bearish";
  price_level: number | null;
  detected_at: string;
  notes: string | null;
  confidence: number | null;
  institutional_bias: "BUY" | "SELL" | "WAIT" | null;
  market_trend: "BULLISH" | "BEARISH" | "RANGE" | null;
  trend_strength: number | null;
  premium_discount: "PREMIUM" | "DISCOUNT" | "EQUILIBRIUM" | null;
  buy_ote_low: number | null;
  buy_ote_high: number | null;
  sell_ote_low: number | null;
  sell_ote_high: number | null;
}

export interface AiDecision {
  asset: string;
  decision: "long" | "short" | "neutral";
  confidence: number;
  rationale: string;
  contributing_factors: Record<string, unknown>;
  created_at: string;
}

export interface HistoricalOutcome {
  id: string;
  asset: string;
  outcome: "win" | "loss" | "neutral";
  pnl_pct: number | null;
  evaluated_at: string;
}

export interface WinRateSummary {
  asset: string;
  total: number;
  wins: number;
  losses: number;
  neutral: number;
  win_rate: number | null;
}

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  body: string | null;
  read: boolean;
  created_at: string;
}

export interface PerformanceSummary {
  asset: string;
  win_rate: number | null;
  avg_pnl_pct: number | null;
  total_decisions: number;
  last_updated: string | null;
}

// --- Top-Down Analysis --------------------------------------------------

export interface MacroRegime {
  as_of: string;
  inflation_regime: "inflationary" | "disinflationary" | "deflationary" | null;
  cpi_yoy_pct: number | null;
  rate_regime: "higher_rates_expected" | "lower_rates_expected" | "unexpected_change" | "steady" | null;
  commodity_trend: "up" | "down" | "flat" | null;
  usdx_trend: "up" | "down" | "flat" | null;
}

export interface SeasonalityMonth {
  asset: string;
  month: number;
  avg_return_pct: number;
  win_rate_pct: number;
  years_sampled: number;
}

export interface BigPictureSummary {
  asset: string;
  macro_regime: MacroRegime | null;
  current_month_seasonality: SeasonalityMonth | null;
  seasonality_by_month: SeasonalityMonth[];
}

export interface TopDownBiasEntry {
  timeframe: string;
  bias: "bullish" | "bearish" | "neutral";
  notes: string;
  as_of: string;
}

export interface CotPositioning {
  report_date: string;
  net_noncommercial: number;
  net_noncommercial_pct: number | null;
  positioning: "net long" | "net short" | "flat";
}

export interface MarketSentiment {
  asset: string;
  news_sentiment_counts: { positive: number; neutral: number; negative: number };
  cot_positioning: CotPositioning | null;
}

export interface IntermediateSummary {
  asset: string;
  top_down_bias: Record<"1M" | "1W" | "1D", TopDownBiasEntry | null>;
  sentiment: MarketSentiment;
}

export interface CorrelationEntry {
  as_of: string;
  asset_a: string;
  asset_b: string;
  correlation: number;
  window_days: number;
}

export interface PriceLevel {
  high: number;
  low: number;
}

export interface TimeAndPrice {
  asset: string;
  price_levels: {
    previous_day: PriceLevel;
    previous_week: PriceLevel | null;
    previous_month: PriceLevel | null;
  } | null;
  day_of_week_tendency: { day: string; avg_return_pct: number; samples: number }[] | null;
}

export interface IpdaRange {
  asset: string;
  range_days: number;
  range_high: number;
  range_low: number;
  current_close: number;
  position: "at_high" | "at_low" | "inside" | "beyond_high" | "beyond_low";
  as_of: string;
}

export interface ShortTermSummary {
  asset: string;
  correlations: CorrelationEntry[];
  time_and_price: TimeAndPrice;
  ipda_ranges: IpdaRange[];
}

export interface OpenFloatLevel {
  label?: string;
  price: number;
  date: string;
  distance: number;
  pct_distance: number;
  importance?: string;
  liquidity_status?: string;
  sweep_status: "UNTOUCHED" | "SWEPT";
}

export interface QuarterlyShift {
  direction: "bullish" | "bearish" | "neutral";
  notes: string;
  current_quarter_high: number | null;
  current_quarter_low: number | null;
  price_position: string;
}

export interface OpenFloatAnalysis {
  asset: string;
  current_price: number;
  as_of: string;
  quarterly_shift: QuarterlyShift;
  buy_side: {
    last_bearish_shift: OpenFloatLevel | "Data unavailable";
    short_term_highs: OpenFloatLevel[];
    three_month_high: OpenFloatLevel | "Data unavailable";
    six_month_high: OpenFloatLevel | "Data unavailable";
    twelve_month_high: OpenFloatLevel | "Data unavailable";
  };
  sell_side: {
    last_bullish_shift: OpenFloatLevel | "Data unavailable";
    short_term_lows: OpenFloatLevel[];
    three_month_low: OpenFloatLevel | "Data unavailable";
    six_month_low: OpenFloatLevel | "Data unavailable";
    twelve_month_low: OpenFloatLevel | "Data unavailable";
  };
  nearest_buy_side: OpenFloatLevel | null;
  nearest_sell_side: OpenFloatLevel | null;
  dominant_liquidity_side: "BUY_SIDE" | "SELL_SIDE" | "BALANCED";
  buy_side_score: number;
  sell_side_score: number;
  interpretation: string;
  error?: string;
}
