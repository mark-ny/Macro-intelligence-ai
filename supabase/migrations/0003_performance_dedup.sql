-- Macro Intelligence AI — migration 3
-- Lets performance_metrics be upserted per (date, asset, metric_type)
-- instead of accumulating duplicate rows every time the job reruns on
-- the same day.

create unique index if not exists performance_metrics_dedup_uidx
  on performance_metrics (date, asset, metric_type);
