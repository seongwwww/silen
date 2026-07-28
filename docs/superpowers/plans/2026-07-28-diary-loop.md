# 일기 루프 완성 구현 계획 (기획서 §6)

> **실행 주체:** Codex. 태스크마다 ① 실패 테스트 → ② 실패 확인 → ③ 계획의 코드 그대로 → ④ 통과 → ⑤ lint/ruff + build → ⑥ 1커밋.

**Goal:** 일기를 고치고, 확정하고, 톤을 정하고, 다시 만들 수 있게 한다.

**Architecture:** 상태 전이는 `difference` 선례(순수 검증 + TOCTOU) 그대로. 톤과 재생성은 **요청을 남기고 다음 생성이 반영**한다 — 즉시 반영용 큐를 만들지 않는다.

**Tech Stack:** Next.js 16 · TypeScript · Vitest · Python 워커 · Supabase

## Global Constraints

- **`main` 직접 커밋 금지** — **`feat/diary-loop`을 `main`에서 새로 만들어** 작업한다.
- 커밋 `<type>(<scope>): <한국어 요약>`. scope는 `db`·`ui`·`api`·`worker`·`eval`·`docs`. **`Co-Authored-By`는 네 것으로.**
- **태스크마다 커밋만. push·merge 금지.**
- **앱 코드 전 Next.js 16 문서**(`node_modules/next/dist/docs/01-app/`) 확인 — `params`·`searchParams`는 **Promise**다.
- ⚠️ **`supabase.select()` 인자는 리터럴 타입 유지**(상수면 `as const`). 이 오류는 lint·단위로 안 잡히고 **`npm run build`(tsc)에서만** 드러난다 → **프론트 태스크마다 build를 돌려라.**
- ⚠️ **터치 타깃 44px**(`min-h-11`). `min-h-9` 금지.
- ⚠️ **색만으로 의미를 전달하지 마라** — 라벨 병행.
- ⚠️ **죄책감·독려 문구 금지**(frontend.md).
- **저장소는 세션 클라이언트 + RLS.** `service_role` 금지.
- **기존 가드레일을 약화하지 마라.** 톤이 바뀌어도 사실 집합은 그대로다.
- 🚫 **실 LLM 호출 금지**(스텁으로 검증). eval은 Task 8에서 1회.
- 완료(DoD) = lint + build + vitest(단위·통합) + ruff + pytest.
- 못 고치는 실패·모호한 점은 **멈추고 보고**하라.

## 결정 고정

1. **상태 전이:** `draft→edited` · `draft→confirmed` · `edited→confirmed` · `confirmed→edited`(되돌리기). 그 외 금지.
2. **편집 저장은 `edited_text`에.** `generated_text`(AI 초안)는 **절대 덮어쓰지 않는다** — 원본↔생성물 분리 원칙.
3. **본문 표시 우선순위는 기존 그대로** `edited_text ?? generated_text`.
4. **TOCTOU 방어:** 읽은 status를 `expected`로 넘겨 원자적 업데이트, 0행이면 **409**.
5. **톤 프리셋은 `담백`·`따뜻` 둘뿐.** 늘리지 마라.
6. **`users.style_profile`은 jsonb.** `{"preset":"담백"}` 형태로 쓴다.
7. **재생성 요청 처리 후 두 필드를 비운다**(`tone_instruction=null`, `regenerate_requested_at=null`). 자동 재생성이 아니다.
8. **재생성은 `status` 무관하게 덮어쓴다** — 명시적 요청이기 때문이다. UI가 편집본일 때 경고한다.
9. **`generated_text`만 재생성이 갱신**하고, 재생성 시 `edited_text`는 **`null`로 비운다**(고친 내용이 사라진다고 경고했으므로). status는 `draft`로 되돌린다.
10. **새 저장소 `userRepository.ts`를 `eslint.config.mjs` 예외 목록에 추가**한다(기존 4개와 같은 이유 — 경계가 조립하는 팩토리). 규칙 구조는 건드리지 마라.
11. **설정 화면은 톤 프리셋만.** `diary_time`은 F4다.
12. **즉시 반영·처리중 UI·폴링을 만들지 마라.**
13. **사용자가 `다시 만들기`를 요청한 경우만 편집본을 덮는다.** 요청 없는
    일반 force는 저장 순간에도 `draft`일 때만 갱신해, 그사이 사용자가 고친
    일기를 보존한다.

## File Structure

| 경로 | 책임 |
|------|------|
| `supabase/migrations/<ts>_diary_loop.sql` + `down/` | `diaries`에 컬럼 2개 |
| `lib/services/diary.ts`(수정) | `DiaryStatus`·전이 검증·타입 확장 |
| `lib/repositories/diaryRepository.ts`(수정) | 편집·상태·재생성 요청 |
| `lib/repositories/userRepository.ts` | `style_profile` 읽기·쓰기 |
| `eslint.config.mjs`(수정) | 예외에 `userRepository.ts` |
| `app/api/diaries/[id]/route.ts` | PATCH 편집·확정 |
| `app/api/diaries/[id]/regenerate/route.ts` | POST 재생성 요청 |
| `app/api/users/me/route.ts` | PATCH 프리셋 |
| `app/diary/_components/DiaryEditor.tsx` | 인라인 편집·확정·다시 만들기 |
| `app/settings/page.tsx` + `_components/TonePicker.tsx` | 톤 프리셋 |
| `worker/src/silen_worker/db.py`·`diary/service.py`·`tasks/write_diary.py`(수정) | 프리셋·주문·재생성 |
| `evals/diary/`(수정) | 톤 불변성 케이스 |

