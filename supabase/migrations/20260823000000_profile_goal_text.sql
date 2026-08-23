-- The free-text goal from the conversational intake ("Your Goal"), persisted
-- so the grounded Q&A assistant can reference what the learner actually wrote.
-- Nullable: manual assessment submissions have no goal and older rows predate it.
alter table public.profiles
  add column if not exists goal_text text;
