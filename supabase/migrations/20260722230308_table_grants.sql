-- 역할별 테이블 권한. RLS는 어느 '행'이 보이는지 정하지만, 그 전에
-- 테이블 수준 권한이 있어야 PostgREST 요청이 통과한다. postgres가 만든
-- 테이블은 Supabase가 CRUD를 자동 부여하지 않으므로 여기서 명시한다.

-- 미인증 요청(anon 키만 든 요청)은 데이터에 접근할 이유가 없다.
-- 익명 로그인 사용자도 anon이 아니라 authenticated 역할을 받는다.
-- 기본 ACL로 붙은 TRUNCATE(RLS를 우회한다)까지 함께 회수한다.
revoke all on all tables in schema public from anon;

-- authenticated는 CRUD. 어느 행이 보이는지는 RLS 정책이 정한다.
grant select, insert, update, delete on all tables in schema public to authenticated;

-- TRUNCATE는 WHERE 없이 테이블을 비우며 RLS를 우회한다. 기본 ACL로
-- 이미 붙어 있으므로 명시적으로 회수한다.
revoke truncate on all tables in schema public from authenticated;

-- deletions는 사용자 읽기 전용. 쓰기는 워커·Route Handler가 service_role로
-- 수행한다. 사용자가 steps_done을 위조하면 삭제 완전성이 무너진다.
revoke insert, update, delete on public.deletions from authenticated;

-- service_role은 RLS를 우회하는 워커·서버 경로다. 전체 권한을 준다.
grant all on all tables in schema public to service_role;