---

## Task 1: 스키마

**Files:** Create `supabase/migrations/<ts>_diary_loop.sql`, `down/<ts>_diary_loop.down.sql`, `worker/tests/test_diary_loop_schema_integration.py`

- [ ] **Step 1: 마이그레이션 생성**

```powershell
npx supabase migration new diary_loop
```
생성된 14자리 타임스탬프를 up/down 파일명에 **동일하게** 쓴다.

- [ ] **Step 2: up 작성**

```sql
-- 톤 주문과 재생성 요청. 둘 다 다음 생성이 1회 소비하고 비운다.
-- 자동 재생성이 아니라 사용자가 명시적으로 누른 요청이다(기획서 §6).
alter table public.diaries
  add column tone_instruction text,
  add column regenerate_requested_at timestamptz;
```

- [ ] **Step 3: down 작성**

```sql
alter table public.diaries
  drop column if exists regenerate_requested_at,
  drop column if exists tone_instruction;
```

- [ ] **Step 4: 통합 테스트**

`worker/tests/test_diary_loop_schema_integration.py`:

```python
from datetime import date

import pytest

from tests.conftest import seed_user, delete_user


@pytest.mark.integration
def test_톤주문과_재생성요청을_저장한다(conn):
    user = seed_user(conn)
    try:
        diary = conn.execute(
            "insert into public.diaries (user_id, date, status, generated_text) "
            "values (%s, %s, 'draft', '본문') returning id::text",
            (user, date.today()),
        ).fetchone()[0]
        conn.execute(
            "update public.diaries set tone_instruction = %s, "
            "regenerate_requested_at = now() where id = %s",
            ("더 짧게", diary),
        )
        row = conn.execute(
            "select tone_instruction, regenerate_requested_at is not null "
            "from public.diaries where id = %s",
            (diary,),
        ).fetchone()
        assert row[0] == "더 짧게"
        assert row[1] is True
    finally:
        delete_user(conn, user)
```

- [ ] **Step 5: 적용·실행·커밋**

```powershell
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_diary_loop_schema_integration.py -m integration -v
```

```powershell
git add supabase/migrations worker/tests/test_diary_loop_schema_integration.py
git commit -m "feat(db): 일기 톤 주문·재생성 요청 컬럼

둘 다 다음 생성이 1회 소비하고 비운다. 자동 재생성이 아니라 사용자가
명시적으로 누른 요청이다(기획서 §6). up/down 동봉."
```

---

## Task 2: 상태 전이 서비스 (순수)

**Files:** Modify `lib/services/diary.ts`; Create `lib/services/diary.test.ts`

- [ ] **Step 1: 실패 테스트**

`lib/services/diary.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import {
  assertValidDiaryTransition,
  InvalidDiaryTransitionError,
  type DiaryStatus,
} from "./diary";

const allowed: [DiaryStatus, DiaryStatus][] = [
  ["draft", "edited"],
  ["draft", "confirmed"],
  ["edited", "confirmed"],
  ["confirmed", "edited"],
];

const forbidden: [DiaryStatus, DiaryStatus][] = [
  ["draft", "draft"],
  ["edited", "draft"],
  ["confirmed", "draft"],
  ["confirmed", "confirmed"],
];

describe("일기 상태 전이", () => {
  it.each(allowed)("%s → %s 는 허용된다", (from, to) => {
    expect(() => assertValidDiaryTransition(from, to)).not.toThrow();
  });

  it.each(forbidden)("%s → %s 는 거부된다", (from, to) => {
    expect(() => assertValidDiaryTransition(from, to)).toThrow(
      InvalidDiaryTransitionError,
    );
  });
});
```

- [ ] **Step 2: 실패 확인**

```powershell
npx vitest run lib/services/diary.test.ts
```
Expected: FAIL — export 없음.

- [ ] **Step 3: 구현**

`lib/services/diary.ts` **끝에** 추가하고, `DiaryView`에 필드 둘을 더한다:

```ts
export type DiaryStatus = "draft" | "edited" | "confirmed";

export class InvalidDiaryTransitionError extends Error {
  constructor() {
    super("허용되지 않은 상태 전이");
    this.name = "InvalidDiaryTransitionError";
  }
}

// 초안을 고치거나 바로 확정하고, 확정은 되돌릴 수 있다.
// draft로는 되돌아가지 않는다 — 사람이 손댄 흔적을 지우지 않는다.
const ALLOWED: Record<DiaryStatus, DiaryStatus[]> = {
  draft: ["edited", "confirmed"],
  edited: ["confirmed"],
  confirmed: ["edited"],
};

export function assertValidDiaryTransition(
  current: DiaryStatus,
  target: DiaryStatus,
): void {
  if (!ALLOWED[current]?.includes(target)) {
    throw new InvalidDiaryTransitionError();
  }
}
```

