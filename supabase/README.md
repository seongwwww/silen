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

## Storage

- 비공개 버킷 `memories`. 경로 규약 `{user_id}/{uuid}.{ext}`.
- `storage.objects` 정책은 테이블 RLS와 같은 원리다 — 최상위 폴더가 소유자.
  `authenticated`는 자기 폴더만 CRUD, `update`는 없음(원본 불변).
- 사진은 클라이언트가 직접 업로드하고, 서버는 경로의 본인 폴더 여부를
  검증한 뒤 `assets` 행을 만든다. `assets` RLS는 부모 메모 소유권만 보고
  파일 소유권은 안 보므로, 이 경로 검증이 교차 사용자 파일 누출의
  유일한 방어선이다.

## 큐 (pgmq)

- 비동기 큐는 pgmq. 큐 `memory_jobs`, 메시지 `{memory_id, user_id}`.
- 메모 insert AFTER 트리거가 적재한다. in-DB라 메모 커밋과 같은
  트랜잭션 — 유령·유실 잡이 없다. 메시지엔 본문을 싣지 않는다.
- 워커는 특권 역할(로컬 postgres)로 psycopg 직접 접속해 RLS를 우회하므로,
  워커 쿼리가 user_id 필터를 지키는 것이 유일한 격리 방어선이다.
- 새 잡을 추가하면 이 큐를 재사용하고, 처리는 멱등(자연키 upsert)해야 한다.

## 엔티티

- 워커가 메모 텍스트에서 4종(person·place·activity·thing)을 추출해
  `entities`·`memory_entities`를 채운다. relation_type은 `'mentioned'`
  (met/visited/did로 단정하지 않는다 — 과잉해석 금지).
- 추출 name이 원문에 없으면 폐기한다(환각 0%). 추출자이지 해석자가 아니다.
- 고아 entity는 `memory_entities` AFTER DELETE 트리거(`delete_orphan_entity`)로
  즉시 삭제한다 — 링크가 사라진 타인 이름이 남지 않게(삭제 완전성).
- 추출은 Vertex AI Gemini + ADC로 호출한다(env는 루트 `.env.example` 참고).
  본문은 로그·APM에 남기지 않는다(ID·카운트만).
