-- 도메인 시각을 DB가 강제한다.
--
-- captured_at은 앱에 기록한 시각(감사·정렬), occurred_at은 실제 일이 일어난
-- 시각이다. 차이 탐지·감정·일기 날짜·주간 리포트·활동일은 모두 후자를 따라야
-- 하는데, 호출부마다 coalesce를 손으로 넣으면 한 곳만 빠져도 조용히 틀린다.
-- 실제로 occurred_at이 탐지에 전혀 반영되지 않는 결함이 그렇게 생겼다.
alter table public.memories
  add column effective_at timestamptz
  generated always as (coalesce(occurred_at, captured_at)) stored;

-- 탐지·일기·주간은 (user_id, effective_at) 범위로 훑는다.
create index memories_user_effective_idx
  on public.memories (user_id, effective_at desc);
