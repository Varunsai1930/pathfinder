-- Upgrade the earlier task scaffold to the persisted milestone-task contract.
alter table public.tasks enable row level security;

alter table public.tasks
  add column if not exists task_label text,
  add column if not exists completed boolean not null default false,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

update public.tasks
set task_label = coalesce(task_label, task_id),
    completed = coalesce(completed, is_complete, false)
where task_label is null or completed is null;

alter table public.tasks
  alter column task_label set not null;

alter table public.tasks
  drop constraint if exists tasks_roadmap_id_task_id_key,
  drop column if exists task_id,
  drop column if exists is_complete;

alter table public.tasks
  drop constraint if exists tasks_roadmap_id_milestone_id_key,
  add constraint tasks_roadmap_id_milestone_id_key unique (roadmap_id, milestone_id);

drop policy if exists "Users manage their own tasks" on public.tasks;
create policy "Users manage their own tasks"
  on public.tasks for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
