# 일기 보기 화면(`/diary`) Implementation Plan

> **실행 주체:** 이 계획은 **Codex가 구현**한다. Superpowers 스킬 없이 수동으로 수행한다 — 태스크마다 ① 실패 테스트 → ② 실패 확인 → ③ 계획의 코드 그대로 구현 → ④ 통과 확인 → ⑤ lint → ⑥ 그 태스크 단위로 1커밋.

**Goal:** 파이프라인이 만든 일기를 사용자가 볼 수 있게 한다 — 가장 최근 일기 하나를 읽기 전용으로, 근거 메모는 접어서.

**Architecture:** `/review`와 동일한 패턴. 서버 컴포넌트가 세션 클라이언트로 저장소를 부르고(RLS가 소유권 강제), 표시는 클라이언트 컴포넌트가 맡는다. 스키마·API 라우트·워커 변경 없음.

**Tech Stack:** Next.js 16(App Router) · TypeScript · Tailwind · shadcn/ui · Vitest + Testing Library

## Global Constraints

- 산출물은 **코드**다. `main` 직접 커밋 금지 — **`feat/diary-view` 브랜치를 `main`에서 새로 만들어** 작업한다.
- 커밋 메시지 `<type>(<scope>): <한국어 요약>`. scope는 `ui`·`docs`. **`Co-Authored-By` 트레일러는 네 것으로** 바꾼다(git.md).
- **태스크마다 커밋만. push·merge 금지**(사람이 한다).
- **앱 코드 작성 전 Next.js 16 문서**(`node_modules/next/dist/docs/01-app/`)를 확인한다 — 학습데이터와 API·관례가 다르다.
- **스키마 변경·마이그레이션·API 라우트·워커 변경 없음.** 읽기 전용 프론트 슬라이스다.
- **`components/common/StateView.tsx`를 수정하지 마라.** 미생성 상태는 기존 `EmptyState`에 `message`를 넘겨 쓴다(중복 컴포넌트 금지).
- **저장소는 세션 클라이언트 + RLS**를 쓴다. `service_role`을 쓰지 마라(`differenceRepository` 선례).
- **잠긴(`is_locked`)·삭제된(`deleted_at`)·본문이 공백인 메모는 근거에서 제외**한다(privacy.md).
- **죄책감 유도 문구 금지**(frontend.md): "일기를 써보세요"·"N일째" 같은 독려·압박 표현을 쓰지 마라.
- **터치 타깃 44px 이상** — 토글 버튼은 `min-h-11`(`ConfirmActions` 선례). `min-h-9`(36px)를 쓰지 마라.
- **색만으로 의미를 전달하지 마라** — 라벨을 병행한다.
- 테스트: `npx vitest run`(단위) · `npm run lint` · `npm run build`(타입) · `npx vitest run --config vitest.integration.config.mts`(통합, 로컬 Supabase 필요).
- 완료(DoD) = lint + typecheck(build) + unit + integration.
- 못 고치는 실패나 모호한 점이 있으면 **멈추고 보고**하라. 추측하거나 테스트를 약화시키지 마라.

## 결정 고정 (Locked Decisions — 무-추측 규약)

1. **"오늘"이 아니라 "가장 최근"이다.** `run-diary`는 사용자 로컬 어제를 대상으로 돌아 최신 일기는 보통 어제 것이다. 날짜로 필터하지 말고 `order("date", {ascending:false}).limit(1)`로 최신 하나를 가져온다.
2. **본문 = `edited_text ?? generated_text ?? ""`.** 사용자 편집본이 있으면 그것이 우선이다.
3. **`isEdited = status !== "draft"`.** `edited`·`confirmed`면 true. 생성물 표식 문구가 이 값으로 갈린다 — 편집본을 "AI가 쓴 초안"이라 하면 거짓이다.
4. **`oneLine`이 없으면 빈 문자열**이고, 빈 문자열이면 그 영역을 렌더하지 않는다.
5. **`hasAnyMemory`는 "일기 재료가 될 수 있는 기록"을 센다** — `deleted_at is null AND is_locked = false AND raw_text is not null AND raw_text <> ''`. 이 조건이어야 "메모는 있는데 일기가 없다"는 메시지가 정직하다. (공백만 있는 본문까지 거르지는 않는다 — 기록 폼이 빈 제출을 막으므로 실사용에서 발생하지 않고, 여기서 판정을 더 정교하게 만들 이득이 없다.)
6. **근거가 0건이면 접기 UI 자체를 렌더하지 않는다**(빈 서랍을 보여주지 않는다).
7. **접기 기본 상태는 닫힘.** 토글은 `<button aria-expanded>`로 상태를 알린다.
8. **날짜 표시 형식은 `YYYY-MM-DD` 그대로** 쓴다. 상대 표현("어제")을 계산하지 마라 — 사용자 타임존과 어긋날 위험이 있고 이번 범위 밖이다.
9. **API 라우트를 만들지 마라.** 서버 컴포넌트가 저장소를 직접 부른다(`/review` 선례).
10. **로그인하지 않았으면 빈 상태**로 처리한다(`/review`가 `user ? ... : []`로 하는 것과 동일). 리다이렉트·로그인 유도를 넣지 마라.
11. **장식 문자를 접근 가능한 텍스트에 넣지 마라.** 불릿·구분자는 CSS(`list-disc`·`::before`)로 그린다. 문자로 넣으면 스크린리더가 읽고 `getByText` 정확 일치도 깨진다. **계획 예시 코드와 접근성 규칙이 어긋나면 규칙이 이긴다** — 예시 코드는 출발점이지 근거가 아니다(record-screen의 44px 선례와 동일).

## File Structure

| 경로 | 책임 |
|------|------|
| `lib/services/diary.ts` | 표시용 타입 `DiaryView` |
| `lib/repositories/diaryRepository.ts` | 최신 일기 조회·근거 필터·메모 존재 확인(세션 RLS) |
| `lib/repositories/diary.integration.test.ts` | 저장소 통합(RLS·잠금 필터·편집본) |
| `app/diary/_components/EvidenceDisclosure.tsx` | 근거 메모 접기(클라이언트) |
| `app/diary/_components/EvidenceDisclosure.test.tsx` | 접기 단위 |
| `app/diary/_components/DiaryView.tsx` | 일기 본문·한 문장·다른 점·생성물 표식 |
| `app/diary/_components/DiaryView.test.tsx` | 표시 단위 |
| `app/diary/page.tsx` | 서버 컴포넌트, 상태 분기 |
| `app/diary/loading.tsx` · `app/diary/error.tsx` | 로딩·에러 |
| `README.md`(수정) | 저장소 구조에 화면 추가 |

---

## Task 1: 타입 + 저장소

**Files:**
- Create: `lib/services/diary.ts`, `lib/repositories/diaryRepository.ts`, `lib/repositories/diary.integration.test.ts`

**Interfaces:**
- Consumes: `@supabase/supabase-js` `SupabaseClient`
- Produces:
  ```ts
  export interface DiaryView {
    date: string; oneLine: string; body: string;
    differences: string[]; evidence: string[]; isEdited: boolean;
  }
  export function createDiaryRepository(client: SupabaseClient): {
    findLatest(): Promise<DiaryView | null>;
    hasAnyMemory(): Promise<boolean>;
  }
  ```

- [ ] **Step 1: 실패 테스트 작성**

`lib/repositories/diary.integration.test.ts`:

