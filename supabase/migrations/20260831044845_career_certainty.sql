alter table public.profiles
  add column if not exists career_certainty text not null default 'exploring';
