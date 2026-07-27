# 일기 날짜 이동(`/diary/[date]`) Implementation Plan

> **실행 주체:** 이 계획은 **Codex가 구현**한다. Superpowers 스킬 없이 수동으로 수행한다 — 태스크마다 ① 실패 테스트 → ② 실패 확인 → ③ 계획의 코드 그대로 구현 → ④ 통과 확인 → ⑤ lint+build → ⑥ 그 태스크 단위로 1커밋.

**Goal:** 최신 일기 하나만 보이던 `/diary`에 과거 일기 접근을 붙인다 — `/diary/[date]`와 "존재하는 일기로 점프"하는 이전/다음 이동.

**Architecture:** 기존 `/diary`를 공통 화면 컴포넌트로 분리하고 `/diary/[date]`가 같은 것을 재사용한다. 저장소에 날짜 조회·이웃 날짜 조회를 추가하되 행→뷰 매핑은 공통 함수로 뽑는다. 스키마·API 라우트·워커 변경 없음.

**Tech Stack:** Next.js 16(App Router, `params`는 Promise) · TypeScript · Tailwind · Vitest + Testing Library

## Global Constraints

- 산출물은 **코드**다. `main` 직접 커밋 금지 — **`feat/diary-navigation` 브랜치를 `main`에서 새로 만들어** 작업한다.
- 커밋 메시지 `<type>(<scope>): <한국어 요약>`. scope는 `ui`·`docs`. **`Co-Authored-By` 트레일러는 네 것으로** 바꾼다(git.md).
- **태스크마다 커밋만. push·merge 금지**(사람이 한다).
- **앱 코드 작성 전 Next.js 16 문서**(`node_modules/next/dist/docs/01-app/`)를 확인한다. **동적 라우트의 `params`는 Promise다** — `const { date } = await params;`(기존 `app/api/differences/[id]/route.ts` 선례).
- **스키마 변경·마이그레이션·API 라우트·워커 변경 없음.** `eslint.config.mjs`도 `diaryRepository.ts`가 이미 예외에 있어 **수정 불필요**.
- **`DiaryArticle`·`EvidenceDisclosure`·`StateView`를 수정하지 마라.** 그대로 재사용한다.
- **저장소는 세션 클라이언트 + RLS.** `service_role`을 쓰지 마라.
- **잠긴(`is_locked`)·삭제된(`deleted_at`) 메모를 근거에 노출하지 마라**(privacy.md). 기존 필터를 그대로 유지한다.
- **터치 타깃 44px 이상**(`min-h-11`). `min-h-9`(36px)는 `frontend.md` 위반이다.
- **색만으로 의미를 전달하지 마라** — 이전/다음에 텍스트 라벨을 병행하고 비활성은 `aria-disabled`로 알린다.
- ⚠️ **`supabase.select()` 인자는 리터럴 타입이어야 한다.** 문자열을 `+`로 이어붙이면 타입 추론이 깨진다. 이 오류는 lint·단위 테스트로 안 잡히고 **`npm run build`(tsc)에서만** 드러난다 — **태스크마다 build를 돌려라.**
- 테스트: `npx vitest run`(단위) · `npm run lint` · `npm run build`(타입) · `npx vitest run --config vitest.integration.config.mts`(통합, 로컬 Supabase 필요).
- 완료(DoD) = lint + typecheck(build) + unit + integration. **eval은 이 기능 대상 아님**.
- 못 고치는 실패나 모호한 점이 있으면 **멈추고 보고**하라. 추측하거나 테스트를 약화시키지 마라.

## 결정 고정 (Locked Decisions — 무-추측 규약)

1. **`/diary`는 최신 일기를 계속 보여준다.** 목록으로 바꾸지 마라. 과거 접근은 `/diary/[date]`로만 붙인다.
2. **리다이렉트를 쓰지 마라.** `/diary` → 최신 날짜로 `redirect()`하면 뒤로가기가 꼬인다. 두 라우트가 각자 렌더하되 공통 컴포넌트 `DiaryScreen`을 공유한다.
3. **이전/다음은 "존재하는 일기로 점프"** 한다. 날짜−1/＋1이 아니다. `findNeighborDates`가 실제 일기가 있는 앞뒤 날짜를 준다.
4. **없는 방향은 비활성**(숨기지 않는다). 링크가 아니라 비활성 요소로 두고 `aria-disabled="true"`를 붙인다. 레이아웃이 흔들리지 않아야 한다.
5. **일기 없는 날짜·잘못된 형식 → `notFound()`.** 형식 검증은 `/^\d{4}-\d{2}-\d{2}$/` 정규식. 존재하지 않는 실제 날짜(예: `2026-13-45`)는 조회 결과 0행이라 자연히 404가 된다.
6. **select 문자열은 모듈 상수로 뽑되 `as const`를 붙인다.** 리터럴 타입이 유지돼야 supabase 타입 추론이 산다. `+` 연결 금지.
7. **행→뷰 매핑은 `toDiaryView(row)` 한 함수로 뽑는다.** `findLatest`·`findByDate`가 같은 매핑을 두 번 쓰지 않게.
8. **날짜 표시 형식은 `YYYY-MM-DD` 그대로.** 상대 표현("어제")을 계산하지 마라(사용자 타임존과 어긋날 위험, 범위 밖).
9. **`hasAnyMemory`는 `/diary`에서만 쓴다.** `/diary/[date]`는 일기가 없으면 404이므로 필요 없다.
10. **로그인하지 않았으면 `/diary`는 빈 상태**(현행 유지). `/diary/[date]`는 RLS로 0행 → 404.

## File Structure

| 경로 | 책임 |
|------|------|
| `lib/repositories/diaryRepository.ts`(수정) | `findByDate`·`findNeighborDates` 추가, 매핑·select 상수 추출 |
| `lib/repositories/diary.integration.test.ts`(수정) | 날짜 조회·이웃 점프·경계 테스트 추가 |
| `app/diary/_components/DiaryNav.tsx` | 이전/다음 이동 |
| `app/diary/_components/DiaryNav.test.tsx` | 네비게이션 단위 |
| `app/diary/_components/DiaryScreen.tsx` | 두 라우트가 공유하는 화면(제목·상태 분기·Article·Nav) |
| `app/diary/page.tsx`(수정) | 최신 조회 → `DiaryScreen` 위임 |
| `app/diary/[date]/page.tsx` | 날짜 검증·조회 → `DiaryScreen` 위임, 없으면 404 |
| `README.md`(수정) | 화면 설명 한 줄 |

---

## Task 1: 저장소 — 날짜 조회·이웃 날짜

**Files:**
- Modify: `lib/repositories/diaryRepository.ts`
- Modify: `lib/repositories/diary.integration.test.ts`

**Interfaces:**
- Produces:
  ```ts
  findByDate(date: string): Promise<DiaryView | null>
  findNeighborDates(date: string): Promise<{ prev: string | null; next: string | null }>
  ```

- [ ] **Step 1: 실패 테스트 추가**

`lib/repositories/diary.integration.test.ts`의 `describe("diaryRepository", ...)` 블록 **안 끝에** 추가한다. 기존 테스트·헬퍼는 그대로 둔다.

```ts
  it("날짜로 일기를 가져온다", async () => {
    await db.query("delete from public.diaries where user_id = $1", [bob]);
    await db.query("delete from public.memories where user_id = $1", [bob]);
    await seedDiary(bob, { memo: "날짜 조회용" });
    const today = (await db.query("select current_date::text as d")).rows[0].d;

    const repo = createDiaryRepository(await clientFor("diary-bob@example.com"));
    const view = await repo.findByDate(today);
    expect(view).not.toBeNull();
    expect(view!.date).toBe(today);
    expect(view!.evidence).toContain("날짜 조회용");
  });

  it("일기가 없는 날짜는 null", async () => {
    const repo = createDiaryRepository(await clientFor("diary-bob@example.com"));
    expect(await repo.findByDate("2020-01-01")).toBeNull();
  });

  it("이웃은 빈 날을 건너뛰고 존재하는 일기로 점프한다", async () => {
    await db.query("delete from public.diaries where user_id = $1", [alice]);
    // 7/10, 7/20, 7/30 — 사이 날짜엔 일기가 없다
    for (const d of ["2026-07-10", "2026-07-20", "2026-07-30"]) {
      await db.query(
        "insert into public.diaries (user_id, date, status, generated_text) values ($1,$2,'draft','본문')",
        [alice, d],
      );
    }
    const repo = createDiaryRepository(await clientFor("diary-alice@example.com"));
    const mid = await repo.findNeighborDates("2026-07-20");
    expect(mid.prev).toBe("2026-07-10");
    expect(mid.next).toBe("2026-07-30");
  });

  it("가장 오래된·최신 일기에서 경계는 null", async () => {
    const repo = createDiaryRepository(await clientFor("diary-alice@example.com"));
    const oldest = await repo.findNeighborDates("2026-07-10");
    expect(oldest.prev).toBeNull();
    expect(oldest.next).toBe("2026-07-20");

    const newest = await repo.findNeighborDates("2026-07-30");
    expect(newest.prev).toBe("2026-07-20");
    expect(newest.next).toBeNull();
  });

  it("타 사용자 일기는 이웃으로 잡히지 않는다", async () => {
    await db.query("delete from public.diaries where user_id = $1", [bob]);
    await db.query(
      "insert into public.diaries (user_id, date, status, generated_text) values ($1,'2026-07-20','draft','밥의 일기')",
      [bob],
    );
    // alice의 일기는 7/10·7/20·7/30 — bob은 7/20 하나뿐이라 이웃이 없어야 한다
    const repo = createDiaryRepository(await clientFor("diary-bob@example.com"));
    const neighbors = await repo.findNeighborDates("2026-07-20");
    expect(neighbors.prev).toBeNull();
    expect(neighbors.next).toBeNull();
  });
```

- [ ] **Step 2: 실패 확인**

```powershell
npx vitest run --config vitest.integration.config.mts lib/repositories/diary.integration.test.ts
```
Expected: 새 5건 FAIL — `repo.findByDate is not a function`.

- [ ] **Step 3: 구현 — 상수·매핑 추출 + 두 메서드 추가**

`lib/repositories/diaryRepository.ts`를 아래로 **교체**한다(기존 `findLatest`·`hasAnyMemory` 동작은 그대로, 매핑만 함수로 빠진다):

