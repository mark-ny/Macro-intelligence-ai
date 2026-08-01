-- Macro Intelligence AI — initial schema
-- Run via the Supabase SQL editor, or `supabase db push` with the CLI.
-- Market/macro data tables are public-read (it's not sensitive personal
-- data) but write-restricted to the service role, which the backend uses
-- and which bypasses RLS by design — the policies below are what protect
-- these tables from anon/authenticated writes.

-- ============================================================
-- 1. Treasury Intelligence Engine (implemented this milestone)
-- ============================================================
create table if not exists treasury_yields (
  series     text not null,           -- '3M','2Y','5Y','10Y','30Y','10Y2Y','10Y3M'
  date       date not null,
  value      numeric not null,
  updated_at timestamptz not null default now(),
  primary key (series, date)
);

alter table treasury_yields enable row level security;

create policy "treasury_yields readable by anyone"
  on treasury_yields for select
  using (true);

-- No insert/update/delete policy for anon/authenticated: only the
-- service-role key (used exclusively by the backend) can write here.

-- ============================================================
-- 2. Interest Rate Intelligence Engine (scaffolded)
-- ============================================================
create table if not exists interest_rates (
  series     text not null,           -- e.g. 'FEDFUNDS', 'SOFR'
  date       date not null,
  value      numeric not null,
  updated_at timestamptz not null default now(),
  primary key (series, date)
);
alter table interest_rates enable row level security;
create policy "interest_rates readable by anyone" on interest_rates for select using (true);

-- ============================================================
-- 3. Economic News Intelligence Engine (scaffolded)
-- ============================================================
create table if not exists economic_news (
  id             uuid primary key default gen_random_uuid(),
  published_at   timestamptz not null,
  source         text not null,
  headline       text not null,
  summary        text,
  sentiment      text,               -- 'positive' | 'neutral' | 'negative'
  impact_level   text,               -- 'low' | 'medium' | 'high'
  related_asset  text,               -- 'XAUUSD' | 'NQ' | 'both'
  url            text,
  created_at     timestamptz not null default now()
);
alter table economic_news enable row level security;
create policy "economic_news readable by anyone" on economic_news for select using (true);

-- ============================================================
-- 4. DXY Forecast Engine (scaffolded)
-- ============================================================
create table if not exists dxy_data (
  date       date primary key,
  value      numeric not null,
  source     text not null default 'FRED_DTWEXBGS',
  updated_at timestamptz not null default now()
);
alter table dxy_data enable row level security;
create policy "dxy_data readable by anyone" on dxy_data for select using (true);

create table if not exists dxy_forecasts (
  id            uuid primary key default gen_random_uuid(),
  forecast_date date not null,
  horizon_days  int not null,
  predicted     numeric not null,
  confidence    numeric,
  model_version text,
  created_at    timestamptz not null default now()
);
alter table dxy_forecasts enable row level security;
create policy "dxy_forecasts readable by anyone" on dxy_forecasts for select using (true);

-- ============================================================
-- 5. ICT Analysis Engine (scaffolded)
-- ============================================================
create table if not exists ict_signals (
  id           uuid primary key default gen_random_uuid(),
  asset        text not null,        -- 'XAUUSD' | 'NQ'
  timeframe    text not null,        -- '1H','4H','1D', ...
  signal_type  text not null,        -- 'order_block' | 'fvg' | 'liquidity_grab' | 'mss'
  direction    text not null,        -- 'bullish' | 'bearish'
  price_level  numeric,
  detected_at  timestamptz not null default now(),
  notes        text
);
alter table ict_signals enable row level security;
create policy "ict_signals readable by anyone" on ict_signals for select using (true);

-- ============================================================
-- 6. AI Decision Engine (scaffolded)
-- ============================================================
create table if not exists ai_decisions (
  id                   uuid primary key default gen_random_uuid(),
  asset                text not null,     -- 'XAUUSD' | 'NQ'
  decision             text not null,     -- 'long' | 'short' | 'neutral'
  confidence           numeric,
  rationale            text,
  contributing_factors jsonb,
  created_at           timestamptz not null default now(),
  outcome_evaluated     boolean not null default false
);
alter table ai_decisions enable row level security;
create policy "ai_decisions readable by anyone" on ai_decisions for select using (true);

-- ============================================================
-- 7. Historical Learning Engine (scaffolded)
-- ============================================================
create table if not exists historical_outcomes (
  id           uuid primary key default gen_random_uuid(),
  decision_id  uuid references ai_decisions(id) on delete cascade,
  asset        text not null,
  outcome      text not null,      -- 'win' | 'loss' | 'neutral'
  pnl_pct      numeric,
  evaluated_at timestamptz not null default now()
);
alter table historical_outcomes enable row level security;
create policy "historical_outcomes readable by anyone" on historical_outcomes for select using (true);

-- ============================================================
-- 11. Notifications (per-user — scaffolded)
-- ============================================================
create table if not exists notifications (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  type       text not null,
  title      text not null,
  body       text,
  read       boolean not null default false,
  created_at timestamptz not null default now()
);
alter table notifications enable row level security;

create policy "users read their own notifications"
  on notifications for select
  using (auth.uid() = user_id);

create policy "users update their own notifications"
  on notifications for update
  using (auth.uid() = user_id);

-- ============================================================
-- 10. Settings (per-user — scaffolded)
-- ============================================================
create table if not exists user_settings (
  user_id            uuid primary key references auth.users(id) on delete cascade,
  risk_tolerance     text default 'moderate',   -- 'conservative' | 'moderate' | 'aggressive'
  notification_prefs jsonb not null default '{}'::jsonb,
  watchlist          jsonb not null default '["XAUUSD", "NQ"]'::jsonb,
  theme              text not null default 'dark',
  updated_at         timestamptz not null default now()
);
alter table user_settings enable row level security;

create policy "users manage their own settings"
  on user_settings for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ============================================================
-- 12. Performance Analytics (scaffolded)
-- ============================================================
create table if not exists performance_metrics (
  id          uuid primary key default gen_random_uuid(),
  date        date not null,
  asset       text not null,
  metric_type text not null,   -- 'win_rate' | 'drawdown' | 'model_accuracy'
  value       numeric not null,
  created_at  timestamptz not null default now()
);
alter table performance_metrics enable row level security;
create policy "performance_metrics readable by anyone" on performance_metrics for select using (true);

-- ============================================================
-- Helpful indexes
-- ============================================================
create index if not exists idx_treasury_yields_date on treasury_yields (date desc);
create index if not exists idx_economic_news_published_at on economic_news (published_at desc);
create index if not exists idx_ict_signals_asset_detected on ict_signals (asset, detected_at desc);
create index if not exists idx_ai_decisions_asset_created on ai_decisions (asset, created_at desc);
create index if not exists idx_notifications_user_unread on notifications (user_id) where not read;
