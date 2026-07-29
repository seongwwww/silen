alter table public.users
  add column diary_hour smallint not null default 21
    check (diary_hour between 0 and 23);

comment on column public.users.diary_hour is
  '사용자 로컬 시간대 기준 자동 일기 생성 시각(0~23시)';
