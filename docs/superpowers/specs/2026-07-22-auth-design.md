# 인증 설계 스펙 — 익명 시작 · 매직링크 연결 · RLS 정책

- 날짜: 2026-07-22
- 관련: `docs/decisions/ADR-0002-schema-gates.md`, `.claude/rules/privacy.md`, `.claude/rules/backend.md`, `docs/planning/서비스_기획서.md` §11·13, `docs/design/wireframes.html`
- 상태: 설계 확정 (구현 계획 대기)

## 1. 배경

기획서는 "인증·파일: Supabase Auth"라고만 정하고 **로그인 방식을 어디에도 결정해두지 않았다.** 와이어프레임에는 로그인·가입 화면이 아예 없고, 곧바로 "기록(5초)"으로 시작한다. `testing.md`의 E2E 목록도 "첫 기록 5초"를 핵심 흐름으로 둔다.

즉 제품은 5초 만의 첫 기록을 약속하는데, 그 앞에 계정 생성을 세우면 약속이 깨진다. 이 스펙은 그 충돌을 해소하는 것이 목적이다.

또한 ADR-0002 스키마는 RLS를 **활성화만** 하고 정책을 비워두었다. 지금은 `anon`/`authenticated`가 어떤 행도 못 보는 안전한 상태지만, 동시에 아무것도 동작하지 않는 상태이기도 하다. 정책 작성이 이 스펙의 두 번째 목적이다.

## 2. 결정 요약

| # | 항목 | 결정 |
|---|------|------|
| 1 | 첫 진입 | 익명 세션 자동 생성. 로그인 벽 없음 |
| 2 | 계정 연결 | 이메일 매직링크. 사용자 ID 불변 |
| 3 | `public.users.email` | **제거.** `auth.users`가 단일 출처 |
| 4 | 프로필 생성 | `auth.users` INSERT 트리거 |
| 5 | RLS 정책 | 소유자 직접 / 부모 경유 `EXISTS` 2종 |
| 6 | `deletions` | 사용자는 읽기만. 쓰기는 워커(`service_role`) |
| 7 | 소셜 확장 | 콜백·서비스 진입점·트리거를 provider 무관하게 미리 설계 |

---

## 3. 인증 흐름

```
첫 진입 ──▶ 익명 세션 자동 생성 ──▶ 바로 기록 (5초 약속 유지)
                                        │
                        기록이 쌓이거나 사용자가 요청하면
                                        ▼
                        "다른 기기에서도 보려면 이메일을 남겨주세요"
                                        │
                        updateUser({ email }) + 매직링크 확인
                                        ▼
                        같은 auth.users.id 유지 ──▶ 기존 기록 그대로
```

**사용자 ID가 바뀌지 않는 것이 핵심이다.** 익명 계정과 영구 계정이 같은 `auth.users` 행이므로 데이터 이관이 없다. 이관이 없으면 이관 실패 시나리오도, 부분 이관 복구 로직도 필요 없다.

**연결 유도는 압박이 아니어야 한다**(`frontend.md`: 죄책감 유도 UI 금지). 배지·카운터·경고로 띄우지 않는다. 거절해도 앱은 그대로 동작하며 다시 조르지 않는다.

**유도를 띄우는 정확한 시점은 이 스펙에서 정하지 않는다.** 화면 흐름에 달린 UI 결정이므로 기록 화면 작업에서 정한다. 이 스펙이 보장하는 것은 "언제 부르든 사용자 ID가 유지된 채 연결된다"는 것뿐이다. 설정 화면의 상시 진입점은 이번 범위에 포함한다.

**익명 상태의 위험을 명시한다.** 계정 연결 전에는 기기/브라우저 저장소에 세션이 묶여 있어 **기기를 잃거나 저장소를 지우면 복구할 수 없다.** 이 사실을 연결 안내에 한 줄로 밝힌다. 되돌릴 수 없는 결과를 감추지 않는다.

---

## 4. 스키마 변경

### 4.1 `public.users.email` 제거

현재 `email text not null unique`다. 세 가지 이유로 제거한다.

1. **익명 사용자에게 이메일이 없다.** `not null`이면 프로필 생성 트리거가 그 자리에서 실패한다.
2. **소셜을 붙이면 이메일이 없을 수도 있다.** 카카오는 이메일을 선택 동의 항목으로 두므로 사용자가 거부하면 이메일 없는 영구 계정이 생긴다.
3. **한 사용자가 여러 identity를 가질 수 있다.** 매직링크와 소셜을 둘 다 연결하면 이메일이 둘이 된다. `public.users`에 하나만 복제하면 어느 쪽이 진짜인지 알 수 없다. `auth.users.identities`가 이미 이를 관리한다.

