-- 우리가 부여한 권한을 회수한다. RLS는 유지되므로 되돌린 뒤에도
-- authenticated는 아무 행도 볼 수 없다(안전 방향으로 실패).
-- anon의 기존 기본 ACL은 완전 복원하지 않는다 — 회수가 안전한 방향이다.
revoke all on all tables in schema public from service_role;
revoke select, insert, update, delete on all tables in schema public from authenticated;