```ts
import type { SupabaseClient } from "@supabase/supabase-js";
import type { DiaryView } from "@/lib/services/diary";

type SectionRow = { section_type: string; content: string };
type SourceRow = {
  memories: {
    raw_text: string | null;
    is_locked: boolean;
    deleted_at: string | null;
  } | null;
};

// `as const`로 리터럴 타입을 유지한다. 문자열을 `+`로 이어붙이거나 리터럴
// 타입을 잃으면 supabase-js의 select 타입 추론이 깨져 row.diary_sections가
// GenericStringError가 된다(tsc에서만 드러남).
const DIARY_SELECT =
  "date, status, generated_text, edited_text, diary_sections(section_type, content), diary_sources(memories(raw_text, is_locked, deleted_at))" as const;

/** 조회 행 하나를 표시용 뷰로 옮긴다. findLatest·findByDate가 공유한다. */
function toDiaryView(row: {
  date: unknown;
  status: unknown;
  generated_text: unknown;
  edited_text: unknown;
  diary_sections: unknown;
  diary_sources: unknown;
}): DiaryView {
  const sections = (row.diary_sections ?? []) as unknown as SectionRow[];
  const sources = (row.diary_sources ?? []) as unknown as SourceRow[];

  return {
    date: row.date as string,
    oneLine:
      sections.find((section) => section.section_type === "오늘의한문장")
        ?.content ?? "",
    body:
      (row.edited_text as string | null) ??
      (row.generated_text as string | null) ??
      "",
    differences: sections
      .filter((section) => section.section_type === "다른점")
      .map((section) => section.content),
    // 잠긴·삭제된·빈 메모는 노출하지 않는다(privacy.md).
    evidence: sources
      .map((source) => source.memories)
      .filter(
        (
          memory,
        ): memory is {
          raw_text: string;
          is_locked: boolean;
          deleted_at: string | null;
        } =>
          !!memory &&
          !memory.is_locked &&
          !memory.deleted_at &&
          !!memory.raw_text &&
          memory.raw_text.trim().length > 0,
      )
      .map((memory) => memory.raw_text),
    isEdited: (row.status as string) !== "draft",
  };
}

/** 세션 클라이언트로 일기를 조회한다. RLS(diaries=본인, sections/sources=부모 소유자)가
 * 소유권을 강제하므로 service_role을 쓰지 않는다. */
export function createDiaryRepository(client: SupabaseClient) {
  return {
    /** 가장 최근 일기 하나. run-diary는 '어제'를 대상으로 돌기 때문에
     * 오늘 날짜로 찾지 않고 최신 하나를 가져온다. */
    async findLatest(): Promise<DiaryView | null> {
      const { data, error } = await client
        .from("diaries")
        .select(DIARY_SELECT)
        .order("date", { ascending: false })
        .limit(1);
      if (error) throw error;
      const row = data?.[0];
      return row ? toDiaryView(row) : null;
    },

    /** 그 날짜의 일기. 없으면 null(호출자가 404로 처리한다). */
    async findByDate(date: string): Promise<DiaryView | null> {
      const { data, error } = await client
        .from("diaries")
        .select(DIARY_SELECT)
        .eq("date", date)
        .limit(1);
      if (error) throw error;
      const row = data?.[0];
      return row ? toDiaryView(row) : null;
    },

    /** 기준 날짜의 앞뒤로 **실제 일기가 있는** 날짜. 날짜-1이 아니라
     * 존재하는 일기로 점프하기 위한 것이다(빈 날엔 일기가 없다). */
    async findNeighborDates(
      date: string,
    ): Promise<{ prev: string | null; next: string | null }> {
      const [prevResult, nextResult] = await Promise.all([
        client
          .from("diaries")
          .select("date")
          .lt("date", date)
          .order("date", { ascending: false })
          .limit(1),
        client
          .from("diaries")
          .select("date")
          .gt("date", date)
          .order("date", { ascending: true })
          .limit(1),
      ]);
      if (prevResult.error) throw prevResult.error;
      if (nextResult.error) throw nextResult.error;
      return {
        prev: (prevResult.data?.[0]?.date as string | undefined) ?? null,
        next: (nextResult.data?.[0]?.date as string | undefined) ?? null,
      };
    },

    /** 일기 재료가 될 수 있는 기록이 하나라도 있는가.
     * '기록도 없음'과 '기록은 있는데 일기가 아직 없음'을 가르는 데만 쓴다. */
    async hasAnyMemory(): Promise<boolean> {
      const { data, error } = await client
        .from("memories")
        .select("id")
        .is("deleted_at", null)
        .eq("is_locked", false)
        .not("raw_text", "is", null)
        .neq("raw_text", "")
        .limit(1);
      if (error) throw error;
      return (data?.length ?? 0) > 0;
    },
  };
}
```

- [ ] **Step 4: 통과 확인 + 빌드**

```powershell
npx vitest run --config vitest.integration.config.mts lib/repositories/diary.integration.test.ts
npm run lint
npm run build
```
Expected: 통합 10건(기존 5 + 새 5) PASS, lint 통과, **build 통과**(타입 추론이 살아 있는지 확인).

- [ ] **Step 5: 커밋**