```ts
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { Client } from "pg";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { adminClient, SUPABASE_URL, ANON_KEY } from "./testSupport";
import { createDiaryRepository } from "./diaryRepository";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let admin: SupabaseClient, db: Client, alice: string, bob: string;

async function clientFor(email: string): Promise<SupabaseClient> {
  const { data } = await admin.auth.admin.generateLink({ type: "magiclink", email });
  const c = createClient(SUPABASE_URL, ANON_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  await c.auth.verifyOtp({ token_hash: data.properties.hashed_token, type: "magiclink" });
  return c;
}

/** 메모 1건 + 일기(섹션·출처 포함)를 만든다. 반환: diary id */
async function seedDiary(
  user: string,
  opts: { body?: string; edited?: string | null; status?: string; memo?: string; locked?: boolean } = {},
): Promise<string> {
  const {
    body = "특별할 것 없는 하루였다.", edited = null, status = "draft",
    memo = "점심 김밥", locked = false,
  } = opts;
  const mem = (await db.query(
    "insert into public.memories (user_id, raw_text, source_type, memory_type, is_locked) " +
      "values ($1,$2,'manual','moment',$3) returning id",
    [user, memo, locked],
  )).rows[0].id;
  const diary = (await db.query(
    "insert into public.diaries (user_id, date, status, generated_text, edited_text) " +
      "values ($1, current_date, $2, $3, $4) returning id",
    [user, status, body, edited],
  )).rows[0].id;
  await db.query(
    "insert into public.diary_sections (diary_id, section_type, content) values ($1,'오늘의한문장',$2), ($1,'본문',$3)",
    [diary, "비슷한 하루.", body],
  );
  await db.query(
    "insert into public.diary_sections (diary_id, section_type, content) values ($1,'다른점',$2)",
    [diary, "평소보다 일찍 퇴근"],
  );
  await db.query("insert into public.diary_sources (diary_id, memory_id) values ($1,$2)", [diary, mem]);
  return diary;
}

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
  alice = (await admin.auth.admin.createUser({ email: "diary-alice@example.com", email_confirm: true }))
    .data.user!.id;
  bob = (await admin.auth.admin.createUser({ email: "diary-bob@example.com", email_confirm: true }))
    .data.user!.id;
});

afterAll(async () => {
  await admin.auth.admin.deleteUser(alice);
  await admin.auth.admin.deleteUser(bob);
  await db.end();
});

describe("diaryRepository", () => {
  it("최신 일기를 섹션·근거와 함께 가져온다", async () => {
    await seedDiary(alice);
    const repo = createDiaryRepository(await clientFor("diary-alice@example.com"));
    const view = await repo.findLatest();
    expect(view).not.toBeNull();
    expect(view!.oneLine).toBe("비슷한 하루.");
    expect(view!.body).toBe("특별할 것 없는 하루였다.");
    expect(view!.differences).toContain("평소보다 일찍 퇴근");
    expect(view!.evidence).toContain("점심 김밥");
    expect(view!.isEdited).toBe(false);
  });

  it("편집본이 있으면 그것을 본문으로 쓴다", async () => {
    await db.query("delete from public.diaries where user_id = $1", [bob]);
    await seedDiary(bob, { edited: "내가 고친 본문", status: "edited", memo: "저녁 산책" });
    const repo = createDiaryRepository(await clientFor("diary-bob@example.com"));
    const view = await repo.findLatest();
    expect(view!.body).toBe("내가 고친 본문");
    expect(view!.isEdited).toBe(true);
  });

  it("잠긴 메모는 근거에서 빠진다", async () => {
    await db.query("delete from public.diaries where user_id = $1", [bob]);
    await db.query("delete from public.memories where user_id = $1", [bob]);
    await seedDiary(bob, { memo: "비밀 기록", locked: true });
    const repo = createDiaryRepository(await clientFor("diary-bob@example.com"));
    const view = await repo.findLatest();
    expect(view!.evidence).toEqual([]);
  });

  it("타 사용자 일기는 보이지 않는다", async () => {
    await db.query("delete from public.diaries where user_id = $1", [bob]);
    await db.query("delete from public.memories where user_id = $1", [bob]);
    const repo = createDiaryRepository(await clientFor("diary-bob@example.com"));
    expect(await repo.findLatest()).toBeNull();
  });

  it("일기 재료가 될 메모가 있는지 판정한다", async () => {
    await db.query("delete from public.memories where user_id = $1", [bob]);
    const repo = createDiaryRepository(await clientFor("diary-bob@example.com"));
    expect(await repo.hasAnyMemory()).toBe(false);
    await db.query(
      "insert into public.memories (user_id, raw_text, source_type, memory_type) values ($1,'뭔가 남김','manual','moment')",
      [bob],
    );
    expect(await repo.hasAnyMemory()).toBe(true);
  });
});
```

- [ ] **Step 2: 실패 확인**

```powershell
npx vitest run --config vitest.integration.config.mts lib/repositories/diary.integration.test.ts
```
Expected: FAIL — `Failed to resolve import "./diaryRepository"`.

- [ ] **Step 3: 구현 작성**

`lib/services/diary.ts`:

```ts
/** 일기 보기 화면 표시용 타입. 원본(evidence)과 AI 생성물(body 등)을 함께 담되
 * 화면에서 시각적으로 구분한다(frontend.md). */
export interface DiaryView {
  /** YYYY-MM-DD */
  date: string;
  /** 오늘의 한 문장. 없으면 빈 문자열 */
  oneLine: string;
  /** edited_text가 있으면 그것, 없으면 generated_text */
  body: string;
  /** 일기에 녹아든 확정 차이 */
  differences: string[];
  /** 근거 메모 본문(잠금·삭제·공백 제외) */
  evidence: string[];
  /** 사용자가 손댄 일기인가(status !== 'draft') */
  isEdited: boolean;
}
```

