-- Macro Intelligence AI — migration 2
-- Adds what the News and DXY modules need beyond the initial schema.

-- ============================================================
-- Economic calendar (News Intelligence Engine)
-- ============================================================
create table if not exists economic_calendar (
  id            uuid primary key default gen_random_uuid(),
  release_name  text not null,
  release_id    integer not null,
  scheduled_at  date not null,
  importance    text not null default 'medium',
  created_at    timestamptz not null default now(),
  unique (release_id, scheduled_at)
);
alter table economic_calendar enable row level security;
create policy "economic_calendar readable by anyone" on economic_calendar for select using (true);

create index if not exists idx_economic_calendar_scheduled_at on economic_calendar (scheduled_at);

-- ============================================================
-- economic_news needs a unique key on url so upsert(on_conflict="url")
-- can dedupe headlines seen from more than one search keyword.
-- ============================================================
create unique index if not exists economic_news_url_uidx
  on economic_news (url)
  where url is not null;

-- ============================================================
-- dxy_forecasts needs the confidence band + trend persisted so the API
-- can serve them back without recomputing the fit on every read.
-- ============================================================
alter table dxy_forecasts add column if not exists lower_bound numeric;
alter table dxy_forecasts add column if not exists upper_bound numeric;
alter table dxy_forecasts add column if not exists trend text;

-- ============================================================
-- ict_signals: the detectors re-scan the whole lookback window on every
-- refresh, so without a dedup key the same historical pattern would be
-- re-inserted every run. This lets the service upsert instead.
-- ============================================================
create unique index if not exists ict_signals_dedup_uidx
  on ict_signals (asset, timeframe, signal_type, direction, detected_at);