```powershell
git add lib/repositories/diaryRepository.ts lib/repositories/diary.integration.test.ts
git commit -m "feat(ui): 일기 날짜 조회·이웃 날짜

findByDate와 findNeighborDates를 추가한다. 이웃은 날짜-1이 아니라 실제
일기가 있는 앞뒤 날짜다 — 빈 날엔 일기가 없어 날짜 단위로 넘기면 계속
지나가야 한다. 행→뷰 매핑을 toDiaryView로 뽑아 두 조회가 공유한다."
```

---

## Task 2: 이전/다음 이동 컴포넌트

**Files:**
- Create: `app/diary/_components/DiaryNav.tsx`, `app/diary/_components/DiaryNav.test.tsx`

**Interfaces:**
- Produces: `export function DiaryNav({ prev, next }: { prev: string | null; next: string | null })`

- [ ] **Step 1: 실패 테스트 작성**

`app/diary/_components/DiaryNav.test.tsx`:

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiaryNav } from "./DiaryNav";

describe("DiaryNav", () => {
  it("이전·다음 일기로 가는 링크를 보여준다", () => {
    render(<DiaryNav prev="2026-07-10" next="2026-07-30" />);
    expect(screen.getByRole("link", { name: "이전 일기" })).toHaveAttribute(
      "href",
      "/diary/2026-07-10",
    );
    expect(screen.getByRole("link", { name: "다음 일기" })).toHaveAttribute(
      "href",
      "/diary/2026-07-30",
    );
  });

  it("이전 일기가 없으면 링크가 아니라 비활성이다", () => {
    render(<DiaryNav prev={null} next="2026-07-30" />);
    expect(screen.queryByRole("link", { name: "이전 일기" })).not.toBeInTheDocument();
    // 사라지지 않고 경계임을 알린다(색만으로 전달하지 않음)
    expect(screen.getByText("이전 일기")).toHaveAttribute("aria-disabled", "true");
  });

  it("다음 일기가 없으면 링크가 아니라 비활성이다", () => {
    render(<DiaryNav prev="2026-07-10" next={null} />);
    expect(screen.queryByRole("link", { name: "다음 일기" })).not.toBeInTheDocument();
    expect(screen.getByText("다음 일기")).toHaveAttribute("aria-disabled", "true");
  });

  it("44px 터치 타깃을 만족한다", () => {
    render(<DiaryNav prev="2026-07-10" next="2026-07-30" />);
    expect(screen.getByRole("link", { name: "이전 일기" }).className).toContain("min-h-11");
    expect(screen.getByRole("link", { name: "다음 일기" }).className).toContain("min-h-11");
  });
});
```

- [ ] **Step 2: 실패 확인**

```powershell
npx vitest run app/diary/_components/DiaryNav.test.tsx
```
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 구현 작성**

`app/diary/_components/DiaryNav.tsx`:

```tsx
import Link from "next/link";

/** 존재하는 이전/다음 일기로 이동한다(날짜-1이 아니다).
 * 없는 방향은 숨기지 않고 비활성으로 둔다 — 경계임을 알리고 레이아웃도 안 흔들린다.
 * 방향을 화살표만으로 전달하지 않고 텍스트 라벨을 쓴다(frontend.md). */
const ITEM = "min-h-11 flex-1 rounded-lg border px-3 py-2 text-[15px]";

export function DiaryNav({ prev, next }: { prev: string | null; next: string | null }) {
  return (
    <nav className="mt-8 flex gap-2">
      {prev ? (
        <Link href={`/diary/${prev}`} className={`${ITEM} text-left`}>
          이전 일기
        </Link>
      ) : (
        <span aria-disabled="true" className={`${ITEM} text-left text-muted-foreground opacity-50`}>
          이전 일기
        </span>
      )}
      {next ? (
        <Link href={`/diary/${next}`} className={`${ITEM} text-right`}>
          다음 일기
        </Link>
      ) : (
        <span aria-disabled="true" className={`${ITEM} text-right text-muted-foreground opacity-50`}>
          다음 일기
        </span>
      )}
    </nav>
  );
}
```

- [ ] **Step 4: 통과 확인 + 빌드**

```powershell
npx vitest run app/diary/_components/DiaryNav.test.tsx
npm run lint
npm run build
```
Expected: 4건 PASS, lint·build 통과.

- [ ] **Step 5: 커밋**

```powershell
git add app/diary/_components/DiaryNav.tsx app/diary/_components/DiaryNav.test.tsx
git commit -m "feat(ui): 일기 이전/다음 이동

