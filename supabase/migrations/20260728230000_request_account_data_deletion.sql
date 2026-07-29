-- 인증 사용자가 본인 기록 전체 삭제 원장을 안전하게 요청한다.
-- target_id=user_id를 강제해 진행 중 요청의 부분 유니크 인덱스가 이중 클릭을 막는다.

create function public.request_account_data_deletion()
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
  deletion_id uuid;
begin
  if caller_id is null then
    raise exception using errcode = '42501', message = 'authentication_required';
  end if;

  insert into public.deletions (
    user_id,
    trigger,
    target_type,
    target_id,
    status
  )
  values (
    caller_id,
    'account',
    'user',
    caller_id,
    'running'
  )
  on conflict (target_type, target_id) where status <> 'completed'
  do update set user_id = excluded.user_id
  returning id into deletion_id;

  return deletion_id;
end;
$$;

revoke all on function public.request_account_data_deletion() from public;
grant execute on function public.request_account_data_deletion() to authenticated;