`DiaryView` 인터페이스에 추가:

```ts
  /** 편집·확정 UI가 쓰는 현재 상태 */
  status: DiaryStatus;
  /** 일기 id — PATCH 대상 */
  id: string;
```

- [ ] **Step 4: 통과 확인 + 커밋**

```powershell
npx vitest run lib/services/diary.test.ts
npm run lint
```

```powershell
git add lib/services/diary.ts lib/services/diary.test.ts
git commit -m "feat(ui): 일기 상태 전이 규칙

초안을 고치거나 바로 확정하고, 확정은 되돌릴 수 있다. draft로는 되돌아가지
않는다 — 사람이 손댄 흔적을 지우지 않는다. difference 선례와 같은 형태."
```

---

## Task 3: 저장소 + 편집·확정 API

**Files:** Modify `lib/repositories/diaryRepository.ts`; Create `app/api/diaries/[id]/route.ts`, `lib/repositories/diaryEdit.integration.test.ts`

- [ ] **Step 1: 저장소 확장**

`DIARY_SELECT` 상수에 `id, ` 를 맨 앞에 넣고(리터럴 유지), `toDiaryView` 반환에 `id`·`status`를 더한다:

```ts
const DIARY_SELECT =
  "id, date, status, generated_text, edited_text, diary_sections(id, section_type, content), diary_sources(memories(raw_text, is_locked, deleted_at))" as const;
```

```ts
    id: row.id as string,
    status: (row.status as DiaryStatus) ?? "draft",
```

`import type { DiaryStatus }` 를 추가한다. 저장소 객체에 메서드 둘을 더한다:

```ts
    /** 편집 본문과 상태를 함께 바꾼다. 기대 상태와 다르면 0행 → false(TOCTOU).
     * generated_text(AI 초안)는 절대 건드리지 않는다 — 원본↔생성물 분리. */
    async updateDraft(
      id: string,
      editedText: string,
      status: DiaryStatus,
      expected: DiaryStatus,
    ): Promise<boolean> {
      const { data, error } = await client
        .from("diaries")
        .update({ edited_text: editedText, status })
        .eq("id", id)
        .eq("status", expected)
        .select("id");
      if (error) throw error;
      return (data?.length ?? 0) > 0;
    },

    /** 상태만 바꾼다(본문 수정 없이 확정·되돌리기). */
    async updateStatus(
      id: string,
      status: DiaryStatus,
      expected: DiaryStatus,
    ): Promise<boolean> {
      const { data, error } = await client
        .from("diaries")
        .update({ status })
        .eq("id", id)
        .eq("status", expected)
        .select("id");
      if (error) throw error;
      return (data?.length ?? 0) > 0;
    },

    /** 재생성 요청을 남긴다. 다음 생성이 1회 소비한다. */
    async requestRegenerate(id: string, toneInstruction: string | null): Promise<boolean> {
      const { data, error } = await client
        .from("diaries")
        .update({
          tone_instruction: toneInstruction,
          regenerate_requested_at: new Date().toISOString(),
        })
        .eq("id", id)
        .select("id");
      if (error) throw error;
      return (data?.length ?? 0) > 0;
    },
```

- [ ] **Step 2: PATCH 라우트**

`app/api/diaries/[id]/route.ts` — `app/api/differences/[id]/route.ts` 구조를 따른다:

```ts
import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";
import {
  assertValidDiaryTransition,
  InvalidDiaryTransitionError,
  type DiaryStatus,
} from "@/lib/services/diary";

const bodySchema = z.object({
  editedText: z.string().max(2000).optional(),
  status: z.enum(["draft", "edited", "confirmed"]),
});

export async function PATCH(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
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
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json(
      { error: { code: "unauthorized", message: "세션이 필요합니다" } },
      { status: 401 },
    );
  }

  // 현재 status를 읽어 전이를 검증한다(본인 것만 보임 — RLS).
  const { data: current } = await supabase
    .from("diaries")
    .select("status")
    .eq("id", id)
    .maybeSingle();
  if (!current) {
    return NextResponse.json(
      { error: { code: "not_found", message: "일기를 찾을 수 없습니다" } },
      { status: 404 },
    );
  }
  try {
    assertValidDiaryTransition(current.status as DiaryStatus, parsed.status);
  } catch (e) {
    if (e instanceof InvalidDiaryTransitionError) {
      return NextResponse.json(
        { error: { code: "invalid_transition", message: "허용되지 않은 변경입니다" } },
        { status: 400 },
      );
    }
    throw e;
  }

  const repo = createDiaryRepository(supabase);
  // 읽은 상태를 기대값으로 넘긴다 — 그새 바뀌었으면 0행(409).
  const changed =
    parsed.editedText === undefined
      ? await repo.updateStatus(id, parsed.status, current.status as DiaryStatus)
      : await repo.updateDraft(id, parsed.editedText, parsed.status, current.status as DiaryStatus);
  if (!changed) {
    return NextResponse.json(
      { error: { code: "conflict", message: "그새 상태가 바뀌었어요. 다시 시도해 주세요" } },
      { status: 409 },
    );
  }
  return new NextResponse(null, { status: 204 });
}
```

