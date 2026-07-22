-- 원본 기록 계열. AI 생성물(differences/diaries)과 분리 저장한다.
-- auth.users FK는 Auth 도입 시 별도 마이그레이션으로 추가한다.

create table public.users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  display_name text,
  style_profile jsonb not null default '{}'::jsonb,
  diary_time time not null default '22:00',
  -- backend.md: "하루"는 사용자 로컬 자정 기준. lib/time이 이 값을 받는다.
  timezone text not null default 'Asia/Seoul',
  created_at timestamptz not null default now()
);

create table public.memories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  captured_at timestamptz not null default now(),
  occurred_at timestamptz,
  raw_text text,
  source_type text not null check (source_type in ('manual','share','sensor','ocr','stt')),
  memory_type text not null check (memory_type in ('moment','thought','event')),
  metadata jsonb not null default '{}'::jsonb,
  -- 잠긴 기억은 검색·일기·회고·탐지에서 제외된다(privacy.md).
  is_locked boolean not null default false,
  -- 휴지통이 아니라 삭제 파이프라인 진행 중 tombstone이다(ADR-0002).
  deleted_at timestamptz
);

create table public.assets (
  id uuid primary key default gen_random_uuid(),
  memory_id uuid not null references public.memories(id) on delete cascade,
  asset_type text not null check (asset_type in ('photo','voice','link')),
  file_url text not null,
  extracted_text text,
  transcription text,
  mime_type text
);

create table public.emotions (
  id uuid primary key default gen_random_uuid(),
  memory_id uuid not null references public.memories(id) on delete cascade,
  valence real check (valence between -1 and 1),
  tags text[] not null default '{}',
  confidence real,
  confirmed_by_user boolean not null default false
);

-- database.md: 자주 조회하는 (user_id, 날짜) 복합 인덱스
create index memories_user_captured_idx on public.memories (user_id, captured_at desc);
create index memories_user_active_idx on public.memories (user_id) where deleted_at is null;
create index assets_memory_idx on public.assets (memory_id);
create index emotions_memory_idx on public.emotions (memory_id);

-- 정책 없는 RLS의 기본값은 전면 차단이다. 정책은 Auth 도입 시 작성한다.
alter table public.users enable row level security;
alter table public.memories enable row level security;
alter table public.assets enable row level security;
alter table public.emotions enable row level security;