앱은 세션에서 `auth.getUser()`로 이메일을 읽는다. 복제하지 않는다.

**실사용 데이터가 없는 지금이 이 변경을 무상으로 할 수 있는 유일한 시점이다.** 나중에는 expand/backfill/contract 3단계가 필요하다.

### 4.2 `auth.users` FK 연결

`public.users.id`에 `references auth.users(id) on delete cascade`를 추가한다. 지금은 끊어져 있어 `public.users`가 인증과 무관하게 존재할 수 있다.

### 4.3 프로필 생성 트리거

```sql
create function public.handle_new_user() returns trigger
  language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.users (id, display_name)
  values (new.id, new.raw_user_meta_data ->> 'name');
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
```

**앱 코드가 아니라 DB에 두는 이유:** 사용자 생성 경로가 익명·매직링크·(후일)소셜로 늘어나는데, 어느 한 경로라도 프로필 생성을 빠뜨리면 프로필 없는 사용자가 생긴다. 트리거는 경로와 무관하게 걸린다.

**`raw_user_meta_data`를 처음부터 읽는 이유:** 소셜 provider는 이름·아바타를 이 필드로 넘긴다. 지금 매직링크에서는 NULL이 들어가지만, 이렇게 써두면 소셜 추가 시 트리거를 고칠 필요가 없다.

`search_path = ''`는 `security definer` 함수의 표준 방어다. 스키마를 모두 명시해 검색 경로 조작을 막는다.

---

## 5. RLS 정책

두 형태만 쓴다. 형태를 늘리지 않는 것이 검토 가능성을 지킨다.

### 5.1 소유자 직접

`user_id` 컬럼이 있는 테이블. `users`는 `id`로 비교한다.

```sql
create policy "본인 데이터만" on public.memories
  for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));
```

대상: `users`(id 기준) · `memories` · `differences` · `diaries` · `entities` · `signals` · `baselines` · `weekly_reports` · `consents`

`(select auth.uid())`로 감싸는 것은 Postgres가 행마다 재평가하지 않고 한 번만 계산하게 하기 위함이다.

### 5.2 부모 경유 `EXISTS`

`user_id`가 없는 조인·자식 테이블.

```sql
create policy "부모 소유자만" on public.difference_evidence
  for all to authenticated
  using (exists (
    select 1 from public.differences d
     where d.id = difference_id and d.user_id = (select auth.uid())
  ));
```

대상: `assets` · `emotions` · `memory_entities` · `relations` · `difference_evidence` · `diary_sources` · `diary_sections` · `weekly_report_highlights`

**비정규화하지 않은 이유:** 소유자가 부모 한 곳에만 존재하므로 부모와 자식의 `user_id`가 어긋나는 상황이 원천적으로 불가능하다. 비정규화하면 그 불일치를 막는 트리거나 제약이 또 필요하다. FK가 인덱스이므로 이 규모에서 `EXISTS` 비용은 문제되지 않는다.

### 5.3 `deletions` — 읽기 전용

```sql
create policy "본인 삭제 진행만 조회" on public.deletions
  for select to authenticated
  using (user_id = (select auth.uid()));
```

`insert`/`update`/`delete` 정책을 만들지 않는다. 정책이 없으면 해당 동작은 차단된다. 삭제 요청은 Route Handler가 검증 후 `service_role`로 기록하고, 단계 진행은 워커가 쓴다.

**사용자가 ledger를 직접 조작할 수 있으면 삭제 완전성이 무너진다.** `steps_done`을 위조하면 실제로 지워지지 않은 단계가 완료로 표시된다.

### 5.4 워커와 `service_role`

Python 워커는 `service_role`로 접속하며 RLS를 우회한다. 따라서 **워커 코드에서 `user_id` 필터를 빠뜨리면 RLS가 막아주지 않는다.** 워커의 저장소 계층이 user 스코프를 강제하는 유일한 지점이며(`backend.md`), 이는 코드 리뷰 대상이다.

---

## 6. 코드 배치 (2자산 3계층)

### 경계

- `middleware.ts` — **기존 세션 토큰 갱신만** 한다. 세션이 없어도 만들지 않는다.
- `app/auth/callback/route.ts` — PKCE `code`를 세션으로 교환한다.

