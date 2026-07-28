-- 웹의 수동 일기 생성 요청을 durable 상태로 보존한다.
-- Next.js는 이 원장과 기존 pgmq 큐에만 쓰고, 실제 LLM 호출은 Python 워커가 맡는다.

create table public.diary_generation_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  date date not null,
  status text not null default 'queued'
    check (status in ('queued', 'processing', 'done', 'failed')),
  diary_id uuid references public.diaries(id) on delete set null,
  attempts integer not null default 0 check (attempts >= 0),
  error_code text,
  requested_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  unique (user_id, date)
);

create index diary_generation_requests_user_status_idx
  on public.diary_generation_requests (user_id, status, requested_at desc);

alter table public.diary_generation_requests enable row level security;

create policy "본인 일기 생성 요청만 조회"
  on public.diary_generation_requests
  for select to authenticated
  using (user_id = (select auth.uid()));

revoke all on public.diary_generation_requests from anon;
grant select on public.diary_generation_requests to authenticated;
grant all on public.diary_generation_requests to service_role;

create function public.request_diary_generation(target_date date)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
  caller_timezone text;
  request_id uuid;
  request_status text;
  existing_diary_id uuid;
  should_enqueue boolean := false;
begin
  if caller_id is null then
    raise exception using errcode = '42501', message = 'authentication_required';
  end if;

  select timezone
    into caller_timezone
    from public.users
   where id = caller_id;

  if caller_timezone is null then
    raise exception using errcode = 'P0002', message = 'user_profile_not_found';
  end if;

  if target_date <> (clock_timestamp() at time zone caller_timezone)::date then
    raise exception using errcode = '22023', message = 'target_must_be_local_today';
  end if;

  select id
    into existing_diary_id
    from public.diaries
   where user_id = caller_id
     and date = target_date;

  if existing_diary_id is null and not exists (
    select 1
      from public.memories
     where user_id = caller_id
       and deleted_at is null
       and is_locked = false
       and raw_text is not null
       and btrim(raw_text) <> ''
       and (captured_at at time zone caller_timezone)::date = target_date
  ) then
    raise exception using errcode = '22023', message = 'memory_required';
  end if;

  insert into public.diary_generation_requests (
    user_id,
    date,
    status,
    diary_id,
    completed_at
  )
  values (
    caller_id,
    target_date,
    case when existing_diary_id is null then 'queued' else 'done' end,
    existing_diary_id,
    case when existing_diary_id is null then null else now() end
  )
  on conflict (user_id, date) do nothing
  returning id, status into request_id, request_status;

  if request_id is not null then
    should_enqueue := request_status = 'queued';
  else
    select id, status
      into request_id, request_status
      from public.diary_generation_requests
     where user_id = caller_id
       and date = target_date
     for update;

    if existing_diary_id is not null and request_status <> 'done' then
      update public.diary_generation_requests
         set status = 'done',
             diary_id = existing_diary_id,
             error_code = null,
             completed_at = now()
       where id = request_id;
    elsif request_status = 'failed' then
      update public.diary_generation_requests
         set status = 'queued',
             error_code = null,
             requested_at = now(),
             started_at = null,
             completed_at = null
       where id = request_id;
      should_enqueue := true;
    end if;
  end if;

  if should_enqueue then
    perform pgmq.send(
      'memory_jobs',
      jsonb_build_object(
        'job_type', 'diary',
        'request_id', request_id,
        'user_id', caller_id,
        'date', target_date
      )
    );
  end if;

  return request_id;
end;
$$;

revoke all on function public.request_diary_generation(date) from public;
grant execute on function public.request_diary_generation(date) to authenticated;
