-- 엔티티·관계·신호·평소모델(baseline). 탐지 파이프라인의 입력이다.

create table public.entities (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  entity_type text not null check (entity_type in ('person','place','activity','thing')),
  name text not null,
  -- 보수적 자동 병합 키. 같은 사용자 안에서만 유일하다.
  normalized_name text not null,
  unique (user_id, entity_type, normalized_name)
);

create table public.memory_entities (
  memory_id uuid not null references public.memories(id) on delete cascade,
  entity_id uuid not null references public.entities(id) on delete cascade,
  relation_type text not null check (relation_type in ('met','visited','did')),
  confidence real,
  confirmed_by_user boolean not null default false,
  primary key (memory_id, entity_id, relation_type)
);

create table public.relations (
  id uuid primary key default gen_random_uuid(),
  source_entity_id uuid not null references public.entities(id) on delete cascade,
  target_entity_id uuid not null references public.entities(id) on delete cascade,
  relation_type text not null,
  confidence real,
  -- 근거 메모가 사라지면 이 관계도 근거를 잃는다.
  source_memory_id uuid references public.memories(id) on delete cascade
);

create table public.signals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  signal_type text not null check (signal_type in ('steps','sleep','screen','checkin')),
  value double precision not null,
  observed_at timestamptz not null,
  source text not null check (source in ('sensor','derived'))
);

create table public.baselines (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  dimension text not null,
  stat jsonb not null default '{}'::jsonb,
  -- ERD의 window는 PostgreSQL 예약어(WINDOW 절)라 그대로 쓸 수 없다.
  window_spec text not null check (window_spec in ('7d','28d','dow')),
  updated_at timestamptz not null default now(),
  -- baseline은 캐시다. 같은 (사용자, 차원, 창)에 하나만 존재한다.
  unique (user_id, dimension, window_spec)
);

create index memory_entities_entity_idx on public.memory_entities (entity_id);
create index relations_source_memory_idx on public.relations (source_memory_id);
create index signals_user_observed_idx on public.signals (user_id, observed_at desc);

alter table public.entities enable row level security;
alter table public.memory_entities enable row level security;
alter table public.relations enable row level security;
alter table public.signals enable row level security;
alter table public.baselines enable row level security;
