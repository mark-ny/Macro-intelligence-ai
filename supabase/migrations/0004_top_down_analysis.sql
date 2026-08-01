-- Macro Intelligence AI — migration 4
-- Adds the "Top-Down Analysis" feature: Big Picture, Intermediate, and
-- Short-Term perspectives, per the classic ICT top-down framework.

-- ============================================================
-- Shared OHLC store. ict_service and history_service previously fetched
-- Twelve Data live on every call; this migration also refactors them to
-- read from here instead, so Top-Down/Correlation/Seasonality/IPDA reuse
-- the exact same bars rather than each hitting Twelve Data separately.
-- ============================================================
create table if not exists market_prices (
  asset text not null,   -- 'XAUUSD' | 'NQ'
  date  date not null,
  open  numeric not null,
  high  numeric not null,
  low   numeric not null,
  close numeric not null,
  primary key (asset, date)
);
alter table market_prices enable row level security;
create policy "market_prices readable by anyone" on market_prices for select using (true);
create index if not exists idx_market_prices_asset_date on market_prices (asset, date desc);

-- ============================================================
-- Big Picture: CPI level (for a YoY inflation trend) and a free broad
-- commodity index (IMF's Global Price Index of All Commodities via FRED
-- — a legitimate free proxy for "the CRB index," same spirit as DXY
-- being proxied by FRED's trade-weighted dollar index).
-- ============================================================
create table if not exists cpi_data (
  date  date primary key,
  value numeric not null
);
alter table cpi_data enable row level security;
create policy "cpi_data readable by anyone" on cpi_data for select using (true);

create table if not exists commodity_index (
  date   date primary key,
  value  numeric not null,
  source text not null default 'FRED_PALLFNFINDEXM'
);
alter table commodity_index enable row level security;
create policy "commodity_index readable by anyone" on commodity_index for select using (true);

create table if not exists macro_regime (
  as_of            date primary key,
  inflation_regime text,     -- 'inflationary' | 'disinflationary' | 'deflationary'
  cpi_yoy_pct      numeric,
  rate_regime      text,     -- 'higher_rates_expected' | 'lower_rates_expected' | 'unexpected_change' | 'steady'
  commodity_trend  text,     -- 'up' | 'down' | 'flat'
  usdx_trend       text,     -- reuses the DXY engine's trend classification
  created_at       timestamptz not null default now()
);
alter table macro_regime enable row level security;
create policy "macro_regime readable by anyone" on macro_regime for select using (true);

create table if not exists seasonality_stats (
  asset          text not null,
  month          int not null,   -- 1-12
  avg_return_pct numeric,
  win_rate_pct   numeric,
  years_sampled  int,
  updated_at     timestamptz not null default now(),
  primary key (asset, month)
);
alter table seasonality_stats enable row level security;
create policy "seasonality_stats readable by anyone" on seasonality_stats for select using (true);

-- ============================================================
-- Intermediate: multi-timeframe structural bias, and CFTC COT positioning
-- ============================================================
create table if not exists topdown_bias (
  asset     text not null,
  timeframe text not null,   -- '1M' | '1W' | '1D'
  bias      text not null,   -- 'bullish' | 'bearish' | 'neutral'
  as_of     date not null,
  notes     text,
  primary key (asset, timeframe, as_of)
);
alter table topdown_bias enable row level security;
create policy "topdown_bias readable by anyone" on topdown_bias for select using (true);

create table if not exists cot_positioning (
  report_date         date not null,
  asset               text not null,  -- our mapped 'XAUUSD' | 'NQ'
  market_name         text,           -- the raw CFTC market_and_exchange_names matched
  noncommercial_long  bigint,
  noncommercial_short bigint,
  commercial_long     bigint,
  commercial_short    bigint,
  created_at          timestamptz not null default now(),
  primary key (report_date, asset)
);
alter table cot_positioning enable row level security;
create policy "cot_positioning readable by anyone" on cot_positioning for select using (true);

-- ============================================================
-- Short-Term: correlations and IPDA range levels
-- ============================================================
create table if not exists correlation_matrix (
  as_of       date not null,
  asset_a     text not null,
  asset_b     text not null,
  correlation numeric not null,
  window_days int not null,
  primary key (as_of, asset_a, asset_b, window_days)
);
alter table correlation_matrix enable row level security;
create policy "correlation_matrix readable by anyone" on correlation_matrix for select using (true);

create table if not exists ipda_ranges (
  asset         text not null,
  range_days    int not null,   -- 20 | 40 | 60
  range_high    numeric,
  range_low     numeric,
  current_close numeric,
  position      text,           -- 'at_high' | 'at_low' | 'inside' | 'beyond_high' | 'beyond_low'
  as_of         date not null,
  primary key (asset, range_days, as_of)
);
alter table ipda_ranges enable row level security;
create policy "ipda_ranges readable by anyone" on ipda_ranges for select using (true);
