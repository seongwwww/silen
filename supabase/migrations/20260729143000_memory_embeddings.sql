-- P3 회고: 메모 임베딩과 기존 pgmq를 이용한 일시적 질문/응답 전달.
-- 모델·차원·거리 결정: ADR-0004.

alter table public.memories
  add constraint memories_id_user_unique unique (id, user_id);

create table public.memory_embeddings (
  memory_id uuid primary key,
  user_id uuid not null,
  embedding vector(768) not null,
  model text not null
    check (model = 'gemini-embedding-001'),
  is_searchable boolean not null default true,
  created_at timestamptz not null default now(),
  constraint memory_embeddings_memory_owner_fk
    foreign key (memory_id, user_id)
    references public.memories (id, user_id)
    on delete cascade
);

create index memory_embeddings_user_id_idx
  on public.memory_embeddings (user_id);

create index memory_embeddings_hnsw_cosine_idx
  on public.memory_embeddings
  using hnsw (embedding vector_cosine_ops)
  where is_searchable = true;

alter table public.memory_embeddings enable row level security;

create policy "본인 활성 메모 임베딩만 조회"
  on public.memory_embeddings
  for select to authenticated
  using (
    user_id = (select auth.uid())
    and is_searchable = true
    and exists (
      select 1
        from public.memories m
       where m.id = memory_embeddings.memory_id
         and m.user_id = memory_embeddings.user_id
         and m.user_id = (select auth.uid())
         and m.is_locked = false
         and m.deleted_at is null
    )
  );

revoke all on public.memory_embeddings from anon;
grant select on public.memory_embeddings to authenticated;
grant all on public.memory_embeddings to service_role;

create function public.sync_memory_embedding_searchability()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.memory_embeddings
     set is_searchable = new.deleted_at is null and new.is_locked = false
   where memory_id = new.id
     and user_id = new.user_id;

  if (old.is_locked = true or old.deleted_at is not null)
     and new.is_locked = false
     and new.deleted_at is null
     and new.raw_text is not null
     and btrim(new.raw_text) <> ''
     and not exists (
       select 1
         from public.memory_embeddings me
        where me.memory_id = new.id
          and me.user_id = new.user_id
     )
  then
    perform pgmq.send(
      'memory_jobs',
      jsonb_build_object(
        'memory_id', new.id,
        'user_id', new.user_id
      )
    );
  end if;

  return new;
end;
$$;

create trigger memories_sync_embedding_searchability
after update of is_locked, deleted_at on public.memories
for each row execute function public.sync_memory_embedding_searchability();

create function public.request_recall(
  target_request_id uuid,
  question text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
  normalized_question text := btrim(question);
begin
  if caller_id is null then
    raise exception using errcode = '42501', message = 'authentication_required';
  end if;
  if normalized_question is null
     or char_length(normalized_question) = 0
     or char_length(normalized_question) > 100
  then
    raise exception using errcode = '22023', message = 'invalid_question';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(target_request_id::text, 0));

  if not exists (
    select 1
      from pgmq.q_memory_jobs q
     where q.message->>'request_id' = target_request_id::text
       and q.message->>'user_id' = caller_id::text
  ) and not exists (
    select 1
      from pgmq.a_memory_jobs a
     where a.message->>'request_id' = target_request_id::text
       and a.message->>'user_id' = caller_id::text
  )
  then
    perform pgmq.send(
      'memory_jobs',
      jsonb_build_object(
        'job_type', 'recall',
        'request_id', target_request_id,
        'user_id', caller_id,
        'query', normalized_question,
        'status', 'queued',
        'expires_at', now() + interval '15 minutes'
      )
    );
  end if;

  return target_request_id;
end;
$$;

create function public.poll_recall(target_request_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
  queue_message_id bigint;
  payload jsonb;
  request_status text;
  result jsonb;
begin
  if caller_id is null then
    raise exception using errcode = '42501', message = 'authentication_required';
  end if;

  select q.msg_id, q.message
    into queue_message_id, payload
    from pgmq.q_memory_jobs q
   where q.message->>'request_id' = target_request_id::text
     and q.message->>'user_id' = caller_id::text
     and q.message->>'job_type' in ('recall', 'recall_result')
   for update;

  if queue_message_id is null then
    return jsonb_build_object('status', 'missing');
  end if;

  request_status := payload->>'status';
  if request_status = 'done' then
    result := jsonb_build_object(
      'status', 'done',
      'response', payload->'response'
    );
    perform pgmq.delete('memory_jobs', queue_message_id);
    return result;
  end if;
  if request_status = 'error' then
    result := jsonb_build_object(
      'status', 'error',
      'errorCode', coalesce(payload->>'error_code', 'recall_failed')
    );
    perform pgmq.delete('memory_jobs', queue_message_id);
    return result;
  end if;
  if request_status not in ('queued', 'processing') then
    return jsonb_build_object('status', 'missing');
  end if;
  return jsonb_build_object('status', request_status);
end;
$$;

revoke all on function public.request_recall(uuid, text) from public;
revoke all on function public.poll_recall(uuid) from public;
grant execute on function public.request_recall(uuid, text) to authenticated;
grant execute on function public.poll_recall(uuid) to authenticated;

