-- Complete the existing roadmap scaffold without changing the out-of-scope tasks table.
alter table public.roadmaps enable row level security;

alter table public.roadmaps
  add column if not exists updated_at timestamptz not null default now();

alter table public.roadmaps
  alter column generation_mode set default 'fallback';

alter table public.roadmaps
  alter column generation_mode set not null;

alter table public.roadmaps
  drop constraint if exists roadmaps_user_id_role_id_key;

alter table public.roadmaps
  add constraint roadmaps_user_id_role_id_key unique (user_id, role_id);

-- The initial scaffold allowed reads only. A user must also be able to create
-- and refresh their own roadmap, while RLS remains an independent boundary.
drop policy if exists "Users read their own roadmaps" on public.roadmaps;
drop policy if exists "Users manage their own roadmaps" on public.roadmaps;
create policy "Users manage their own roadmaps"
  on public.roadmaps for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
