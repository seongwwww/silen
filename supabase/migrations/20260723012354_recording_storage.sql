-- 사진 저장용 비공개 버킷과 접근 격리.
-- 테이블 RLS와 같은 원리를 Storage 객체에도 적용한다.

insert into storage.buckets (id, name, public)
values ('memories', 'memories', false)
on conflict (id) do nothing;

-- 최상위 폴더가 소유자 식별자다: {user_id}/{uuid}.{ext}
-- storage.foldername(name)[1] 이 그 폴더를 준다.

create policy "본인 폴더만 조회" on storage.objects
  for select to authenticated
  using (
    bucket_id = 'memories'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy "본인 폴더만 업로드" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'memories'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy "본인 폴더만 삭제" on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'memories'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );
