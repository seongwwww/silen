-- 추출 링크는 met/visited/did로 단정하지 않는다 — "메모가 이 엔티티를
-- 언급했다"가 정직하다(과잉해석 금지). mentioned를 허용값에 추가한다.
alter table public.memory_entities
  drop constraint memory_entities_relation_type_check;
alter table public.memory_entities
  add constraint memory_entities_relation_type_check
  check (relation_type in ('met', 'visited', 'did', 'mentioned'));

-- 고아 entity 즉시 삭제. 링크가 사라진 entity가 다른 memory_entities·
-- relations 어디서도 참조되지 않으면 지운다. 타인 이름이 "지웠는데 남는"
-- 창을 원천 차단한다(privacy.md 삭제 완전성). 메모 삭제·계정 삭제·미래
-- 경로 모두에 균일하게 걸린다.
create function public.delete_orphan_entity() returns trigger
  language plpgsql
  security definer
  set search_path = ''
as $$
begin
  if not exists (
        select 1 from public.memory_entities where entity_id = old.entity_id
      )
     and not exists (
        select 1 from public.relations
         where source_entity_id = old.entity_id or target_entity_id = old.entity_id
      )
  then
    delete from public.entities where id = old.entity_id;
  end if;
  return old;
end;
$$;

create trigger on_memory_entity_deleted
  after delete on public.memory_entities
  for each row execute function public.delete_orphan_entity();
