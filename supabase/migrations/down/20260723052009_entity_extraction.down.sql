drop trigger if exists on_memory_entity_deleted on public.memory_entities;
drop function if exists public.delete_orphan_entity();
-- mentioned를 되돌리면 기존 데이터가 위반일 수 있어 실패할 수 있다(의도).
alter table public.memory_entities
  drop constraint memory_entities_relation_type_check;
alter table public.memory_entities
  add constraint memory_entities_relation_type_check
  check (relation_type in ('met', 'visited', 'did'));
