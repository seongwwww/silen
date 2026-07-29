drop index if exists public.memories_user_effective_idx;
alter table public.memories drop column if exists effective_at;