**미들웨어에서 익명 세션을 만들지 않는 이유:** 미들웨어는 모든 요청에 걸린다. 거기서 세션을 생성하면 크롤러·봇·프리페치가 페이지를 칠 때마다 `auth.users` 행이 하나씩 생겨 인증 테이블이 유령 계정으로 채워진다. 익명 세션은 **사용자가 실제로 기록을 남기려 할 때** 서비스 계층이 만든다.

**콜백은 provider를 모른다.** 매직링크도 OAuth도 같은 `code` 교환을 거치므로, 소셜을 추가해도 이 라우트는 바뀌지 않는다. provider 설정만 늘어난다.

### 서비스

- `lib/services/session.ts`
  - `ensureSession()` — 세션이 없으면 익명 세션을 만든다. **기록을 남기려는 시점에만 호출한다.** 단순 페이지 조회에서는 호출하지 않는다.
  - `linkAccount(method)` — 익명 계정을 영구 계정으로 연결한다. `method: { kind: 'email', address: string }`이 첫 구현체이고, 소셜은 `{ kind: 'oauth', provider: 'kakao' }` 분기를 추가한다.

**단일 진입점을 두는 이유:** 익명→영구 전환은 수단이 무엇이든 "identity를 연결한다"는 같은 동작이다. 호출부가 수단별로 갈라지면 나중에 "연결 전에는 이런 안내를 띄운다" 같은 규칙을 여러 곳에 중복 구현하게 된다.

이 계층은 Request/Response를 모른다(`backend.md` 역방향 의존 금지, ESLint가 강제).

### 저장소

- `lib/repositories/supabase.ts` — 서버·브라우저·미들웨어용 Supabase 클라이언트 생성을 여기 숨긴다. `@supabase/ssr`을 쓴다. 테스트에서 스텁으로 교체 가능해야 한다.

---

## 7. 테스트 요구사항

### 통합 (필수)

- **교차 사용자 격리** — 사용자 A의 세션으로 B의 메모·일기·차이를 조회하면 0건이다(`testing.md` 필수 시나리오). raw SQL로 `set local role authenticated` + `request.jwt.claims` 주입해 실제 RLS를 통과시켜 검증한다.
- **조인 테이블 격리** — A가 B의 `difference_evidence`·`diary_sources`를 조회하면 0건이다. 부모 경유 정책이 실제로 막는지 확인한다.
- **`deletions` 쓰기 차단** — `authenticated` 역할로 `insert`/`update`를 시도하면 실패한다.
- **프로필 자동 생성** — `auth.users`에 행이 생기면 `public.users`에 짝이 생긴다.
- **익명 → 영구 전환 후 기록 유지** — 전환 전에 남긴 메모가 전환 후에도 같은 사용자 것으로 조회된다.
- **매직링크 수신** — Mailpit(`http://127.0.0.1:54324`)에서 메일을 읽어 링크를 추출한다.
- **RLS 뮤테이션 점검** — 정책 하나를 지우면 격리 테스트가 깨지는지 확인한다. 통과만 하는 껍데기 테스트를 걸러낸다.

### 마이그레이션

- 모든 마이그레이션에 down 스크립트를 같은 커밋에 넣는다.
- `supabase db reset`이 빈 DB에서 전체를 재생한다.

---

## 8. 이번 범위 밖

- **소셜 로그인 provider 설정** — 구조는 이번에 준비하되 실제 카카오·Google 연동은 별도 작업. 개발자 앱 등록·리다이렉션 URL이 선행되어야 한다.
- **회원 탈퇴 UI와 삭제 파이프라인 실행** — ledger 구조는 있으나 단계를 실제로 수행하는 워커는 아직 없다.
- **익명 계정 정리 정책** — 방치된 익명 계정을 언제 지울지. 스키마에 영향이 없으므로 사용자를 받기 시작할 때 정한다.
- **익명 로그인 남용 방지(CAPTCHA 등)** — 공개 배포 시점에 검토.
- **임베딩 테이블 RLS** — 테이블 자체가 아직 없다.

## 9. 검증이 필요한 가정

구현 첫 단계에서 확인하고, 다르면 설계를 고친다.

- `updateUser({ email })` 후 매직링크 확인으로 **익명 사용자가 같은 id를 유지한 채 영구 계정이 되는지.** 이 스펙의 전제이므로 가장 먼저 확인한다. 만약 id가 바뀐다면 데이터 이관 설계가 추가로 필요하다.
- Supabase 로컬 스택에서 **익명 로그인이 기본 활성화인지.** `supabase/config.toml`에 설정이 필요할 수 있다.
