# 기록 백엔드 설계 스펙 — 텍스트·감정·사진 쓰기 경로

- 날짜: 2026-07-23
- 관련: `docs/planning/서비스_기획서.md` §7·13, `docs/design/wireframes.html`(기록 5초 화면), `docs/decisions/ADR-0002-schema-gates.md`, `docs/superpowers/specs/2026-07-22-auth-design.md`, `.claude/rules/backend.md`, `.claude/rules/privacy.md`
- 상태: 설계 확정 (구현 계획 대기)
- 선행: 인증(익명 세션·RLS). auth 브랜치가 `main`에 병합된 뒤 이 위에서 분기한다.

## 1. 배경

기획서 §13 구현 순서에서 데이터모델·인증 다음은 **텍스트 기록 + 감정 태그**다. 와이어프레임의 "기록(5초)" 화면([wireframes.html](../../design/wireframes.html))이 이 기능의 UX를 정의한다 — 텍스트 기본, 감정 칩 한 탭, 사진·음성·위치 옵션, "남기기(5초면 끝)".

이 스펙은 그중 **백엔드 쓰기 경로**만 다룬다. 화면 UI는 별도 스펙이다(아래 §8). 범위는 **텍스트 + 감정 + 사진**이며, 음성(STT)·위치(동의·PostGIS)는 각자 하위 시스템을 끌고 오므로 제외한다(기획서 8주 계획도 사진·센서를 W7로 둔다).

기록은 사용자 요청에 **동기 응답**하는 앱의 책임이다(backend.md 2자산 구분). 워커·큐를 쓰지 않는다.

## 2. 결정 요약

| # | 항목 | 결정 |
|---|------|------|
| 1 | API | `POST /api/memories` 한 요청으로 메모 1건 |
| 2 | 필수 입력 | text와 asset 중 **최소 하나**. 빈 기록 거부 |
| 3 | memory_type | 사용자에게 안 묻고 `'moment'` 기본 |
| 4 | 감정 | 칩 3개 → valence `+1/0/-1`, `confirmed_by_user=true`, 선택 |
| 5 | 사진 업로드 | 클라이언트 직접 → Storage(비공개 버킷) + Storage RLS |
| 6 | 쓰기 권한 | authenticated 세션 클라이언트. RLS with-check가 강제. service_role 안 씀 |
| 7 | 원자성 | 메모 우선 생성, emotion·asset 순차. 트랜잭션 아님 |
| 8 | 삭제 | 이 슬라이스에 없음. 사진 삭제 완전성이 불가능하므로 |

---

## 3. API — `POST /api/memories`

### 입력 (zod 검증)

```ts
{
  text?: string,               // 트림 후 비어 있지 않아야 유효
  emotion?: "good" | "neutral" | "bad",
  assetPaths?: string[],       // Storage에 이미 업로드된 객체 경로
  occurredAt?: string,         // ISO 8601. 생략 시 null
}
```

- **`text`와 `assetPaths` 중 최소 하나가 있어야 한다.** 둘 다 없으면 `400`. "빈 기록을 억지로 만들지 않는다"(제품 원칙)와 일치한다.
- `assetPaths`의 각 경로는 `{user_id}/`로 시작해야 한다(서버가 세션 user_id와 대조). 다른 사용자 경로면 `400`.
- `memory_type`은 입력에 없다. 항상 `'moment'`. 마찰 최소화(와이어프레임에 타입 선택이 없다).
- `source_type`은 항상 `'manual'`.

### 출력

- 성공 `201` + `{ memoryId: string }`
- 검증 실패 `400` + 구조화 에러 `{ error: { code, message } }`
- 미인증 `401`
- 서버 에러 `500` + 상관관계 ID (기록 본문은 로그·응답에 남기지 않는다)

### 응답 본문에 원문을 넣지 않는다

생성 결과로 `memoryId`만 반환한다. 화면은 낙관적 UI로 자기가 방금 입력한 값을 이미 갖고 있으므로 원문을 되돌려줄 필요가 없다. 이는 backend.md의 "기록 본문을 로그·APM에 남기지 않는다"와 같은 방향이다.

---

## 4. 감정 매핑

와이어프레임의 칩 3개를 `emotions` 행으로 옮긴다.

| 칩 | `emotion` 입력 | `valence` |
|----|------|-----------|
| 🙂 좋음 | `good` | `+1` |
| 😐 그냥 | `neutral` | `0` |
| 😔 별로 | `bad` | `-1` |

- `confirmed_by_user = true` — 사용자가 직접 골랐으므로 보정이 아니라 확정이다.
- `tags = '{}'`, `confidence = null` — 수동 입력에는 자동 태그·신뢰도가 없다.
- **감정은 선택이다.** `emotion`이 없으면 `emotions` 행을 만들지 않는다. 메모는 감정 없이도 성립한다.
- 메모당 감정은 최대 1건(수동 입력). `emotions` 테이블은 다건을 허용하지만 이 경로는 1건만 쓴다.

