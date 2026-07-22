-- 삭제 단계 추적 원장. 부분 실패 시 steps_done부터 재개한다.

create table public.deletions (
  id uuid primary key default gen_random_uuid(),
  -- users FK를 걸지 않는다. 계정 삭제 시 users 행이 사라지면 CASCADE로
  -- ledger가 함께 없어져 삭제가 끝나기 전에 진행 상태를 잃는다.
  -- ledger는 삭제 대상보다 오래 살아야 한다(ADR-0002).
  user_id uuid not null,
  trigger text not null check (trigger in ('memory','consent_revoke','account')),
  target_type text not null,
  target_id uuid,
  -- 사용자 응답. NULL = 아직 안 물어봤거나 응답 대기.
  cascade_diaries boolean,
  status text not null default 'running'
    check (status in ('awaiting_user','running','completed','failed')),
  steps_done text[] not null default '{}',
  attempts int not null default 0,
  last_error text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

-- backend.md "자연키로 upsert"를 스키마로 강제한다.
-- 이게 없으면 삭제 버튼을 두 번 눌렀을 때 ledger가 복제되고
-- 같은 단계가 경쟁 실행된다.
create unique index deletions_active_target_idx
  on public.deletions (target_type, target_id)
  where status <> 'completed';

create index deletions_user_idx on public.deletions (user_id);
create index deletions_pending_idx on public.deletions (status)
  where status in ('awaiting_user','running','failed');

alter table public.deletions enable row level security;