존재하는 이전·다음 일기로 점프한다. 없는 방향은 숨기지 않고 비활성으로
둬 경계임을 알린다(aria-disabled, 색만으로 전달하지 않음). 44px 터치 타깃."
```

---

## Task 3: 공통 화면 + 두 라우트 배선

**Files:**
- Create: `app/diary/_components/DiaryScreen.tsx`, `app/diary/[date]/page.tsx`
- Modify: `app/diary/page.tsx`

**Interfaces:**
- Consumes: Task 1 저장소, Task 2 `DiaryNav`, 기존 `DiaryArticle`·`EmptyState`
- Produces: `export function DiaryScreen({ diary, hasMemory, neighbors })`

- [ ] **Step 1: 공통 화면 작성**

`app/diary/_components/DiaryScreen.tsx`:

```tsx
import type { DiaryView } from "@/lib/services/diary";
import { EmptyState } from "@/components/common/StateView";
import { DiaryArticle } from "./DiaryView";
import { DiaryNav } from "./DiaryNav";

/** /diary와 /diary/[date]가 공유하는 화면. 리다이렉트 대신 이 컴포넌트를
 * 공유해 표시·상태 분기 로직이 두 곳으로 갈라지지 않게 한다. */
export function DiaryScreen({
  diary,
  hasMemory,
  neighbors,
}: {
  diary: DiaryView | null;
  hasMemory: boolean;
  neighbors: { prev: string | null; next: string | null };
}) {
  return (
    <main className="mx-auto max-w-md p-4">
      <h1 className="mb-4 text-lg font-medium">일기</h1>
      {diary ? (
        <>
          <DiaryArticle diary={diary} />
          <DiaryNav prev={neighbors.prev} next={neighbors.next} />
        </>
      ) : hasMemory ? (
        // 일기가 없을 때, 기록조차 없는 경우와 '아직 안 만들어진' 경우를 구분한다.
        // 섞으면 사용자가 "내가 기록을 안 했나?"로 오해한다.
        <EmptyState message="아직 일기가 만들어지지 않았어요" />
      ) : (
        <EmptyState message="아직 쌓인 기록이 없어요" />
      )}
    </main>
  );
}
```

- [ ] **Step 2: `/diary` 축소**

`app/diary/page.tsx`를 아래로 **교체**한다:

```tsx
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";
import { DiaryScreen } from "./_components/DiaryScreen";

export default async function DiaryPage() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const repo = createDiaryRepository(supabase);
  const diary = user ? await repo.findLatest() : null;
  const hasMemory = user && !diary ? await repo.hasAnyMemory() : false;
  const neighbors = diary
    ? await repo.findNeighborDates(diary.date)
    : { prev: null, next: null };

  return <DiaryScreen diary={diary} hasMemory={hasMemory} neighbors={neighbors} />;
}
```

- [ ] **Step 3: `/diary/[date]` 작성**

`app/diary/[date]/page.tsx`:

```tsx
import { notFound } from "next/navigation";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";
import { DiaryScreen } from "../_components/DiaryScreen";

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

