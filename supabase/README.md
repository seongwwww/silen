# Supabase 로컬

## 명령

- `npx supabase start` — 로컬 스택 기동 (Docker 필요)
- `npx supabase stop` — 중지
- `npx supabase migration new <name>` — 마이그레이션 생성
- `npx supabase db reset` — 초기화 후 마이그레이션 전체 재적용

로컬 DB URL: `postgresql://postgres:postgres@127.0.0.1:54322/postgres`

**`db reset` 뒤 auth 요청이 502를 내면** Kong↔GoTrue 라우팅이 컨테이너
재시작으로 깨진 것이다. `npx supabase stop && npx supabase start`로 전체를
다시 띄우면 복구된다. 통합 테스트가 `signInAnonymously`에서 502로 무더기
실패하면 이 경우다.

## down 스크립트 규약

Supabase CLI에는 down 마이그레이션 개념이 없다. `database.md`가 요구하는
보상 전략은 `migrations/down/<같은-타임스탬프>_<같은-이름>.down.sql`로 보관한다.

- **자동 실행되지 않는다.** 롤백은 사람이 검토 후 실행한다.
- up 마이그레이션을 추가하면 down도 **같은 커밋에** 넣는다(git.md).
- 적용 전 staging에서 dry-run 한다. production 적용은 사람이 실행한다.

`migrations/down/`은 CLI가 마이그레이션으로 오인하지 않도록 하위 디렉터리에 둔다.

## 인증

- 익명 로그인이 켜져 있다(`config.toml`의 `enable_anonymous_sign_ins`).
  익명 사용자는 `authenticated` 역할을 받는다(`anon`이 아니다).
- 이메일 변경에 확인이 필요하다(`enable_confirmations = true`). 끄면 익명
  사용자가 남의 주소를 자기 계정에 등록할 수 있다.
- 메일은 Mailpit(`http://127.0.0.1:54324`)으로 간다. 실제 발송되지 않는다.
- RLS 정책은 소유자 직접과 부모 경유 EXISTS 두 형태뿐이다. 새 테이블을
  추가하면 둘 중 하나를 골라 정책을 함께 넣는다. 정책 없이 RLS만 켜면
  그 테이블은 앱에서 전혀 보이지 않는다.
- `postgres`가 만든 테이블은 역할 권한이 자동 부여되지 않는다. 새 테이블에는
  `authenticated`(CRUD)·`service_role`(ALL) GRANT를 함께 넣는다. `anon`에는
  주지 않는다.