`lib/repositories/diaryRepository.ts`:

```ts
import type { SupabaseClient } from "@supabase/supabase-js";
import type { DiaryView } from "@/lib/services/diary";

type SectionRow = { section_type: string; content: string };
type SourceRow = {
  memories: { raw_text: string | null; is_locked: boolean; deleted_at: string | null } | null;
};

/** 세션 클라이언트로 일기를 조회한다. RLS(diaries=본인, sections/sources=부모 소유자)가
 * 소유권을 강제하므로 service_role을 쓰지 않는다. */
export function createDiaryRepository(client: SupabaseClient) {
  return {
    /** 가장 최근 일기 하나. run-diary는 '어제'를 대상으로 돌기 때문에
     * 오늘 날짜로 찾지 않고 최신 하나를 가져온다. */
    async findLatest(): Promise<DiaryView | null> {
      const { data, error } = await client
        .from("diaries")
        .select(
          "date, status, generated_text, edited_text, " +
            "diary_sections(section_type, content), " +
            "diary_sources(memories(raw_text, is_locked, deleted_at))",
        )
        .order("date", { ascending: false })
        .limit(1);
      if (error) throw error;
      const row = data?.[0];
      if (!row) return null;

      const sections = (row.diary_sections ?? []) as unknown as SectionRow[];
      const sources = (row.diary_sources ?? []) as unknown as SourceRow[];

      return {
        date: row.date as string,
        oneLine: sections.find((s) => s.section_type === "오늘의한문장")?.content ?? "",
        body: (row.edited_text as string | null) ?? (row.generated_text as string | null) ?? "",
        differences: sections.filter((s) => s.section_type === "다른점").map((s) => s.content),
        // 잠긴·삭제된·빈 메모는 노출하지 않는다(privacy.md).
        evidence: sources
          .map((s) => s.memories)
          .filter(
            (m): m is { raw_text: string; is_locked: boolean; deleted_at: string | null } =>
              !!m && !m.is_locked && !m.deleted_at && !!m.raw_text && m.raw_text.trim().length > 0,
          )
          .map((m) => m.raw_text),
        isEdited: (row.status as string) !== "draft",
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

- [ ] **Step 4: 통과 확인**

```powershell
npx vitest run --config vitest.integration.config.mts lib/repositories/diary.integration.test.ts
npm run lint
```
Expected: 5건 PASS, lint 통과.

- [ ] **Step 5: 커밋**

```powershell
git add lib/services/diary.ts lib/repositories/diaryRepository.ts lib/repositories/diary.integration.test.ts
git commit -m "feat(ui): 일기 조회 저장소 — 최신 일기·근거 필터

세션 클라이언트+RLS로 최신 일기 하나를 섹션·근거와 함께 읽는다.
run-diary가 어제를 대상으로 돌아 오늘 날짜가 아니라 최신 하나를 가져온다.
잠긴·삭제된·빈 메모는 근거에서 제외한다(privacy.md)."
```

---

## Task 2: 근거 접기 컴포넌트

**Files:**
- Create: `app/diary/_components/EvidenceDisclosure.tsx`, `app/diary/_components/EvidenceDisclosure.test.tsx`

**Interfaces:**
- Produces: `export function EvidenceDisclosure({ items }: { items: string[] }): JSX.Element | null`

- [ ] **Step 1: 실패 테스트 작성**

`app/diary/_components/EvidenceDisclosure.test.tsx`:

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EvidenceDisclosure } from "./EvidenceDisclosure";

describe("EvidenceDisclosure", () => {
  it("기본은 닫혀 있고 원본을 보여주지 않는다", () => {
    render(<EvidenceDisclosure items={["점심 김밥"]} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("점심 김밥")).not.toBeInTheDocument();
  });

  it("펼치면 원본과 원본 표식을 함께 보여준다", async () => {
    render(<EvidenceDisclosure items={["점심 김밥"]} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("점심 김밥")).toBeInTheDocument();
    // 색만으로 구분하지 않는다 — 원본임을 라벨로 밝힌다
    expect(screen.getByText("내가 남긴 기록")).toBeInTheDocument();
  });

  it("근거가 없으면 아무것도 렌더하지 않는다", () => {
    const { container } = render(<EvidenceDisclosure items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("토글 버튼이 44px 터치 타깃을 만족한다", () => {
    render(<EvidenceDisclosure items={["점심 김밥"]} />);
    expect(screen.getByRole("button").className).toContain("min-h-11");
  });
});
```

- [ ] **Step 2: 실패 확인**

```powershell
npx vitest run app/diary/_components/EvidenceDisclosure.test.tsx
```
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 구현 작성**

`app/diary/_components/EvidenceDisclosure.tsx`:

```tsx
"use client";
import { useState } from "react";

/** 일기가 무엇을 보고 쓰였는지 펼쳐 볼 수 있게 한다(추적성).
 * 펼친 내용은 사용자 원본이므로 AI 생성물과 시각·라벨로 구분한다(frontend.md). */
export function EvidenceDisclosure({ items }: { items: string[] }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null; // 빈 서랍을 보여주지 않는다

  return (
    <section className="mt-6">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="min-h-11 w-full rounded-lg border px-3 text-left text-[15px] text-muted-foreground"
      >
        {open ? "근거 접기" : `무엇을 보고 썼는지 보기 (${items.length})`}
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          <p className="text-xs text-muted-foreground">내가 남긴 기록</p>
          {items.map((text, i) => (
            <p key={i} className="rounded-lg bg-muted px-3 py-2 text-[15px] whitespace-pre-wrap">
              {text}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: 통과 확인**

```powershell
npx vitest run app/diary/_components/EvidenceDisclosure.test.tsx
npm run lint
```
Expected: 4건 PASS, lint 통과.

- [ ] **Step 5: 커밋**

```powershell
git add app/diary/_components/EvidenceDisclosure.tsx app/diary/_components/EvidenceDisclosure.test.tsx
git commit -m "feat(ui): 근거 메모 접기

일기가 무엇을 보고 쓰였는지 펼쳐 볼 수 있게 한다. 펼친 내용은 사용자
원본이라 '내가 남긴 기록' 라벨로 생성물과 구분한다. 기본 닫힘,
aria-expanded로 상태를 알리고 토글은 44px 터치 타깃."
```

---

## Task 3: 일기 표시 컴포넌트

**Files:**
- Create: `app/diary/_components/DiaryView.tsx`, `app/diary/_components/DiaryView.test.tsx`

**Interfaces:**
- Consumes: Task 1 `DiaryView` 타입, Task 2 `EvidenceDisclosure`
- Produces: `export function DiaryArticle({ diary }: { diary: DiaryView }): JSX.Element`

> 타입 이름(`DiaryView`)과 컴포넌트 이름이 겹치지 않게 컴포넌트는 **`DiaryArticle`** 로 둔다.

- [ ] **Step 1: 실패 테스트 작성**

`app/diary/_components/DiaryView.test.tsx`:

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiaryArticle } from "./DiaryView";
import type { DiaryView } from "@/lib/services/diary";

const base: DiaryView = {
  date: "2026-07-26",
  oneLine: "비슷한 하루, 그래도 조금 일찍.",
  body: "특별할 것 없는 하루였다. 점심은 김밥.",
  differences: ["평소보다 일찍 퇴근"],
  evidence: ["점심 김밥"],
  isEdited: false,
};

describe("DiaryArticle", () => {
  it("날짜·한 문장·본문·다른 점을 보여준다", () => {
    render(<DiaryArticle diary={base} />);
    expect(screen.getByText("2026-07-26")).toBeInTheDocument();
    expect(screen.getByText(base.oneLine)).toBeInTheDocument();
    expect(screen.getByText(base.body)).toBeInTheDocument();
    expect(screen.getByText("평소보다 일찍 퇴근")).toBeInTheDocument();
  });

  it("AI 생성물임을 라벨로 밝힌다", () => {
    render(<DiaryArticle diary={base} />);
    expect(screen.getByText("AI가 쓴 초안")).toBeInTheDocument();
  });

  it("사용자가 고친 일기는 초안이라고 하지 않는다", () => {
    render(<DiaryArticle diary={{ ...base, isEdited: true }} />);
    expect(screen.queryByText("AI가 쓴 초안")).not.toBeInTheDocument();
    expect(screen.getByText("내가 고친 일기")).toBeInTheDocument();
  });

  it("한 문장이 없으면 그 영역을 렌더하지 않는다", () => {
    render(<DiaryArticle diary={{ ...base, oneLine: "" }} />);
    expect(screen.getByText(base.body)).toBeInTheDocument();
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });

  it("근거 접기를 함께 보여준다", () => {
    render(<DiaryArticle diary={base} />);
    expect(screen.getByRole("button", { name: /무엇을 보고 썼는지/ })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 실패 확인**

```powershell
npx vitest run app/diary/_components/DiaryView.test.tsx
```
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 구현 작성**

`app/diary/_components/DiaryView.tsx`:

```tsx
import type { DiaryView } from "@/lib/services/diary";
import { EvidenceDisclosure } from "./EvidenceDisclosure";