---

## 5. Storage — 사진

### 버킷·경로

- 비공개 버킷 **`memories`**. 공개 URL 없음.
- 경로 규약 **`{user_id}/{uuid}.{ext}`**. 최상위 폴더가 소유자 식별자다.

### Storage RLS 정책

테이블 RLS와 같은 격리를 Storage 객체에도 적용한다. `storage.objects`에 정책을 건다.

```sql
create policy "본인 폴더만 조회" on storage.objects
  for select to authenticated
  using (bucket_id = 'memories' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy "본인 폴더만 업로드" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'memories' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy "본인 폴더만 삭제" on storage.objects
  for delete to authenticated
  using (bucket_id = 'memories' and (storage.foldername(name))[1] = (select auth.uid())::text);
```

`update` 정책은 만들지 않는다 — 업로드된 원본은 불변이다. 교체는 삭제 후 재업로드.

### 업로드 흐름

1. 클라이언트가 `memories/{user_id}/{uuid}.jpg`로 직접 업로드(Storage RLS가 경로를 검증).
2. 클라이언트가 `POST /api/memories`에 `assetPaths`로 그 경로를 넘긴다.
3. 서버가 각 경로의 최상위 폴더가 세션 user_id와 같은지 확인하고 `assets` 행을 만든다(`asset_type='photo'`, `file_url`=경로, `mime_type`은 경로 확장자에서 유추, 불명이면 null).

`file_url`에는 공개 URL이 아니라 **Storage 경로**를 저장한다. 조회 시 서명 URL을 발급한다(화면 스펙에서 다룬다).

### 경로 검증은 보안 필수 (누출 방어)

`assets`의 RLS는 부모 `memories`의 소유권만 검사하고 **file_url이 가리키는 Storage 객체의 소유권은 검사하지 않는다.** 따라서 서버가 `assetPaths`의 최상위 폴더를 세션 user_id와 대조하지 않으면, 공격자가 `assetPaths=["{피해자_id}/x.jpg"]`를 자기 메모에 붙일 수 있다. 그 뒤 조회 시 앱이 "자기 메모의 asset"이라 판단해 **피해자 파일의 서명 URL을 발급**하면 교차 사용자 누출이 된다. 서버의 `{user_id}/` 접두 검사가 이 벡터를 막는 유일한 지점이며, 통합 테스트로 고정한다(§9).

---

## 6. 코드 배치 (2자산 3계층)

### 경계 — `app/api/memories/route.ts`

- `POST` 핸들러. 세션 확인(없으면 `ensureSession`으로 익명 세션 생성 — 기록 시점이 세션을 만드는 유일한 지점, auth 스펙 §6), zod 검증, 서비스 호출, 직렬화.
- 비즈니스 로직 없음.

### 서비스 — `lib/services/memory.ts`

```ts
export type EmotionChoice = "good" | "neutral" | "bad";

export type CreateMemoryInput = {
  userId: string;
  text?: string;
  emotion?: EmotionChoice;
  assetPaths?: string[];
  occurredAt?: string;
};

export interface MemoryRepository {
  insertMemory(row: {
    userId: string;
    rawText: string | null;
    occurredAt: string | null;
  }): Promise<{ id: string }>;
  insertEmotion(row: { memoryId: string; valence: number }): Promise<void>;
  insertAsset(row: { memoryId: string; fileUrl: string; mimeType: string | null }): Promise<void>;
}

export async function createMemory(
  repo: MemoryRepository,
  input: CreateMemoryInput,
): Promise<{ memoryId: string }>;
```

규칙:
- **text(트림 후)와 assetPaths 중 최소 하나 없으면 예외.** 경계가 이를 400으로 변환한다.
- 감정 매핑(`good→+1, neutral→0, bad→-1`).
- 프레임워크·HTTP·Supabase 타입을 모른다. `MemoryRepository`를 주입받는다.

### 저장소 — `lib/repositories/memory.ts`

- `MemoryRepository`를 Supabase **authenticated 세션 클라이언트**로 구현한다.
- `user_id`는 세션에서 온다. RLS with-check(`user_id = auth.uid()`)가 위조를 막으므로 service_role을 쓰지 않는다.
- emotion·asset은 부모 경유 RLS로 검증된다(방금 만든 자기 메모의 자식이므로 통과).

### 원자성

memory를 먼저 insert하고 그 id로 emotion·asset을 순차 insert한다. 단일 트랜잭션이 아니다.

