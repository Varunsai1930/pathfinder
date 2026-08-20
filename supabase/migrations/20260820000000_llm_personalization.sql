-- Persist only validated display text alongside the deterministic roadmap.
-- The roadmap's immutable milestones and task state remain catalog-derived.
alter table public.roadmaps
  add column if not exists fit_explanation text not null default '';

alter table public.roadmaps
  add column if not exists adaptation_note text not null default '';