- [ ] **Step 3: 통합 테스트**

`lib/repositories/diaryEdit.integration.test.ts` — 기존 `diary.integration.test.ts`의 `clientFor`·`seedDiary` 패턴을 그대로 쓴다(파일 상단 부트스트랩을 복사해 온다). 검증할 것:

```ts
  it("편집 본문과 상태를 저장한다", async () => {
    // seedDiary로 draft 일기를 만들고
    const repo = createDiaryRepository(await clientFor("edit-alice@example.com"));
    expect(await repo.updateDraft(diaryId, "내가 고친 본문", "edited", "draft")).toBe(true);
    const view = await repo.findLatest();
    expect(view!.body).toBe("내가 고친 본문");
    expect(view!.status).toBe("edited");
  });

  it("기대 상태가 다르면 실패한다(TOCTOU)", async () => {
    const repo = createDiaryRepository(await clientFor("edit-alice@example.com"));
    // 이미 edited인 일기에 draft를 기대값으로 넘긴다
    expect(await repo.updateDraft(diaryId, "다른 본문", "confirmed", "draft")).toBe(false);
  });

  it("AI 초안은 덮어쓰지 않는다", async () => {
    // updateDraft 후 generated_text가 그대로인지 db로 확인
  });

  it("타 사용자 일기는 바꿀 수 없다", async () => {
    const repo = createDiaryRepository(await clientFor("edit-bob@example.com"));
    expect(await repo.updateDraft(aliceDiaryId, "침입", "edited", "draft")).toBe(false);
  });
```

- [ ] **Step 4: 실행·커밋**

```powershell
npx vitest run --config vitest.integration.config.mts lib/repositories/diaryEdit.integration.test.ts
npm run lint
npm run build
```

```powershell
git add lib/repositories/diaryRepository.ts app/api/diaries lib/repositories/diaryEdit.integration.test.ts lib/services/diary.ts
git commit -m "feat(api): 일기 편집·확정 PATCH

읽은 상태를 기대값으로 넘겨 원자적으로 바꾼다 — 그새 바뀌면 409(TOCTOU).
편집은 edited_text에만 쓰고 AI 초안(generated_text)은 건드리지 않는다."
```

---

## Task 4: 일기 화면 편집·확정 UI

**Files:** Create `app/diary/_components/DiaryEditor.tsx` + 테스트; Modify `app/diary/_components/DiaryView.tsx`

- [ ] **Step 1: 실패 테스트**

`app/diary/_components/DiaryEditor.test.tsx`:

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DiaryEditor } from "./DiaryEditor";

beforeEach(() => vi.restoreAllMocks());

const base = { id: "d1", body: "AI가 쓴 본문", status: "draft" as const };

describe("DiaryEditor", () => {
  it("기본은 읽기 상태이고 고치기·확정 버튼이 있다", () => {
    render(<DiaryEditor {...base} />);
    expect(screen.getByRole("button", { name: "고치기" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "확정" })).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("고치기를 누르면 편집창이 열린다", async () => {
    render(<DiaryEditor {...base} />);
    await userEvent.click(screen.getByRole("button", { name: "고치기" }));
    expect(screen.getByRole("textbox")).toHaveValue("AI가 쓴 본문");
  });

  it("저장하면 편집 본문과 edited 상태를 보낸다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<DiaryEditor {...base} />);
    await userEvent.click(screen.getByRole("button", { name: "고치기" }));
    await userEvent.clear(screen.getByRole("textbox"));
    await userEvent.type(screen.getByRole("textbox"), "내가 고친 글");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ editedText: "내가 고친 글", status: "edited" });
  });

  it("확정하면 confirmed를 보낸다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<DiaryEditor {...base} />);
    await userEvent.click(screen.getByRole("button", { name: "확정" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ status: "confirmed" });
  });

  it("확정된 일기는 되돌리기를 보여준다", () => {
    render(<DiaryEditor {...base} status="confirmed" />);
    expect(screen.getByRole("button", { name: "다시 고치기" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "확정" })).not.toBeInTheDocument();
  });

  it("모든 버튼이 44px 터치 타깃이다", () => {
    render(<DiaryEditor {...base} />);
    for (const b of screen.getAllByRole("button")) {
      expect(b.className).toContain("min-h-11");
    }
  });
});
```

- [ ] **Step 2: 실패 확인 후 구현**

`app/diary/_components/DiaryEditor.tsx`:

```tsx
"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { DiaryStatus } from "@/lib/services/diary";

/** 초안을 고치거나 바로 확정한다(기획서 §6). 안 건드리면 draft 그대로다.
 * 편집은 edited_text에만 쓰이고 AI 초안은 남는다. */
