# 기록 백엔드 (텍스트·감정·사진 쓰기 경로) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `POST /api/memories` 한 요청으로 텍스트·감정·사진 메모를 만들고, Storage와 테이블 모두에서 교차 사용자 접근이 차단되는 백엔드 쓰기 경로를 만든다.

**Architecture:** 스펙(`docs/superpowers/specs/2026-07-23-recording-backend-design.md`)을 그대로 옮긴다. 경계(Route Handler) → 서비스(`createMemory`, 프레임워크 무지) → 저장소(authenticated 세션 클라이언트, RLS가 강제). 사진은 클라이언트가 Storage에 직접 올린 경로를 서버가 검증 후 `assets` 행으로 기록한다. 가장 위험한 가정(버킷·Storage 정책을 마이그레이션으로 재생 가능한지)을 Task 1에서 먼저 검증한다.

**Tech Stack:** Next.js 16 Route Handlers · zod · Supabase Storage · PostgreSQL RLS · `@supabase/ssr` · Vitest(통합·단위)

## Global Constraints

- 산출물은 **코드**다. `main` 직접 커밋 금지 — `feat/recording-backend` 브랜치에서 작업한다(git.md).
- **선행: auth PR(#3)이 `main`에 병합되어야 한다.** 이 기능은 세션 서비스(`lib/services/session.ts`), Supabase 클라이언트(`lib/repositories/supabase.ts`), RLS 정책, 역할 GRANT에 의존한다. 병합 전에는 브랜치를 만들지 않는다.
- 커밋 메시지는 `<type>(<scope>): <한국어 요약>`. scope는 `api`·`db`. `Co-Authored-By` 트레일러.
- **마이그레이션은 up/down을 같은 커밋에.** down은 `supabase/migrations/down/<타임스탬프>_<이름>.down.sql`.
- 타임스탬프는 `npx supabase migration new <name>` 생성값. 이 문서의 `<ts1>`을 그 값으로 대체한다.
- 쓰기는 **authenticated 세션 클라이언트**로. `user_id`는 세션에서 오고 RLS with-check가 강제. service_role 안 씀.
- 입력: **text(트림 후)와 assetPaths 중 최소 하나 필수.** 없으면 400. `memory_type='moment'`, `source_type='manual'` 고정.
- 감정 매핑: `good→+1`, `neutral→0`, `bad→-1`. `confirmed_by_user=true`. 감정은 선택.
- **`assetPaths`의 각 경로는 세션 `{user_id}/`로 시작해야 한다.** 아니면 400. 이 검증이 교차 사용자 파일 누출의 유일한 방어선이다(스펙 §5).
- 인증·Storage·RLS 변경이므로 병합 전 `/security-review`(privacy.md).
- 로컬 Supabase 스택 필요. **`db reset` 후 auth 502는 `supabase stop && start`로 복구**(supabase/README).
- 이 슬라이스에 **삭제 경로를 만들지 않는다**(스펙 §7). 사진 삭제 완전성이 워커 없이는 불가능하므로.

## 스펙과 조정한 점

| 스펙 | 계획 | 이유 |
|---|---|---|
| §3 `401 미인증` | **구현 안 함** | 이 엔드포인트는 `ensureSession`으로 없으면 익명 세션을 만든다(auth §6). 세션이 항상 존재하므로 401이 발생하지 않는다 |

---

## File Structure

| 경로 | 책임 |
|------|------|
| `supabase/migrations/<ts1>_recording_storage.sql` | `memories` 버킷 + storage.objects RLS 정책 |
| `lib/services/memory.ts` | `createMemory` — 검증·감정 매핑·경로 검증·mime 유추. 프레임워크 무지 |
| `lib/services/memory.test.ts` | 서비스 단위 테스트(스텁 저장소) |
| `lib/repositories/memoryRepository.ts` | `MemoryRepository`를 authenticated 클라이언트로 구현 |
| `lib/repositories/memory.integration.test.ts` | 행 생성·교차 사용자 RLS·Storage RLS |
| `app/api/memories/route.ts` | 경계 — 세션·zod·서비스 호출·직렬화 |
| `app/api/memories/route.integration.test.ts` | 라이브 스모크(익명 세션 자동 생성 → 생성) |

---

## Task 1: Storage 버킷과 RLS 정책

가장 위험한 가정을 먼저 검증한다: **버킷·정책을 SQL 마이그레이션으로 만들고 `db reset`으로 재생할 수 있는가.** 여기서 막히면 이후 사진 경로 전체가 달라진다.

**Files:**
- Create: `supabase/migrations/<ts1>_recording_storage.sql`, `supabase/migrations/down/<ts1>_recording_storage.down.sql`, `lib/repositories/storage.integration.test.ts`

**Interfaces:**
- Consumes: auth의 `lib/repositories/testSupport.ts`(`adminClient`, `SUPABASE_URL`, `ANON_KEY`)
- Produces: 비공개 버킷 `memories`, storage.objects 정책 3종

- [ ] **Step 1: 브랜치 생성 (auth 병합 확인 후)**

```powershell
gh pr view 3 --json state | ConvertFrom-Json    # state가 MERGED인지 확인
git checkout main
git pull --ff-only
git checkout -b feat/recording-backend
```

`state`가 `MERGED`가 아니면 중단하고 사람에게 알린다. 이 기능은 auth 없이는 성립하지 않는다.

- [ ] **Step 2: 마이그레이션 생성**

```powershell
npx supabase migration new recording_storage
```

출력의 타임스탬프를 `<ts1>`로 쓴다.

- [ ] **Step 3: up 스크립트 작성**

`supabase/migrations/<ts1>_recording_storage.sql`:

```sql
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
```

`update` 정책은 만들지 않는다 — 업로드 원본은 불변, 교체는 삭제 후 재업로드.

- [ ] **Step 4: down 스크립트 작성**

`supabase/migrations/down/<ts1>_recording_storage.down.sql`:

```sql
drop policy if exists "본인 폴더만 삭제" on storage.objects;
drop policy if exists "본인 폴더만 업로드" on storage.objects;
drop policy if exists "본인 폴더만 조회" on storage.objects;
-- 버킷에 객체가 남아 있으면 실패한다(의도된 동작). 비운 뒤 지운다.
delete from storage.buckets where id = 'memories';
```

- [ ] **Step 5: 적용 및 재생 확인**

```powershell
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
```

Expected: `Applying migration <ts1>_recording_storage.sql...` 출력, `db reset` 종료 코드 0.

**정책 생성이 권한 오류로 실패하면** `postgres` 역할이 `storage.objects`에 정책을 못 만드는 것이다. 그 경우 마이그레이션 첫 줄에 `set role supabase_storage_admin;`을 추가하거나, 버킷을 `config.toml`의 `[storage.buckets.memories]`로 선언하는 방식으로 전환한다. 어느 쪽이든 이 Step에서 확정한다.

- [ ] **Step 6: Storage RLS 통합 테스트 작성**

`lib/repositories/storage.integration.test.ts`:

```ts
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { adminClient, SUPABASE_URL, ANON_KEY } from "./testSupport";

let admin: SupabaseClient;
let alice: string;
let bob: string;

async function clientFor(email: string): Promise<SupabaseClient> {
  const { data, error } = await admin.auth.admin.generateLink({ type: "magiclink", email });
  if (error) throw error;
  const client = createClient(SUPABASE_URL, ANON_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { error: verifyError } = await client.auth.verifyOtp({
    token_hash: data.properties.hashed_token,
    type: "magiclink",
  });
  if (verifyError) throw verifyError;
  return client;
}

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);

beforeAll(async () => {
  admin = adminClient();
  const { data: a } = await admin.auth.admin.createUser({
    email: "alice-storage@example.com",
    email_confirm: true,
  });
  const { data: b } = await admin.auth.admin.createUser({
    email: "bob-storage@example.com",
    email_confirm: true,
  });
  alice = a.user!.id;
  bob = b.user!.id;
});

afterAll(async () => {
  await admin.auth.admin.deleteUser(alice);
  await admin.auth.admin.deleteUser(bob);
});

describe("Storage RLS", () => {
  it("본인 폴더에는 업로드된다", async () => {
    const client = await clientFor("alice-storage@example.com");
    const { error } = await client.storage
      .from("memories")
      .upload(`${alice}/own.png`, PNG, { contentType: "image/png" });
    expect(error).toBeNull();
  });

  it("남의 폴더에는 업로드되지 않는다", async () => {
    const client = await clientFor("alice-storage@example.com");
    const { error } = await client.storage
      .from("memories")
      .upload(`${bob}/intruder.png`, PNG, { contentType: "image/png" });
    expect(error).not.toBeNull();
  });

  it("남의 폴더 객체는 조회되지 않는다", async () => {
    const aliceClient = await clientFor("alice-storage@example.com");
    await aliceClient.storage.from("memories").upload(`${alice}/secret.png`, PNG, {
      contentType: "image/png",
    });

    const bobClient = await clientFor("bob-storage@example.com");
    const { data, error } = await bobClient.storage.from("memories").download(`${alice}/secret.png`);
    // RLS로 막히면 error가 있거나 data가 비어 있다.
    expect(error ?? data === null).toBeTruthy();
  });
});
```

- [ ] **Step 7: 테스트 실행**

```powershell
npm run test:integration
```

Expected: 기존 통합 테스트 + Storage RLS 3건이 통과. 502가 나면 `supabase stop && start`(README).

- [ ] **Step 8: 커밋**

```powershell
git add supabase/migrations lib/repositories/storage.integration.test.ts
git commit -m "feat(db): 사진용 memories 버킷과 Storage RLS

테이블 RLS와 같은 격리를 storage.objects에 적용한다. 최상위 폴더가
소유자 식별자이며, authenticated는 자기 {user_id}/ 아래만 CRUD한다.
남의 폴더 업로드·조회가 막히는 것을 통합 테스트로 고정.

ADR-0002"
```

---

## Task 2: 서비스 — createMemory (단위, DB 없음)

도메인 규칙을 순수 함수로 먼저 만든다. 감정 매핑·빈 기록 거부·경로 검증·mime 유추. 저장소는 인터페이스로 주입해 스텁으로 테스트한다.

**Files:**
- Create: `lib/services/memory.ts`, `lib/services/memory.test.ts`

**Interfaces:**
- Consumes: 없음 (순수 도메인)
- Produces:
  ```ts
  type EmotionChoice = "good" | "neutral" | "bad";
  interface MemoryRepository {
    insertMemory(row: { userId: string; rawText: string | null; occurredAt: string | null }): Promise<{ id: string }>;
    insertEmotion(row: { memoryId: string; valence: number }): Promise<void>;
    insertAsset(row: { memoryId: string; fileUrl: string; mimeType: string | null }): Promise<void>;
  }
  type CreateMemoryInput = { userId: string; text?: string; emotion?: EmotionChoice; assetPaths?: string[]; occurredAt?: string };
  function createMemory(repo: MemoryRepository, input: CreateMemoryInput): Promise<{ memoryId: string }>;
  class EmptyMemoryError extends Error {}
  class ForeignAssetPathError extends Error {}
  ```

- [ ] **Step 1: 실패하는 테스트 작성**

`lib/services/memory.test.ts`:

```ts
import { describe, it, expect, vi } from "vitest";
import {
  createMemory,
  EmptyMemoryError,
  ForeignAssetPathError,
  type MemoryRepository,
} from "./memory";

function stubRepo(overrides: Partial<MemoryRepository> = {}): MemoryRepository {
  return {
    insertMemory: vi.fn().mockResolvedValue({ id: "mem-1" }),
    insertEmotion: vi.fn().mockResolvedValue(undefined),
    insertAsset: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

const USER = "11111111-1111-1111-1111-111111111111";

describe("createMemory", () => {
  it("텍스트만으로 메모를 만든다", async () => {
    const repo = stubRepo();
    const result = await createMemory(repo, { userId: USER, text: "오늘 그 노래 또 들음" });

    expect(repo.insertMemory).toHaveBeenCalledWith({
      userId: USER,
      rawText: "오늘 그 노래 또 들음",
      occurredAt: null,
    });
    expect(repo.insertEmotion).not.toHaveBeenCalled();
    expect(repo.insertAsset).not.toHaveBeenCalled();
    expect(result).toEqual({ memoryId: "mem-1" });
  });

  it("감정 칩을 valence로 매핑한다", async () => {
    const repo = stubRepo();
    await createMemory(repo, { userId: USER, text: "좋았다", emotion: "good" });
    expect(repo.insertEmotion).toHaveBeenCalledWith({ memoryId: "mem-1", valence: 1 });

    const repo2 = stubRepo();
    await createMemory(repo2, { userId: USER, text: "별로", emotion: "bad" });
    expect(repo2.insertEmotion).toHaveBeenCalledWith({ memoryId: "mem-1", valence: -1 });

    const repo3 = stubRepo();
    await createMemory(repo3, { userId: USER, text: "그냥", emotion: "neutral" });
    expect(repo3.insertEmotion).toHaveBeenCalledWith({ memoryId: "mem-1", valence: 0 });
  });

  it("사진 경로를 asset으로 기록하고 mime을 유추한다", async () => {
    const repo = stubRepo();
    await createMemory(repo, { userId: USER, assetPaths: [`${USER}/a.jpg`, `${USER}/b.png`] });

    expect(repo.insertAsset).toHaveBeenCalledWith({
      memoryId: "mem-1",
      fileUrl: `${USER}/a.jpg`,
      mimeType: "image/jpeg",
    });
    expect(repo.insertAsset).toHaveBeenCalledWith({
      memoryId: "mem-1",
      fileUrl: `${USER}/b.png`,
      mimeType: "image/png",
    });
  });

  it("text와 asset이 둘 다 없으면 거부한다", async () => {
    const repo = stubRepo();
    await expect(createMemory(repo, { userId: USER })).rejects.toBeInstanceOf(EmptyMemoryError);
    expect(repo.insertMemory).not.toHaveBeenCalled();
  });

  it("공백뿐인 text는 없는 것으로 취급한다", async () => {
    const repo = stubRepo();
    await expect(createMemory(repo, { userId: USER, text: "   " })).rejects.toBeInstanceOf(
      EmptyMemoryError,
    );
  });

  it("남의 폴더 경로는 거부한다", async () => {
    const repo = stubRepo();
    await expect(
      createMemory(repo, { userId: USER, assetPaths: ["22222222-2222-2222-2222-222222222222/x.jpg"] }),
    ).rejects.toBeInstanceOf(ForeignAssetPathError);
    expect(repo.insertMemory).not.toHaveBeenCalled();
  });

  it("occurredAt을 그대로 넘긴다", async () => {
    const repo = stubRepo();
    await createMemory(repo, { userId: USER, text: "메모", occurredAt: "2026-03-01T09:00:00Z" });
    expect(repo.insertMemory).toHaveBeenCalledWith({
      userId: USER,
      rawText: "메모",
      occurredAt: "2026-03-01T09:00:00Z",
    });
  });
});
```

- [ ] **Step 2: 실패 확인**

```powershell
npm test
```

Expected: FAIL — `Cannot find module './memory'`.

- [ ] **Step 3: 구현 작성**

`lib/services/memory.ts`:

```ts
/**
 * 기록 도메인 규칙. 프레임워크·HTTP·Supabase 타입을 모른다(backend.md).
 * 저장소는 MemoryRepository로 주입받는다.
 */

export type EmotionChoice = "good" | "neutral" | "bad";

export interface MemoryRepository {
  insertMemory(row: {
    userId: string;
    rawText: string | null;
    occurredAt: string | null;
  }): Promise<{ id: string }>;
  insertEmotion(row: { memoryId: string; valence: number }): Promise<void>;
  insertAsset(row: { memoryId: string; fileUrl: string; mimeType: string | null }): Promise<void>;
}

export type CreateMemoryInput = {
  userId: string;
  text?: string;
  emotion?: EmotionChoice;
  assetPaths?: string[];
  occurredAt?: string;
};

/** text와 asset이 둘 다 없을 때. 빈 기록은 만들지 않는다(제품 원칙). */
export class EmptyMemoryError extends Error {
  constructor() {
    super("text와 asset 중 최소 하나가 필요하다");
    this.name = "EmptyMemoryError";
  }
}

/** assetPaths에 세션 사용자 폴더가 아닌 경로가 있을 때(누출 방어). */
export class ForeignAssetPathError extends Error {
  constructor() {
    super("assetPaths는 본인 폴더로 시작해야 한다");
    this.name = "ForeignAssetPathError";
  }
}

const VALENCE: Record<EmotionChoice, number> = { good: 1, neutral: 0, bad: -1 };

const MIME_BY_EXT: Record<string, string> = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
  gif: "image/gif",
  heic: "image/heic",
};

function deriveMime(path: string): string | null {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  return MIME_BY_EXT[ext] ?? null;
}

export async function createMemory(
  repo: MemoryRepository,
  input: CreateMemoryInput,
): Promise<{ memoryId: string }> {
  const trimmed = input.text?.trim() ?? "";
  const hasText = trimmed.length > 0;
  const paths = input.assetPaths ?? [];
  const hasAssets = paths.length > 0;

  if (!hasText && !hasAssets) {
    throw new EmptyMemoryError();
  }

  // 경로 검증: RLS는 파일 소유권을 안 보므로 여기가 유일한 방어선(스펙 §5).
  for (const path of paths) {
    if ((path.split("/")[0] ?? "") !== input.userId) {
      throw new ForeignAssetPathError();
    }
  }

  const { id: memoryId } = await repo.insertMemory({
    userId: input.userId,
    rawText: hasText ? trimmed : null,
    occurredAt: input.occurredAt ?? null,
  });

  if (input.emotion) {
    await repo.insertEmotion({ memoryId, valence: VALENCE[input.emotion] });
  }

  for (const path of paths) {
    await repo.insertAsset({ memoryId, fileUrl: path, mimeType: deriveMime(path) });
  }

  return { memoryId };
}
```

- [ ] **Step 4: 통과 확인**

```powershell
npm test
```

Expected: PASS. 신규 7건 포함.

- [ ] **Step 5: 서비스 계층 규칙 확인**

```powershell
npx eslint lib/services
```

Expected: 종료 코드 0. `memory.ts`가 `next/*`를 import하면 규칙이 막는다.

- [ ] **Step 6: 커밋**

```powershell
git add lib/services/memory.ts lib/services/memory.test.ts
git commit -m "feat(api): createMemory 서비스 — 검증·감정 매핑·경로 방어

빈 기록 거부, 감정 칩 valence 매핑, mime 유추.
assetPaths의 본인 폴더 검증이 교차 사용자 파일 누출의 유일한
방어선이라 서비스에서 강제한다(RLS는 파일 소유권을 안 본다).
MemoryRepository 주입으로 프레임워크를 모른다."
```

---

## Task 3: 저장소 구현 + 통합

`MemoryRepository`를 authenticated 클라이언트로 구현하고, 실제 RLS를 통과하는지 검증한다.

**Files:**
- Create: `lib/repositories/memoryRepository.ts`, `lib/repositories/memory.integration.test.ts`

**Interfaces:**
- Consumes: Task 2의 `MemoryRepository`, auth의 `testSupport`
- Produces: `createMemoryRepository(client: SupabaseClient): MemoryRepository`

- [ ] **Step 1: 구현 작성**

`lib/repositories/memoryRepository.ts`:

```ts
import type { SupabaseClient } from "@supabase/supabase-js";
import type { MemoryRepository } from "@/lib/services/memory";

/**
 * authenticated 세션 클라이언트로 MemoryRepository를 구현한다.
 * user_id는 세션에서 오고 RLS with-check가 위조를 막으므로 service_role을
 * 쓰지 않는다. emotion·asset은 부모 경유 RLS로 검증된다.
 */
export function createMemoryRepository(client: SupabaseClient): MemoryRepository {
  return {
    async insertMemory(row) {
      const { data, error } = await client
        .from("memories")
        .insert({
          user_id: row.userId,
          raw_text: row.rawText,
          occurred_at: row.occurredAt,
          source_type: "manual",
          memory_type: "moment",
        })
        .select("id")
        .single();
      if (error) throw error;
      return { id: data.id as string };
    },

    async insertEmotion(row) {
      const { error } = await client
        .from("emotions")
        .insert({ memory_id: row.memoryId, valence: row.valence, confirmed_by_user: true });
      if (error) throw error;
    },

    async insertAsset(row) {
      const { error } = await client
        .from("assets")
        .insert({
          memory_id: row.memoryId,
          asset_type: "photo",
          file_url: row.fileUrl,
          mime_type: row.mimeType,
        });
      if (error) throw error;
    },
  };
}
```

- [ ] **Step 2: 통합 테스트 작성**

`lib/repositories/memory.integration.test.ts`:

```ts
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { Client } from "pg";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { adminClient, SUPABASE_URL, ANON_KEY } from "./testSupport";
import { createMemoryRepository } from "./memoryRepository";
import { createMemory } from "@/lib/services/memory";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let admin: SupabaseClient;
let db: Client;
let alice: string;
let bob: string;

async function clientFor(email: string): Promise<SupabaseClient> {
  const { data, error } = await admin.auth.admin.generateLink({ type: "magiclink", email });
  if (error) throw error;
  const client = createClient(SUPABASE_URL, ANON_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { error: verifyError } = await client.auth.verifyOtp({
    token_hash: data.properties.hashed_token,
    type: "magiclink",
  });
  if (verifyError) throw verifyError;
  return client;
}

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
  const { data: a } = await admin.auth.admin.createUser({
    email: "alice-mem@example.com",
    email_confirm: true,
  });
  const { data: b } = await admin.auth.admin.createUser({
    email: "bob-mem@example.com",
    email_confirm: true,
  });
  alice = a.user!.id;
  bob = b.user!.id;
});

afterAll(async () => {
  await admin.auth.admin.deleteUser(alice);
  await admin.auth.admin.deleteUser(bob);
  await db.end();
});

describe("메모 생성", () => {
  it("텍스트+감정 메모가 memories·emotions 행으로 생긴다", async () => {
    const client = await clientFor("alice-mem@example.com");
    const repo = createMemoryRepository(client);

    const { memoryId } = await createMemory(repo, {
      userId: alice,
      text: "오늘 그 노래 또 들음",
      emotion: "good",
    });

    const mem = await db.query("select raw_text, memory_type, source_type from public.memories where id = $1", [
      memoryId,
    ]);
    expect(mem.rows[0]).toEqual({
      raw_text: "오늘 그 노래 또 들음",
      memory_type: "moment",
      source_type: "manual",
    });
    const emo = await db.query("select valence, confirmed_by_user from public.emotions where memory_id = $1", [
      memoryId,
    ]);
    expect(emo.rows[0]).toEqual({ valence: 1, confirmed_by_user: true });
  });

  it("사진만 있는 메모가 assets 행으로 생긴다", async () => {
    const client = await clientFor("alice-mem@example.com");
    const repo = createMemoryRepository(client);

    const { memoryId } = await createMemory(repo, {
      userId: alice,
      assetPaths: [`${alice}/photo.jpg`],
    });

    const asset = await db.query(
      "select asset_type, file_url, mime_type from public.assets where memory_id = $1",
      [memoryId],
    );
    expect(asset.rows[0]).toEqual({
      asset_type: "photo",
      file_url: `${alice}/photo.jpg`,
      mime_type: "image/jpeg",
    });
  });

  it("남의 user_id로 위조 insert하면 RLS가 막는다", async () => {
    // Alice의 세션 클라이언트로 Bob 소유의 메모를 만들려 하면 with-check 위반.
    const client = await clientFor("alice-mem@example.com");
    const repo = createMemoryRepository(client);

    await expect(
      repo.insertMemory({ userId: bob, rawText: "위조", occurredAt: null }),
    ).rejects.toBeTruthy();
  });
});
```

- [ ] **Step 3: 실행**

```powershell
npm run test:integration
```

Expected: PASS. 신규 3건 포함. (스택 기동 상태, 502 시 재기동)

- [ ] **Step 4: 뮤테이션 점검 — RLS가 실제 방어선인지**

`memories`의 소유자 정책을 잠시 지우고 위조 테스트가 깨지는지 본다.

```powershell
node -e "const{Client}=require('pg');const c=new Client({connectionString:'postgresql://postgres:postgres@127.0.0.1:54322/postgres'});c.connect().then(()=>c.query('drop policy \"본인 데이터만\" on public.memories')).then(()=>{console.log('dropped');return c.end()})"
npx vitest run --config vitest.integration.config.mts lib/repositories/memory.integration.test.ts
```

Expected: FAIL — "남의 user_id로 위조 insert하면 RLS가 막는다"가 깨진다(정책이 없으면 위조가 통과하거나 전면 차단으로 다른 테스트가 깨진다).

복구:

```powershell
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
npm run test:integration
```

Expected: PASS.

- [ ] **Step 5: 커밋**

```powershell
git add lib/repositories/memoryRepository.ts lib/repositories/memory.integration.test.ts
git commit -m "feat(api): MemoryRepository 구현과 통합 테스트

authenticated 세션 클라이언트로 memories·emotions·assets를 쓴다.
user_id는 세션에서 오고 RLS with-check가 위조를 막는다.
뮤테이션 점검으로 RLS가 실제 방어선임을 확인."
```

---

## Task 4: 경계 — POST /api/memories

**Files:**
- Create: `app/api/memories/route.ts`, `app/api/memories/route.integration.test.ts`

**Interfaces:**
- Consumes: Task 2·3, auth의 `createServerSupabase`, `ensureSession`
- Produces: `POST /api/memories`

- [ ] **Step 1: Route Handler 작성**

`app/api/memories/route.ts`:

```ts
import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createMemoryRepository } from "@/lib/repositories/memoryRepository";
import {
  createMemory,
  EmptyMemoryError,
  ForeignAssetPathError,
} from "@/lib/services/memory";

const bodySchema = z.object({
  text: z.string().optional(),
  emotion: z.enum(["good", "neutral", "bad"]).optional(),
  assetPaths: z.array(z.string()).optional(),
  occurredAt: z.string().datetime().optional(),
});

/**
 * 기록 1건을 만든다. 세션이 없으면 익명 세션을 만든다(auth §6) —
 * 기록 시점이 세션을 만드는 유일한 지점이다. 401은 발생하지 않는다.
 */
export async function POST(request: NextRequest) {
  let parsed;
  try {
    parsed = bodySchema.parse(await request.json());
  } catch {
    return NextResponse.json(
      { error: { code: "invalid_body", message: "요청 형식이 올바르지 않습니다" } },
      { status: 400 },
    );
  }

  const supabase = await createServerSupabase();

  // 기록 시점에 익명 세션을 보장한다.
  const {
    data: { user },
  } = await supabase.auth.getUser();
  let userId = user?.id;
  if (!userId) {
    const { data, error } = await supabase.auth.signInAnonymously();
    if (error || !data.user) {
      return NextResponse.json(
        { error: { code: "session_failed", message: "세션 생성 실패" } },
        { status: 500 },
      );
    }
    userId = data.user.id;
  }

  const repo = createMemoryRepository(supabase);

  try {
    const { memoryId } = await createMemory(repo, {
      userId,
      text: parsed.text,
      emotion: parsed.emotion,
      assetPaths: parsed.assetPaths,
      occurredAt: parsed.occurredAt,
    });
    return NextResponse.json({ memoryId }, { status: 201 });
  } catch (err) {
    if (err instanceof EmptyMemoryError) {
      return NextResponse.json(
        { error: { code: "empty_memory", message: "내용이나 사진이 필요합니다" } },
        { status: 400 },
      );
    }
    if (err instanceof ForeignAssetPathError) {
      return NextResponse.json(
        { error: { code: "foreign_asset", message: "본인 사진만 첨부할 수 있습니다" } },
        { status: 400 },
      );
    }
    // 본문·식별 정보를 응답·로그에 싣지 않는다(backend.md).
    return NextResponse.json(
      { error: { code: "server_error", message: "저장에 실패했습니다" } },
      { status: 500 },
    );
  }
}
```

zod가 없으면 설치한다:

```powershell
npm install zod
```

- [ ] **Step 2: 라이브 스모크 테스트 작성**

Route Handler는 쿠키 기반 세션을 쓰므로 vitest에서 직접 호출하기 어렵다. 실제 서버에 HTTP로 쏘아 익명 세션 자동 생성까지 통째로 검증한다(auth Task 6과 같은 방식).

`app/api/memories/route.integration.test.ts`:

```ts
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { Client } from "pg";

const BASE = process.env.APP_BASE_URL ?? "http://localhost:3000";
const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let db: Client;

beforeAll(async () => {
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
});

afterAll(async () => {
  await db.end();
});

describe("POST /api/memories (라이브)", () => {
  it("익명으로 텍스트 메모를 만들면 201과 memoryId를 준다", async () => {
    const res = await fetch(`${BASE}/api/memories`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text: "라이브 스모크 메모" }),
    });
    expect(res.status).toBe(201);
    const { memoryId } = await res.json();
    expect(memoryId).toBeTruthy();

    const row = await db.query("select id from public.memories where id = $1", [memoryId]);
    expect(row.rowCount).toBe(1);
  });

  it("빈 본문은 400으로 거부한다", async () => {
    const res = await fetch(`${BASE}/api/memories`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("empty_memory");
  });
});
```

- [ ] **Step 3: 빌드·검사**

```powershell
npm run build
npm run check
```

Expected: 둘 다 종료 코드 0. 빌드 라우트 표에 `ƒ /api/memories`가 나타난다. `app/api/**`가 `lib/repositories/*`를 import하는데, `supabase.ts`는 ESLint 예외(auth에서 설정), `memoryRepository.ts`는? — **아래 Step 4에서 예외를 넓힌다.**

- [ ] **Step 4: ESLint 경계 예외 조정**

`route.ts`가 `createMemoryRepository`(저장소)를 직접 import한다. 이는 계층 규칙 위반이다. 그러나 Route Handler가 요청별 저장소 인스턴스를 조립하는 것은 경계의 정당한 역할이다(서비스는 프레임워크·클라이언트를 모른다). auth에서 `supabase.ts`에 준 예외와 같은 성격이다.

`eslint.config.mjs`의 `except` 배열에 추가:

```js
              except: ["./supabase.ts", "./memoryRepository.ts"],
```

재확인:

```powershell
npx eslint .
```

Expected: 종료 코드 0.

**다른 도메인 저장소는 여전히 막히는지** 프로브로 확인한다:

```powershell
"import { adminClient } from '@/lib/repositories/testSupport'; export const p = adminClient;" | Out-File app/__probe3__.ts -Encoding utf8
npx eslint app/__probe3__.ts   # 에러가 나야 정상
Remove-Item app/__probe3__.ts
```

Expected: 프로브는 에러(exit 1). 예외가 두 파일에만 뚫렸음을 확인.

- [ ] **Step 5: 라이브 스모크 실행**

```powershell
npm run build
$server = Start-Process -FilePath "cmd" -ArgumentList "/c","npx next start" -PassThru -WindowStyle Hidden
$ready=$false
for($i=0;$i -lt 30;$i++){ try { if((Invoke-WebRequest "http://localhost:3000/" -UseBasicParsing -TimeoutSec 3).StatusCode){$ready=$true;break} } catch {}; Start-Sleep -Seconds 2 }
"ready=$ready"
npx vitest run --config vitest.integration.config.mts app/api/memories/route.integration.test.ts
Stop-Process -Id $server.Id -Force
Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $PID } | Stop-Process -Force -ErrorAction SilentlyContinue
```

개발 서버는 `.env.local`의 `NEXT_PUBLIC_SUPABASE_*`를 읽으므로 그 파일이 있어야 한다(auth Task 4). Route Handler가 세션 쿠키를 발급하므로 스모크는 실제 서버에 HTTP로 쏜다.

Expected: 2 passed. 서버가 안 뜨면 `.env.local` 유무와 포트 충돌을 확인한다.

- [ ] **Step 6: 커밋**

```powershell
git add app/api/memories eslint.config.mjs package.json package-lock.json
git commit -m "feat(api): POST /api/memories 경계

zod 검증·익명 세션 보장·서비스 호출·에러 매핑. 세션이 없으면
signInAnonymously로 만든다 — 기록 시점이 세션을 만드는 유일한 지점이라
401은 발생하지 않는다. 본문·식별 정보를 응답·로그에 싣지 않는다.

라이브 스모크로 익명 생성→201→행 존재까지 통째로 검증.
Route Handler의 저장소 조립을 위해 ESLint 예외를 memoryRepository로 확장."
```

---

## Task 5: 문서

**Files:**
- Modify: `supabase/README.md`, `README.md`

- [ ] **Step 1: supabase/README에 버킷·정책 메모**

`supabase/README.md`의 인증 절 아래에 추가:

```markdown
## Storage

- 비공개 버킷 `memories`. 경로 규약 `{user_id}/{uuid}.{ext}`.
- storage.objects 정책은 테이블 RLS와 같은 원리다 — 최상위 폴더가 소유자.
  authenticated는 자기 폴더만 CRUD, update는 없음(원본 불변).
- 사진은 클라이언트가 직접 업로드하고, 서버는 경로의 본인 폴더 여부를
  검증한 뒤 assets 행을 만든다(누출 방어).
```

- [ ] **Step 2: README에 API 한 줄**

`README.md`의 저장소 구조 `app/` 줄 아래 또는 적절한 위치에 기록 API를 한 줄 남긴다. 구조 블록의 `app/` 설명을 보강:

```
app/api/memories/       # 기록 생성 API (텍스트·감정·사진)
```

- [ ] **Step 3: 전체 검사**

```powershell
npm run check
npm run test:integration
```

Expected: 둘 다 종료 코드 0.

- [ ] **Step 4: 커밋**

```powershell
git add supabase/README.md README.md
git commit -m "docs: 기록 API와 Storage 버킷 규약 안내"
```

- [ ] **Step 5: 보안 리뷰**

인증·Storage·RLS 변경이므로 `/security-review`(privacy.md). 교차 사용자 파일 접근·경로 검증·본문 로깅을 중점 확인한 뒤 병합으로 넘어간다.

- [ ] **Step 6: 브랜치 마무리**

`/superpowers:finishing-a-development-branch`. rebase 후 `merge --no-ff`, squash 금지(git.md).

---

## 완료 기준

- 텍스트·감정·사진 메모가 각각·조합으로 생성된다
- text·asset 둘 다 없으면 400
- 남의 폴더 경로를 첨부하면 400(누출 방어)
- Storage에서 A가 B의 폴더에 업로드·조회 불가
- 남의 user_id로 위조 insert 시 RLS가 차단(뮤테이션 점검으로 확인)
- 익명으로 즉시 기록됨(로그인 벽 없음)
- `npm run check`·`npm run test:integration`·`supabase db reset` 통과

## 이번 범위 밖

- 기록 화면 UI (별도 스펙)
- 삭제 경로 (Storage 완전 삭제가 워커 필요 — 스펙 §7)
- 탐지 잡 적재 (워커 없음)
- 음성·위치 (STT·동의·PostGIS)
- 타임라인 읽기 API (화면 스펙에서)
