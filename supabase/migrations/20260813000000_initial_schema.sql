-- Supabase Auth owns auth.users. Application data is always scoped to that user.
create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  interest_profile jsonb not null default '{}'::jsonb,
  skill_confidence jsonb not null default '{}'::jsonb,
  work_style_profile jsonb not null default '{}'::jsonb,
  hours_per_week smallint,
  target_timeline_weeks smallint,
  selected_role_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.recommendations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  role_id text not null,
  total_score numeric(5,2) not null check (total_score between 0 and 100),
  score_breakdown jsonb not null,
  created_at timestamptz not null default now()
);

create table public.roadmaps (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  role_id text not null,
  weekly_plan jsonb not null,
  generation_mode text not null check (generation_mode in ('llm', 'fallback')),
  created_at timestamptz not null default now()
);

create table public.tasks (
  id uuid primary key default gen_random_uuid(),
  roadmap_id uuid not null references public.roadmaps(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  milestone_id text not null,
  task_id text not null,
  is_complete boolean not null default false,
  completed_at timestamptz,
  unique (roadmap_id, task_id)
);

-- NOTE: enrichment_events is unused by the application — résumé/GitHub
-- enrichment was descoped. Kept for schema history; no code writes to it.
create table public.enrichment_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source_type text not null check (source_type in ('resume', 'github')),
  status text not null check (status in ('success', 'failure', 'approved')),
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.recommendations enable row level security;
alter table public.roadmaps enable row level security;
alter table public.tasks enable row level security;
alter table public.enrichment_events enable row level security;

create policy "Users manage their own profile" on public.profiles for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users read their own recommendations" on public.recommendations for select using (auth.uid() = user_id);
create policy "Users read their own roadmaps" on public.roadmaps for select using (auth.uid() = user_id);
create policy "Users manage their own tasks" on public.tasks for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users read their own enrichment events" on public.enrichment_events for select using (auth.uid() = user_id);