export function DiaryEditor({
  id,
  body,
  status,
}: {
  id: string;
  body: string;
  status: DiaryStatus;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(body);
  const [saving, setSaving] = useState(false);

  async function send(payload: { editedText?: string; status: DiaryStatus }) {
    setSaving(true);
    try {
      const res = await fetch(`/api/diaries/${id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("failed");
      setEditing(false);
      toast("저장했어요");
    } catch {
      toast.error("저장하지 못했어요. 다시 시도해 주세요.");
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <div className="mt-3 flex flex-col gap-2">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="min-h-11"
          aria-label="일기 본문"
        />
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="min-h-11 flex-1"
            disabled={saving}
            onClick={() => setEditing(false)}
          >
            취소
          </Button>
          <Button
            className="min-h-11 flex-1"
            disabled={saving}
            onClick={() => void send({ editedText: text, status: "edited" })}
          >
            저장
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-3 flex gap-2">
      <Button
        variant="outline"
        className="min-h-11 flex-1"
        onClick={() => setEditing(true)}
      >
        {status === "confirmed" ? "다시 고치기" : "고치기"}
      </Button>
      {status !== "confirmed" && (
        <Button
          className="min-h-11 flex-1"
          disabled={saving}
          onClick={() => void send({ status: "confirmed" })}
        >
          확정
        </Button>
      )}
    </div>
  );
}
```

> `status === "confirmed"`일 때 "다시 고치기"를 누르면 편집창이 열리고, 저장 시 `edited`로 간다 — 전이 규칙(`confirmed→edited`)과 맞는다.

`DiaryView.tsx`의 본문 블록 아래에 `<DiaryEditor id={diary.id} body={diary.body} status={diary.status} />`를 넣고 import를 추가한다. `DiaryView.test.tsx`의 `base` 객체에 `id: "d1"`·`status: "draft"`를 더한다.

- [ ] **Step 3: 실행·커밋**

```powershell
npx vitest run
npm run lint
npm run build
```

```powershell
git add app/diary/_components lib/services/diary.ts
git commit -m "feat(ui): 일기 초안 고치기·확정

초안을 인라인으로 고치거나 바로 확정한다. 안 건드리면 draft 그대로다.
확정한 일기는 다시 고칠 수 있다(전이 규칙 confirmed→edited)."
```

---

## Task 5: 재생성 요청 API + 버튼

**Files:** Create `app/api/diaries/[id]/regenerate/route.ts`, `app/diary/_components/RegenerateButton.tsx` + 테스트

- [ ] **Step 1: 실패 테스트**

`app/diary/_components/RegenerateButton.test.tsx`:

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RegenerateButton } from "./RegenerateButton";

beforeEach(() => vi.restoreAllMocks());

describe("RegenerateButton", () => {
  it("draft면 경고 없이 바로 요청한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<RegenerateButton id="d1" status="draft" />);
    await userEvent.click(screen.getByRole("button", { name: "다시 만들기" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });

  it("편집본이면 사라진다고 알리고 한 번 더 확인받는다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<RegenerateButton id="d1" status="edited" />);
    await userEvent.click(screen.getByRole("button", { name: "다시 만들기" }));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText("고친 내용이 사라져요. 그래도 다시 만들까요?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "다시 만들기" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });

  it("요청은 다음 생성 때 반영된다고 알린다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    render(<RegenerateButton id="d1" status="draft" />);
    await userEvent.click(screen.getByRole("button", { name: "다시 만들기" }));
    await waitFor(() =>
      expect(screen.getByText("다음 일기를 만들 때 반영돼요.")).toBeInTheDocument(),
    );
  });

  it("44px 터치 타깃", () => {
    render(<RegenerateButton id="d1" status="draft" />);
    expect(screen.getByRole("button", { name: "다시 만들기" }).className).toContain("min-h-11");
  });
});
```

- [ ] **Step 2: 구현**

`app/diary/_components/RegenerateButton.tsx`:

```tsx
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { DiaryStatus } from "@/lib/services/diary";

/** 늦은 메모를 반영하려 다시 만든다(기획서 §6 "다시 만들기 1회").
 * 즉시 반영이 아니라 요청을 남기고 다음 생성이 반영한다.
 * 편집본이면 고친 내용이 사라지므로 한 번 더 확인받는다. */
export function RegenerateButton({ id, status }: { id: string; status: DiaryStatus }) {
  const [confirming, setConfirming] = useState(false);
  const [requested, setRequested] = useState(false);
  const [sending, setSending] = useState(false);

  async function send() {
    setSending(true);
    try {
      const res = await fetch(`/api/diaries/${id}/regenerate`, { method: "POST" });
      if (!res.ok) throw new Error("failed");
      setRequested(true);
      setConfirming(false);
    } finally {
      setSending(false);
    }
  }

  if (requested) {
    return <p className="mt-3 text-[15px] text-muted-foreground">다음 일기를 만들 때 반영돼요.</p>;
  }

  return (
    <div className="mt-3">
      {confirming && (
        <p className="mb-2 text-[15px] text-muted-foreground">
          고친 내용이 사라져요. 그래도 다시 만들까요?
        </p>
      )}
      <Button
        variant="outline"
        className="min-h-11 w-full"
        disabled={sending}
        onClick={() => {
          if (status !== "draft" && !confirming) {
            setConfirming(true);
            return;
          }
          void send();
        }}
      >
        다시 만들기
      </Button>
    </div>
  );
}
```

`app/api/diaries/[id]/regenerate/route.ts`:

```ts
import { NextResponse } from "next/server";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";

/** 재생성 요청만 남긴다. 다음 run-diary가 1회 소비하고 비운다(자동 재생성 아님). */
export async function POST(_request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json(
      { error: { code: "unauthorized", message: "세션이 필요합니다" } },
      { status: 401 },
    );
  }
  const ok = await createDiaryRepository(supabase).requestRegenerate(id, null);
  if (!ok) {
    return NextResponse.json(
      { error: { code: "not_found", message: "일기를 찾을 수 없습니다" } },
      { status: 404 },
    );
  }
  return new NextResponse(null, { status: 204 });
}
```

`DiaryView.tsx`에 `<RegenerateButton id={diary.id} status={diary.status} />`를 편집기 아래에 넣는다.

- [ ] **Step 3: 실행·커밋**

```powershell
npx vitest run
npm run lint
npm run build
```

```powershell
git add app/api/diaries app/diary/_components
git commit -m "feat(ui): 일기 다시 만들기 요청

즉시 재생성하지 않고 요청만 남긴다 — 다음 생성이 1회 반영한다.
편집본이면 고친 내용이 사라진다고 알리고 한 번 더 확인받는다."
```

---

## Task 6: 설정 화면 — 톤 프리셋

**Files:** Create `lib/repositories/userRepository.ts`, `app/api/users/me/route.ts`, `app/settings/page.tsx`, `app/settings/_components/TonePicker.tsx` + 테스트; Modify `eslint.config.mjs`

- [ ] **Step 1: eslint 예외 추가**

`eslint.config.mjs`의 `except` 배열에 한 줄 추가한다(기존 4개와 같은 이유 — 경계가 조립하는 팩토리):

```js
                "./userRepository.ts",
```

- [ ] **Step 2: 저장소**

`lib/repositories/userRepository.ts`:

```ts
import type { SupabaseClient } from "@supabase/supabase-js";
import type { TonePreset } from "@/lib/services/diary";

/** 세션 클라이언트로 내 설정을 읽고 쓴다. RLS가 소유권을 강제한다. */
export function createUserRepository(client: SupabaseClient) {
  return {
    async findTonePreset(): Promise<TonePreset> {
      const { data, error } = await client.from("users").select("style_profile").limit(1);
      if (error) throw error;
      const preset = (data?.[0]?.style_profile as { preset?: string } | null)?.preset;
      return preset === "따뜻" ? "따뜻" : "담백";
    },

    async updateTonePreset(preset: TonePreset): Promise<boolean> {
      const { data, error } = await client
        .from("users")
        .update({ style_profile: { preset } })
        .select("id");
      if (error) throw error;
      return (data?.length ?? 0) > 0;
    },
  };
}
```

`lib/services/diary.ts`에 타입을 더한다:

```ts
export type TonePreset = "담백" | "따뜻";
export const TONE_PRESETS: TonePreset[] = ["담백", "따뜻"];
```

- [ ] **Step 3: API**

`app/api/users/me/route.ts`:

```ts
import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createUserRepository } from "@/lib/repositories/userRepository";

const bodySchema = z.object({ tonePreset: z.enum(["담백", "따뜻"]) });

export async function PATCH(request: NextRequest) {
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
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json(
      { error: { code: "unauthorized", message: "세션이 필요합니다" } },
      { status: 401 },
    );
  }
  const ok = await createUserRepository(supabase).updateTonePreset(parsed.tonePreset);
  if (!ok) {
    return NextResponse.json(
      { error: { code: "not_found", message: "설정을 찾을 수 없습니다" } },
      { status: 404 },
    );
  }
  return new NextResponse(null, { status: 204 });
}
```

- [ ] **Step 4: 화면**

`app/settings/_components/TonePicker.tsx`:

```tsx
"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { TONE_PRESETS, type TonePreset } from "@/lib/services/diary";

/** 일기 기본 톤. 사실은 그대로 두고 문체만 바뀐다(기획서 §4-9). */
export function TonePicker({ initial }: { initial: TonePreset }) {
  const [preset, setPreset] = useState<TonePreset>(initial);

  async function pick(next: TonePreset) {
    setPreset(next);
    const res = await fetch("/api/users/me", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ tonePreset: next }),
    });
    if (!res.ok) {
      setPreset(preset);
      toast.error("바꾸지 못했어요. 다시 시도해 주세요.");
      return;
    }
    toast("톤을 바꿨어요");
  }

  return (
    <div className="flex gap-2">
      {TONE_PRESETS.map((p) => (
        <Button
          key={p}
          variant="outline"
          aria-pressed={preset === p}
          className={`min-h-11 flex-1 ${preset === p ? "border-[var(--success-text)] font-medium" : ""}`}
          onClick={() => void pick(p)}
        >
          {p}
        </Button>
      ))}
    </div>
  );
}
```

`app/settings/page.tsx`:

```tsx
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createUserRepository } from "@/lib/repositories/userRepository";
import { TonePicker } from "./_components/TonePicker";

