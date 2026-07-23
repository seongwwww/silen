drop trigger if exists on_auth_user_created on auth.users;
drop function if exists public.handle_new_user();
alter table public.users drop constraint if exists users_id_fkey;
-- email 복원은 데이터를 되살리지 못한다. 컬럼만 되돌린다.
-- 이 마이그레이션은 실사용 데이터가 없는 시점에만 안전하다.
alter table public.users add column email text;
