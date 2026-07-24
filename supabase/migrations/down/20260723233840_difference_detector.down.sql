drop index if exists public.differences_entity_natural_key;
alter table public.differences drop column if exists entity_id;