export default async function SettingsPage() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const preset = user ? await createUserRepository(supabase).findTonePreset() : "담백";

  return (
    <main className="mx-auto max-w-md p-4">
      <h1 className="mb-4 text-lg font-medium">설정</h1>
      <h2 className="mb-2 text-[15px]">일기 톤</h2>
      <TonePicker initial={preset} />
      <p className="mt-2 text-xs text-muted-foreground">
        문체만 바뀌어요. 사실은 그대로예요.
      </p>
    </main>
  );
}
```

- [ ] **Step 5: 단위 테스트**

`app/settings/_components/TonePicker.test.tsx` — 두 프리셋이 보이고, 고르면 PATCH가 나가며 `aria-pressed`가 바뀌고, 44px인지 검증한다(색만으로 전달하지 않음).

- [ ] **Step 6: 실행·커밋**

```powershell
npx vitest run
npm run lint
npm run build
```

```powershell
git add lib/repositories/userRepository.ts app/api/users app/settings eslint.config.mjs lib/services/diary.ts
git commit -m "feat(ui): 설정 화면 — 일기 기본 톤

담백·따뜻 둘 중 하나를 고르면 매 생성에 자동 적용된다. 문체만 바뀌고
사실은 그대로다(기획서 §4-9). 선택 상태를 aria-pressed로 알린다."
```

---

## Task 7: 워커 — 프리셋·주문 반영, 재생성 요청 처리

**Files:** Modify `worker/src/silen_worker/db.py`, `diary/service.py`, `tasks/write_diary.py`, `worker/tests/test_diary.py`, `worker/tests/test_diary_integration.py`

- [ ] **Step 1: 저장소**

`db.py`의 `fetch_existing_diary`를 확장해 재생성 요청과 주문도 함께 읽는다:

```python
def fetch_existing_diary(
    conn: psycopg.Connection, user_id: str, target_date: date
) -> tuple[str, str, str | None, bool] | None:
    """(diary_id, status, tone_instruction, regenerate_requested) 또는 None."""
    row = conn.execute(
        "select id::text, status, tone_instruction, "
        "regenerate_requested_at is not null "
        "from public.diaries where user_id = %s and date = %s",
        (user_id, target_date),
    ).fetchone()
    return (row[0], row[1], row[2], row[3]) if row is not None else None