/** 일기 한 편. AI 생성물임을 라벨·배경으로 밝히고(frontend.md), 근거는 접어 둔다.
 * 사용자가 고친 일기를 '초안'이라 부르지 않는다. */
export function DiaryArticle({ diary }: { diary: DiaryView }) {
  return (
    <article>
      <p className="text-xs text-muted-foreground">{diary.date}</p>

      {diary.oneLine && <h2 className="mt-1 text-lg font-medium">{diary.oneLine}</h2>}

      <div className="mt-3 rounded-xl bg-muted/50 p-4">
        <p className="mb-2 text-xs text-muted-foreground">
          {diary.isEdited ? "내가 고친 일기" : "AI가 쓴 초안"}
        </p>
        <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{diary.body}</p>
      </div>

      {diary.differences.length > 0 && (
        // 불릿은 CSS ::marker(list-disc)로 그린다. 문자 '·'를 텍스트에 넣으면
        // 스크린리더가 "가운데점 …"으로 읽고 접근 가능한 텍스트가 오염된다.
        <ul className="mt-4 list-disc space-y-1 pl-5">
          {diary.differences.map((d, i) => (
            <li key={i} className="text-[15px] text-muted-foreground">
              {d}
            </li>
          ))}
        </ul>
      )}

      <EvidenceDisclosure items={diary.evidence} />
    </article>
  );
}
```

- [ ] **Step 4: 통과 확인**

```powershell
npx vitest run app/diary/_components/DiaryView.test.tsx
npm run lint
```
Expected: 5건 PASS, lint 통과.

- [ ] **Step 5: 커밋**

```powershell
git add app/diary/_components/DiaryView.tsx app/diary/_components/DiaryView.test.tsx
git commit -m "feat(ui): 일기 표시 컴포넌트

날짜·한 문장·본문·녹아든 다른 점을 보여주고, AI 생성물임을 라벨과
배경으로 구분한다(frontend.md). 사용자가 고친 일기는 초안이라 부르지
않는다. 근거는 접어서 함께 노출."
```

---

## Task 4: 페이지 배선 — 상태 분기

**Files:**
- Create: `app/diary/page.tsx`, `app/diary/loading.tsx`, `app/diary/error.tsx`

**Interfaces:**
- Consumes: Task 1 저장소, Task 3 `DiaryArticle`, 기존 `createServerSupabase`·`EmptyState`

- [ ] **Step 1: 페이지 작성**

`app/diary/page.tsx`:

```tsx
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";
import { EmptyState } from "@/components/common/StateView";
import { DiaryArticle } from "./_components/DiaryView";

