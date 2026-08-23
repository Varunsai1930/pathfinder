-- Optional learning-pattern telemetry for milestone tasks.
-- Nullable on purpose: completion without telemetry must stay valid.
alter table public.tasks
  add column if not exists time_spent_minutes integer,
  add column if not exists quiz_score integer;
