-- 톤 주문과 재생성 요청. 둘 다 다음 생성이 1회 소비하고 비운다.
-- 자동 재생성이 아니라 사용자가 명시적으로 누른 요청이다(기획서 §6).
alter table public.diaries
  add column tone_instruction text,
  add column regenerate_requested_at timestamptz;