export default async function DiaryPage() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const repo = createDiaryRepository(supabase);
  const diary = user ? await repo.findLatest() : null;
  // 일기가 없을 때, 기록조차 없는 날과 '아직 안 만들어진' 상태를 구분한다.
  // 섞으면 사용자가 "내가 기록을 안 했나?"로 오해한다.
  const hasMemory = user && !diary ? await repo.hasAnyMemory() : false;

  return (
    <main className="mx-auto max-w-md p-4">
      <h1 className="mb-4 text-lg font-medium">일기</h1>
      {diary ? (
        <DiaryArticle diary={diary} />
      ) : hasMemory ? (
        <EmptyState message="아직 일기가 만들어지지 않았어요" />
      ) : (
        <EmptyState message="아직 쌓인 기록이 없어요" />
      )}
    </main>
  );
}
```

`app/diary/loading.tsx`:

```tsx
import { LoadingState } from "@/components/common/StateView";
export default function Loading() {
  return <main className="mx-auto max-w-md p-4"><LoadingState /></main>;
}
```

`app/diary/error.tsx`:

```tsx
"use client";
import { ErrorState } from "@/components/common/StateView";
export default function Error({ reset }: { error: Error; reset: () => void }) {
  return <main className="mx-auto max-w-md p-4"><ErrorState onRetry={reset} /></main>;
}
```

- [ ] **Step 2: 타입·lint·빌드 확인**

```powershell
npm run lint
npm run build
```
Expected: 통과. `/diary` 라우트가 빌드 산출물에 나타난다.

- [ ] **Step 3: 전체 단위 회귀**

```powershell
npx vitest run
```
Expected: 기존 40건 + 새 9건 = 49건 PASS(정확한 수는 앞 태스크 결과에 따름). 기존 테스트가 깨지면 안 된다.

- [ ] **Step 4: 육안 확인(선택)**

```powershell
npm run dev
```
브라우저에서 `/diary`를 연다. 일기가 없으면 상태 문구가, 있으면 일기가 보이는지 본다.
**일기를 만들려고 `run-diary`를 실행하지 마라(실 LLM 비용).** 필요하면 사람에게 요청하라.

- [ ] **Step 5: 커밋**

```powershell
git add app/diary/page.tsx app/diary/loading.tsx app/diary/error.tsx
git commit -m "feat(ui): 일기 보기 화면 배선

서버 컴포넌트가 최신 일기를 읽어 보여준다. 일기가 없을 때 '기록이 없음'과
'아직 만들어지지 않음'을 구분해 파이프라인 미실행을 정직하게 알린다.
독려·압박 문구 없이 담담하게. loading·error는 기존 StateView 재사용."
```

---

## Task 5: 문서

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 저장소 구조에 화면 추가**

`README.md`의 저장소 구조 블록에서 `app/review/` 줄 **바로 뒤에** 추가:

```
app/diary/              # 일기 보기 화면 (최신 일기 · 근거 접기)
```

- [ ] **Step 2: 화면 설명 한 줄 추가**

`README.md`에서 확인 UI를 설명하는 줄(`확인 UI(/review)는 ...`) **바로 뒤에** 추가:

```markdown
일기 화면(`/diary`)은 가장 최근 일기를 읽기 전용으로 보여주고, 무엇을 보고 썼는지(근거 메모)를 접어서 함께 제공한다. 일기 생성은 `run-diary`(§4)가 하며 화면에서 트리거하지 않는다.
```

- [ ] **Step 3: 전체 검사**

```powershell
npm run lint
npm run build
npx vitest run
npx vitest run --config vitest.integration.config.mts
```
Expected: 전부 통과(통합은 로컬 Supabase 필요).

- [ ] **Step 4: 커밋**

```powershell
git add README.md
git commit -m "docs: 일기 보기 화면 안내"
```

- [ ] **Step 5: 최종 보고**

`HANDOFF.md`의 "상태" 절을 갱신하고 커밋한다(무엇을 했는지·태스크별 커밋 SHA·검증 결과·막힌 점). **push·merge는 하지 마라** — 사람이 한다.

---

## 완료 기준

- `/diary`가 가장 최근 일기(날짜·한 문장·본문·다른 점)를 보여준다.
- **AI 생성물 표식**이 있고, 편집본이면 문구가 다르다.
- 근거는 기본 접혀 있고 펼치면 **원본 라벨과 함께** 보인다. 근거 0건이면 접기 UI가 없다.
- 일기가 없을 때 **"기록 없음"과 "아직 안 만들어짐"을 구분**하고, 독려·압박 문구가 없다.
- **잠긴·삭제된 메모가 근거에 나오지 않는다**(통합 테스트).
- **타 사용자 일기가 조회되지 않는다**(RLS 통합 테스트).
- 토글이 44px 터치 타깃이고 `aria-expanded`로 상태를 알린다.
- lint + build + unit + integration 전부 통과. 스키마·API·워커 변경 없음.

## 이번 범위 밖

- 일기 편집·확정 · 날짜 이동·목록 · 공유·내보내기 · 사진.
- "지금 만들기" 버튼(앱↔워커 직접 호출 금지 — 큐가 필요하다).
- 워커·스키마·API 라우트 변경.
