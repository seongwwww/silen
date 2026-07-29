-- 사진을 텍스트 질문으로 찾을 수 있게 한다.
--
-- gemini-embedding-001은 텍스트 전용이라(실측: "Non-text part found") 사진을
-- 같은 벡터로 넣을 수 없다. multimodalembedding@001은 텍스트와 이미지를 같은
-- 1408차원 공간에 넣어 교차 검색이 된다(실측: "노란 원" 질문이 해 그림을
-- 6.7배 높게 잡음). 차원이 다르므로 테이블을 나눈다 - 한 인덱스에 서로 다른
-- 모델의 벡터를 섞지 않는다(ADR-0004).
create table public.photo_embeddings (
  asset_id uuid primary key references public.assets(id) on delete cascade,
  memory_id uuid not null,
  user_id uuid not null,
  embedding vector(1408) not null,
  model text not null,
  -- 부모 메모의 잠금·삭제를 반영하는 비정규화 플래그(memory_embeddings와 동일).
  -- 성능용이며 프라이버시 경계로 믿지 않는다 - 질의가 부모를 다시 확인한다.
  is_searchable boolean not null default true,
  created_at timestamptz not null default now(),
  foreign key (memory_id, user_id)
    references public.memories(id, user_id) on delete cascade
);

-- 1408차원은 HNSW 상한 2000 아래다(실측 확인).
create index photo_embeddings_vector_idx
  on public.photo_embeddings using hnsw (embedding vector_cosine_ops);
create index photo_embeddings_user_idx
  on public.photo_embeddings (user_id) where is_searchable;

alter table public.photo_embeddings enable row level security;

create policy "본인 사진 임베딩만 조회"
  on public.photo_embeddings
  for select to authenticated
  using (
    exists (
      select 1 from public.memories m
       where m.id = photo_embeddings.memory_id
         and m.user_id = (select auth.uid())
    )
  );

revoke all on public.photo_embeddings from anon;
grant select on public.photo_embeddings to authenticated;
grant all on public.photo_embeddings to service_role;
