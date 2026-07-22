-- AI 생성물과 근거 연결. ADR-0002의 핵심.
-- 근거는 배열이 아니라 조인 테이블로 둔다(다대다·삭제 역추적).

create table public.differences (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  date date not null,
  dimension text not null,
  -- 탐지 상세(통계값). 사람에게 직접 보이지 않는다.
  -- 근거가 훼손되면 파기한다(evidence_state='stale').
  description text,
  detection_method text not null
    check (detection_method in ('zscore','first_occurrence','freq_shift','pattern')),
  confidence real,
  status text not null default 'candidate'
    check (status in ('candidate','confirmed','dismissed')),
  category text not null
    check (category in ('오늘의다른점','성취','감정전환','패턴')),
  -- ADR-0002: 근거가 사라져도 삭제하지 않고 무효화한다.
  -- 사용자의 status 판단은 보존하되 이후 소비 경로에서 제외된다.
  evidence_state text not null default 'intact'
    check (evidence_state in ('intact','stale')),
  staled_at timestamptz
);

create table public.difference_evidence (
  difference_id uuid not null references public.differences(id) on delete cascade,
  memory_id uuid not null references public.memories(id) on delete cascade,
  primary key (difference_id, memory_id)
);

create table public.diaries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  date date not null,
  status text not null default 'draft' check (status in ('draft','edited','confirmed')),
  style_profile jsonb not null default '{}'::jsonb,
  generated_text text,
  edited_text text,
  -- backend.md: 일기는 하루 1건 보장. 재시도가 중복을 만들면 안 된다.
  unique (user_id, date)
);

create table public.diary_sources (
  diary_id uuid not null references public.diaries(id) on delete cascade,
  memory_id uuid not null references public.memories(id) on delete cascade,
  primary key (diary_id, memory_id)
);

create table public.diary_sections (
  id uuid primary key default gen_random_uuid(),
  diary_id uuid not null references public.diaries(id) on delete cascade,
  difference_id uuid references public.differences(id) on delete set null,
  section_type text not null
    check (section_type in ('오늘의한문장','본문','다른점','성취')),
  content text not null
);

create table public.weekly_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  week text not null,
  unique (user_id, week)
);

-- ADR-0002: highlights jsonb 스냅샷은 삭제 방어선 밖에 사본을 만든다.
-- 참조로 두면 소비 시점 evidence_state 필터가 그대로 적용된다.
create table public.weekly_report_highlights (
  report_id uuid not null references public.weekly_reports(id) on delete cascade,
  difference_id uuid not null references public.differences(id) on delete cascade,
  slot text not null check (slot in ('가장많이한것','처음한것','감정순간')),
  rank int not null,
  primary key (report_id, difference_id)
);

create table public.consents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  source text not null,
  scope text not null,
  granted_at timestamptz not null default now(),
  revoked_at timestamptz,
  unique (user_id, source)
);

-- 삭제 파이프라인의 핵심 질의: "이 메모가 어디에 근거로 쓰였나"
create index difference_evidence_memory_idx on public.difference_evidence (memory_id);
create index diary_sources_memory_idx on public.diary_sources (memory_id);
create index weekly_report_highlights_difference_idx
  on public.weekly_report_highlights (difference_id);
create index differences_user_date_idx on public.differences (user_id, date desc);
-- 소비 경로는 intact만 조회한다(ADR-0002 3중 방어의 2번).
create index differences_user_intact_idx
  on public.differences (user_id, date desc) where evidence_state = 'intact';
create index diary_sections_diary_idx on public.diary_sections (diary_id);

alter table public.differences enable row level security;
alter table public.difference_evidence enable row level security;
alter table public.diaries enable row level security;
alter table public.diary_sources enable row level security;
alter table public.diary_sections enable row level security;
alter table public.weekly_reports enable row level security;
alter table public.weekly_report_highlights enable row level security;
alter table public.consents enable row level security;