```

그리고 함수 둘을 더한다:

```python
def fetch_tone_preset(conn: psycopg.Connection, user_id: str) -> str:
    """사용자 기본 톤. 없으면 담백."""
    row = conn.execute(
        "select style_profile->>'preset' from public.users where id = %s", (user_id,)
    ).fetchone()
    return row[0] if row and row[0] in ("담백", "따뜻") else "담백"


def clear_regenerate_request(conn: psycopg.Connection, diary_id: str) -> None:
    """요청을 1회 소비한다. 자동 재생성이 아니므로 반드시 비운다."""
    conn.execute(
        "update public.diaries set tone_instruction = null, "
        "regenerate_requested_at = null where id = %s",
        (diary_id,),
    )
```

`upsert_diary`에 status 인자를 더해 재생성 시 `draft`로 되돌리고 `edited_text`를 비운다:

```python
def upsert_diary(
    conn: psycopg.Connection, user_id: str, target_date: date, generated_text: str,
    reset_edit: bool = False,
) -> str | None:
    """(user_id, date) 자연키로 멱등 upsert. reset_edit이면 편집본을 비우고
    draft로 되돌린다 — 사용자가 '다시 만들기'로 명시 요청한 경우다."""
    row = conn.execute(
        """
        insert into public.diaries (user_id, date, status, style_profile, generated_text)
        values (%s, %s, 'draft', '{"preset":"담백"}'::jsonb, %s)
        on conflict (user_id, date) do update
          set generated_text = excluded.generated_text,
              status = 'draft',
              edited_text = case when %s then null else public.diaries.edited_text end
          where %s or public.diaries.status = 'draft'
        returning id::text
        """,
        (user_id, target_date, generated_text, reset_edit, reset_edit),
    ).fetchone()
    return row[0] if row is not None else None
```

- [ ] **Step 2: 프롬프트에 톤 반영**

`diary/service.py`의 `DiaryInput`에 필드 둘을 더한다:

```python
    tone_preset: str = "담백"
    tone_instruction: str | None = None
```

`build_prompt`의 규칙 줄 뒤에 톤 지시를 넣는다:

```python
        f"톤: {facts.tone_preset}(담백=건조·짧은 호흡, 따뜻=부드러운 말투). "
        "톤은 문체만 바꾼다. 사실을 바꾸거나 없는 감정을 더하지 마라.\n"
        + (f"이번 요청: {facts.tone_instruction}\n" if facts.tone_instruction else "")
