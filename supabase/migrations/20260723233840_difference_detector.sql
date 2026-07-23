-- 엔티티 기반 차이(first_occurrence·freq_shift)를 근거 엔티티에 연결한다.
-- ON DELETE SET NULL: 엔티티가 삭제돼도 difference를 하드 삭제하지 않는다.
-- 사용자의 status(confirmed/dismissed) 판단을 보존하고, 근거 소실 시 무효화는
-- stale 메커니즘(삭제 원장 기능)의 몫이다(ADR-0002).
alter table public.differences
  add column entity_id uuid references public.entities(id) on delete set null;

-- 멱등 자연키: 같은 (사용자, 날짜, 엔티티, 방법) 차이를 재실행이 중복 생성하지 않는다.
-- entity_id 없는 미래 method(zscore/pattern)는 제약 대상 아님(부분 인덱스).
create unique index differences_entity_natural_key
  on public.differences (user_id, date, entity_id, detection_method)
  where entity_id is not null;