export default async function DiaryDatePage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  // Next.js 16에서 동적 라우트 params는 Promise다.
  const { date } = await params;
  if (!DATE_PATTERN.test(date)) notFound();

  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const repo = createDiaryRepository(supabase);
  const diary = user ? await repo.findByDate(date) : null;
  // 기준 일기가 없으면 이전/다음의 기준점도 없다 — 빈 상태 대신 404가 맞다.
  if (!diary) notFound();

  const neighbors = await repo.findNeighborDates(diary.date);
  return <DiaryScreen diary={diary} hasMemory={false} neighbors={neighbors} />;
}
```

- [ ] **Step 4: 전체 검사**

```powershell
npm run lint
npm run build
npx vitest run
```
Expected: lint 통과, build 통과(`/diary`와 `/diary/[date]` 두 라우트가 보인다), 단위 전체 통과(기존 49 + `DiaryNav` 4 = 53).

- [ ] **Step 5: 육안 확인(선택)**

```powershell
npm run dev
```
`/diary`에서 최신 일기와 이전/다음 버튼이 보이는지, 이전 일기가 없으면 비활성인지 확인한다.
**`run-diary`를 실행하지 마라(실 LLM 비용).** 일기가 필요하면 사람에게 요청하라.

- [ ] **Step 6: 커밋**

```powershell
git add app/diary/_components/DiaryScreen.tsx app/diary/page.tsx "app/diary/[date]/page.tsx"
git commit -m "feat(ui): 일기 날짜 라우트와 공통 화면

/diary는 최신을 유지하고 /diary/[date]를 추가한다. 두 라우트가 DiaryScreen을
공유해 상태 분기가 갈라지지 않게 한다(리다이렉트는 뒤로가기가 꼬여 쓰지 않음).
일기 없는 날짜·잘못된 형식은 404 — 기준 일기가 없으면 이전/다음 기준점도 없다."
```

---

## Task 4: 문서

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 화면 설명 갱신**

`README.md`에서 일기 화면을 설명하는 줄(`일기 화면(/diary)은 ...`)을 아래로 **교체**한다:

```markdown
일기 화면(`/diary`)은 가장 최근 일기를 읽기 전용으로 보여주고, 무엇을 보고 썼는지(근거 메모)를 접어서 함께 제공한다. 이전/다음 버튼으로 과거 일기(`/diary/[date]`)를 오갈 수 있으며, 일기가 없는 날은 건너뛰고 실제 일기가 있는 날짜로 점프한다. 일기 생성은 `run-diary`(§4)가 하며 화면에서 트리거하지 않는다.
```

- [ ] **Step 2: 저장소 구조 갱신**

`README.md`의 저장소 구조 블록에서 `app/diary/` 줄을 아래로 **교체**한다:

```
app/diary/              # 일기 보기 (최신 · 근거 접기 · 날짜 이동 /diary/[date])
```

- [ ] **Step 3: 전체 검사**

```powershell
npm run lint
npm run build
npx vitest run
npx vitest run --config vitest.integration.config.mts
```
Expected: 전부 통과.

- [ ] **Step 4: 커밋**

```powershell
git add README.md
git commit -m "docs: 일기 날짜 이동 안내"
```

- [ ] **Step 5: 최종 보고**

`HANDOFF.md`의 "상태" 절을 갱신하고 커밋한다(무엇을 했는지·태스크별 커밋 SHA·검증 결과·막힌 점). **push·merge는 하지 마라** — 사람이 한다.

---

## 완료 기준

- `/diary`가 최신 일기와 이전/다음 이동을 보여준다.
- `/diary/[date]`가 그 날짜 일기를 보여주고, 없는 날짜·잘못된 형식은 404.
- **이전/다음이 빈 날을 건너뛰고 존재하는 일기로 점프한다**(통합 테스트).
- 경계(가장 오래된·최신)에서 해당 방향이 **비활성**이고 `aria-disabled`가 붙는다.
- 타 사용자 일기가 이웃으로 잡히지 않는다(RLS 통합 테스트).
- 44px 터치 타깃. lint + build + unit + integration 전부 통과.
- 스키마·API 라우트·워커·`eslint.config.mjs` 변경 없음.

## 이번 범위 밖
- 목록 화면 · 달력 UI · 페이지네이션.
- 일기 편집·확정 · 공유·내보내기.
- 스키마·API 라우트·워커 변경.
