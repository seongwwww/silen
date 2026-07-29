-- 재생성 요청이 왜 생겼는지 구분한다.
--
-- 사용자가 화면에서 누른 것과, 과거 날짜 기록이 늦게 들어와 그날 일기가
-- 낡아진 것은 화면에서 다르게 보여야 한다. 후자는 "늦게 추가된 기록이 있어요"다.
-- 요청이 소비되면 함께 비운다.
alter table public.diaries
  add column regenerate_reason text
    check (regenerate_reason in ('user', 'late_record'));