```

- [ ] **Step 3: 경계 배선**

`tasks/write_diary.py`의 기존 diary 조회·분기를 아래로 바꾼다:

```python
    existing = fetch_existing_diary(conn, user_id, target)
    regenerate = False
    tone_instruction = None
    if existing is not None:
        diary_id_existing, status, tone_instruction, regenerate = existing
        # 사용자가 명시적으로 '다시 만들기'를 눌렀으면 status 무관하게 다시 쓴다.
        if not regenerate and (not force or status != "draft"):
            return diary_id_existing  # 멱등·유저 편집 보호
```

`DiaryInput` 생성에 톤을 넘긴다:

```python
        tone_preset=fetch_tone_preset(conn, user_id),
        tone_instruction=tone_instruction,
```

저장부에서 재생성이면 편집본을 비우고, 요청을 소비한다:

```python
    diary_id = upsert_diary(conn, user_id, target, diary.body, reset_edit=regenerate)
    ...
    if regenerate:
        clear_regenerate_request(conn, diary_id)
```

- [ ] **Step 4: 테스트**

`worker/tests/test_diary.py`에 프롬프트 검증을 더한다(프리셋·주문이 프롬프트에 들어간다).

`worker/tests/test_diary_integration.py`에 통합 케이스를 더한다:
- 재생성 요청이 있으면 `status='confirmed'`여도 다시 쓰이고, 요청이 **비워진다**.
- 요청이 없으면 기존 멱등 동작(재호출 no-op) 그대로.
- 재생성 시 `edited_text`가 비고 `status`가 `draft`가 된다.
- 사용자 프리셋이 프롬프트에 전달된다(스텁 writer가 받은 facts로 확인).

기존 테스트가 `fetch_existing_diary` 반환 모양 변경으로 깨지면 **함께 고친다**(약화 금지).

- [ ] **Step 5: 실행·커밋**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -q
worker\.venv\Scripts\python.exe -m ruff check worker
```

```powershell
git add worker/src worker/tests
git commit -m "feat(worker): 일기 톤 반영·재생성 요청 처리

사용자 기본 프리셋과 1회 주문을 프롬프트에 넣는다(문체만, 사실 불변).
재생성 요청이 있으면 status 무관하게 다시 쓰고 편집본을 비운 뒤 요청을
소비한다 — 자동 재생성이 아니라 명시 요청이다."
```

---

## Task 8: eval + 문서

**Files:** Modify `evals/diary/fixtures.json`·`run.py`, `README.md`, `supabase/README.md`

- [ ] **Step 1: 톤 불변성 eval**

같은 메모·차이로 `담백`·`따뜻` 두 번 생성해 **`used_memory_ids`가 같은지** 검사한다(사실 집합 불변 — 기획서 §4-9). 문체 차이는 검사하지 않는다.

`run.py`에 케이스를 더하되 실 호출은 **케이스당 2회**로 제한한다.

- [ ] **Step 2: 실행 (실 Vertex, 1회)**

```powershell
$env:GOOGLE_GENAI_USE_VERTEXAI = "true"
$env:GOOGLE_CLOUD_PROJECT = "project-58561b19-fb35-4c01-bb2"
$env:GOOGLE_CLOUD_LOCATION = "global"
worker\.venv\Scripts\python.exe evals/diary/run.py
```
FAIL이면 프롬프트·상수를 임의로 고치지 말고 **출력 그대로 보고**하라.

- [ ] **Step 3: 문서**

`README.md` 저장소 구조에 `app/settings/` 한 줄, 일기 화면 설명에 "고치기·확정·다시 만들기" 한 문장.
`supabase/README.md`의 "일기 생성" 절에 톤·재생성 요청 동작 두 줄.

- [ ] **Step 4: 전체 검사·커밋**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -q
worker\.venv\Scripts\python.exe -m ruff check worker
npx vitest run
npm run lint
npm run build
npx vitest run --config vitest.integration.config.mts
```

- [ ] **Step 5: 최종 보고**

`HANDOFF.md` "상태" 갱신·커밋. **push·merge는 하지 마라.**

---

## 완료 기준

- 일기를 **고치고 확정**할 수 있고, 안 건드리면 `draft`다.
- 확정한 일기를 **다시 고칠** 수 있다.
- 편집은 `edited_text`에만 쓰이고 **AI 초안이 남는다.**
- 기대 상태가 다르면 **409**(TOCTOU). 타 사용자 일기는 못 바꾼다.
- **설정에서 고른 톤이 다음 생성에 반영**된다.
- **다시 만들기**가 요청을 남기고, 다음 생성이 1회 반영한 뒤 **요청을 비운다.**
- 편집본에 다시 만들기를 누르면 **사라진다고 알리고 한 번 더 확인**받는다.
- 톤이 바뀌어도 **사실 집합이 같다**(eval).
- lint + build + vitest(단위·통합) + ruff + pytest 통과.

## 이번 범위 밖
즉시 반영(큐·폴링·처리중 UI) · `diary_time` 설정·알림(F4) · 일기 버전 보관 · 프리셋 3개 이상.
