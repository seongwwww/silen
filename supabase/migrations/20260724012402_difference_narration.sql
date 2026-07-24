-- 서술은 AI 생성물이다. 탐지(differences, 통계)와 행으로 분리해
-- detector 변경과 프롬프트 변경을 섞지 않는다(git.md). difference당 1건.
create table public.difference_narrations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  -- 하나의 차이당 서술 하나. 재서술은 명시적 upsert만.
  difference_id uuid not null unique references public.differences(id) on delete cascade,
  headline text not null,
  body text not null,
  evidence_text text not null,
  model text not null,
  created_at timestamptz not null default now()
);
create index difference_narrations_user_idx on public.difference_narrations (user_id);

alter table public.difference_narrations enable row level security;
-- 쓰기는 워커(service_role/postgres)만. select-only 정책으로 RLS도 2차 차단(deletions 패턴).
create policy "본인 데이터만" on public.difference_narrations
  for select to authenticated
  using (user_id = (select auth.uid()));

-- 신규 테이블이라 과거 일괄 grant에 안 잡힌다. 여기서 명시한다.
-- 서술은 사용자에게 읽기 전용 — 쓰기는 워커(service_role/postgres)만.
-- 사용자가 서술 텍스트를 위조하면 'AI 생성물'의 진실성이 무너진다(deletions 패턴).
revoke all on public.difference_narrations from anon;
grant select on public.difference_narrations to authenticated;
grant all on public.difference_narrations to service_role;
