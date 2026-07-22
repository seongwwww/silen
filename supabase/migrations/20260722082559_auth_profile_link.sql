-- public.users를 auth.users에 종속시키고 프로필을 자동 생성한다.

-- email은 auth.users가 단일 출처다. 여기에 복제하지 않는다:
-- 익명 사용자는 이메일이 없고, 소셜(카카오)은 이메일을 선택 동의로
-- 두며, 한 사용자가 여러 identity를 가지면 이메일이 둘 이상이 된다.
alter table public.users drop column email;

-- 인증과 프로필을 하나로 묶는다. 계정이 사라지면 프로필도 사라진다.
alter table public.users
  add constraint users_id_fkey
  foreign key (id) references auth.users(id) on delete cascade;

-- 프로필 생성을 앱이 아니라 DB에 둔다. 사용자 생성 경로가
-- 익명·매직링크·(후일)소셜로 늘어나는데, 한 경로라도 빠뜨리면
-- 프로필 없는 사용자가 생긴다. 트리거는 경로와 무관하게 걸린다.
create function public.handle_new_user() returns trigger
  language plpgsql
  security definer
  set search_path = ''
as $$
begin
  -- raw_user_meta_data를 처음부터 읽는다. 소셜 provider가 이름을
  -- 이 필드로 넘기므로, 이렇게 두면 소셜 추가 시 트리거를 안 고쳐도 된다.
  insert into public.users (id, display_name)
  values (new.id, new.raw_user_meta_data ->> 'name');
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
