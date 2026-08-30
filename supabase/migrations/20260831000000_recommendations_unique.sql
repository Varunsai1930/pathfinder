-- Recommendations are the persisted match cache: one row per (user, role).
-- A unique index lets POST /match persist with a single PostgREST upsert
-- (Prefer: resolution=merge-duplicates) instead of delete-then-insert.

-- Remove any historical duplicates before the index can be created
-- (keeps the newest row per user/role; safe to re-run).
delete from public.recommendations a
  using public.recommendations b
  where a.user_id = b.user_id
    and a.role_id = b.role_id
    and a.created_at < b.created_at;

create unique index if not exists recommendations_user_role_key
  on public.recommendations (user_id, role_id);
