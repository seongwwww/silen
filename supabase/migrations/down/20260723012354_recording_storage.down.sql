drop policy if exists "본인 폴더만 삭제" on storage.objects;
drop policy if exists "본인 폴더만 업로드" on storage.objects;
drop policy if exists "본인 폴더만 조회" on storage.objects;
-- 버킷에 객체가 남아 있으면 실패한다(의도된 동작). 비운 뒤 지운다.
delete from storage.buckets where id = 'memories';