근거: 이들은 supabase-js 다중 호출이라 하나의 트랜잭션으로 묶기 어렵고, **실패 시 핵심(사용자의 글)이 남는 것이 올바른 실패 모드**다. 감정·사진 부가 insert가 실패해도 메모 자체는 보존된다. "사용자의 말을 잃지 않는다"가 우선이다. 부가 insert 실패는 500으로 보고하되 메모는 롤백하지 않는다.

---

## 7. 이번 범위에서 제외 (그리고 이유)

- **삭제 경로** — 사진이 생기면 삭제는 Storage 파일까지 지워야 한다(privacy.md "삭제 = 원본 + Storage + …"). 그 파이프라인(ADR-0002 deletion ledger 워커)은 아직 없다. **삭제를 이 슬라이스에 넣지 않음**으로써 "지웠는데 Storage에 남는" 불완전 삭제를 원천 차단한다. **삭제 기능을 만들 때 Storage 단계를 반드시 포함해야 한다** — 이 제약을 삭제 스펙에 명시한다.
- **탐지 잡 적재** — 나중에 memory 생성이 탐지 잡을 큐에 넣는다(멱등). 워커가 없어 지금은 하지 않는다. 큐 적재 지점은 경계가 아니라 서비스나 그 이후에 둔다(구현 시 결정).
- **읽기(타임라인)** — 이 슬라이스는 CREATE만. 목록 조회는 화면 스펙에서 필요할 때 만든다.
- **음성·위치** — STT·동의·PostGIS를 끌고 오므로 별도 기능.
- **후속 질문**(과요청 방지 규칙) — 일기·탐지가 있어야 의미가 있어 후속.

### 알려진 한계 — 고아 파일

클라이언트가 Storage에 업로드한 뒤 `POST /api/memories`가 실패하면 참조 없는 파일이 Storage에 남는다. 대응:
- 클라이언트가 생성 실패 시 방금 올린 객체를 삭제한다(Storage RLS delete 권한 보유).
- 향후 주기 sweep으로 asset 행이 없는 `{user_id}/` 객체를 정리한다(이 스펙 범위 밖).

MVP 한계로 명시하고, 데이터 유출이 아니라(본인만 접근 가능) 저장 낭비임을 밝힌다.

---

## 8. 후속 스펙

- **기록 화면 UI** — 텍스트 필드·감정 칩·사진 선택·업로드 진행. frontend.md의 empty/loading/processing/error/offline 5종, 접근성, 공통 상태 뷰 컴포넌트. 이 API를 호출한다.
- **삭제 파이프라인** — deletion ledger 워커. Storage 단계 포함 필수(§7).
- **탐지 적재** — memory 생성 → 탐지 큐(멱등).

---

## 9. 테스트 요구사항

### 통합 (필수)

- 메모 생성 → `memories`·`emotions`·`assets` 행이 기대대로 생긴다.
- **text·asset 둘 다 없으면 거부**(빈 기록 안 만듦 — 제품 원칙).
- text만으로 생성됨(감정·사진 없이).
- 감정만 있고 사진 없는 메모, 사진만 있고 텍스트 없는 메모 각각 생성됨.
- **교차 사용자**: B의 세션으로 `user_id=A`를 위조해 insert하면 RLS가 차단한다(testing.md 필수 시나리오).
- **Storage RLS**: A가 `{B_id}/` 경로에 업로드·조회를 시도하면 실패한다.
- **경로 검증**: `assetPaths`에 남의 폴더 경로를 넣어 생성 요청하면 400으로 거부된다(누출 방어, §5).
- 부가 insert(emotion) 실패 시에도 memory 행은 남는다(원발 실패 모드 검증).

### 단위

- `createMemory` 감정 매핑(`good→+1` 등).
- text·asset 둘 다 없을 때 예외.
- 트림만 있는 공백 text는 없는 것으로 취급.

### 마이그레이션

- 버킷 생성·Storage 정책 마이그레이션에 down 스크립트를 같은 커밋에.
- `supabase db reset`이 빈 DB에서 재생. (db reset 후 auth 502는 재기동으로 복구 — supabase/README)

---

## 10. 검증이 필요한 가정

구현 첫 단계에서 확인하고, 다르면 설계를 고친다.

- **버킷·Storage 정책을 마이그레이션(SQL)으로 만들 수 있는지.** Supabase는 `storage.buckets` insert와 `storage.objects` 정책으로 코드화 가능한 것으로 보이나, 로컬 CLI에서 그대로 재생되는지 확인한다. 안 되면 `config.toml`의 `[storage.buckets]` 선언 방식으로 전환한다.
- **클라이언트 직접 업로드가 익명 세션에서도 되는지.** 익명 사용자도 `authenticated` 역할이므로 Storage 정책이 적용될 것으로 보이나 확인한다.
