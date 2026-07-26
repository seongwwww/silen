# 확인 UI(confirm UI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/review`에서 narrated 후보 차이를 카드로 보여주고 맞아요/아니에요(+undo)로 확정한다 — `PATCH /api/differences/[id]`(3계층·RLS) + 서버 컴포넌트 패칭 + 낙관적 제거.

**Architecture:** 앱 2자산 3계층. 백엔드는 서비스(전이 규칙, 순수)→저장소(세션 클라이언트, user 스코프)→경계(route/서버컴포넌트). 프론트는 서버 컴포넌트가 목록을 패칭해 클라이언트 리스트에 주입, 클라이언트는 낙관적 제거+인라인 undo만. 첫 UI라 primitive는 shadcn 없이 Tailwind v4로 최소 hand-roll. 스키마 변경 없음.

**Tech Stack:** Next.js 16.2.11(App Router) · React 19 · TypeScript · Tailwind v4 · @supabase/ssr · zod 4 · Vitest 4 (+ 컴포넌트 테스트 도입)

## Global Constraints

- 산출물은 **코드**다. `main` 직접 커밋 금지 — `feat/confirm-ui` 브랜치(생성됨).
- 커밋 `<type>(<scope>): <한국어 요약>` + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` 트레일러. scope는 `api`·`ui`. **커밋만, push/merge는 사람.**
- **스키마 변경 없음** — `differences`(RLS: 소유자 for all), `difference_narrations`(select 정책), `difference_evidence`·`memories`(RLS) 재사용. 마이그레이션 만들지 마라.
- **앱 코드 전 Next.js 16 문서 필독**(AGENTS.md): `node_modules/next/dist/docs/01-app/`의 route-handlers·server component·loading/error 규약. 학습데이터와 다르다.
- **Next 16 동적 라우트 `params`는 Promise** — `PATCH(req, ctx)`에서 `const { id } = await ctx.params`. (문서 15-route-handlers.md:195 확인)
- **RLS가 유일한 소유권 방어** — 세션 Supabase 클라이언트로 조회/수정, `user_id=auth.uid()` 정책이 교차 사용자 차단. service_role 쓰지 않는다.
- **shadcn 미도입(스펙 이탈, 의도적)** — 실제 스택이 Tailwind v4 + 컴포넌트 라이브러리 전무라, 이 슬라이스는 Button/Card를 Tailwind v4로 hand-roll하고 undo는 인라인 바(토스트 라이브러리 없음). 새 런타임 의존성 0. shadcn은 UI가 늘 때 별도 도입.
- **프론트 컴포넌트 테스트 도입** — devDep `@testing-library/react`·`@testing-library/jest-dom`·`jsdom`·`@vitejs/plugin-react`. `vitest.config.mts`에 `react()` 플러그인 + `.tsx`/`components/**` include. 컴포넌트 테스트 파일은 `// @vitest-environment jsdom`.
- DoD = lint + typecheck + unit + integration. 파이프라인 트리거 없어 **시드 데이터로 통합 테스트**.
- 상태·라벨은 frontend.md: 죄책감·독려 금지 · "AI가 발견" 표현 금지("오늘의 다른 점") · 맞아요/아니에요 라벨+아이콘+위치 구분·44px·색만으로 전달 금지 · empty/loading/error 명시.

## 결정 고정 (Locked Decisions)

1. **전이 규칙** — 목표 status ∈ {`confirmed`,`dismissed`,`candidate`}. 허용 전이: `candidate`→`confirmed`|`dismissed`(확정), `confirmed`|`dismissed`→`candidate`(undo). 그 외(예: confirmed→dismissed 직접, 동일값) **거부(400)**.
2. **목록 대상** — `differences` where `user_id=auth.uid()` · `status='candidate'` · `evidence_state='intact'`, INNER JOIN `difference_narrations`(headline), LEFT JOIN 근거 메모(`difference_evidence`→`memories`, `deleted_at is null and is_locked=false`). headline 없는 후보는 제외.
3. **목록 응답 shape** — `{ id: string, headline: string, category: string, evidence: string[] }[]`. evidence는 근거 메모 raw_text 배열(최대 3개, 없으면 빈 배열).
4. **undo = 인라인 바(단일 슬롯)** — 액션 탭 → 카드 낙관적 제거 → `PATCH{status}` → 하단 "되돌리기" 바(5초). 되돌리기 탭 → `PATCH{candidate}` + 카드 복원. 5초 경과 → 바 사라짐(확정). 새 액션이 오면 이전 바 대체.
5. **PATCH 실패** — 카드 복원 + 에러 메시지("바꾸지 못했어요. 다시 시도"). 자동 재시도 없음.
6. **primitive** — `components/ui/Button.tsx`·`Card.tsx`(Tailwind v4, 무의존). 아이콘은 인라인 SVG(check·x). 색 토큰은 `app/globals.css` `@theme`에 success/danger/border 추가(라이트·다크).
7. **라우트** — `/review`. `app/review/page.tsx`(서버 컴포넌트, 목록 패칭 후 주입), `_components/ReviewList.tsx`(`"use client"`). `loading.tsx`·`error.tsx`.
8. **세션** — 서버 컴포넌트가 `createServerSupabase().auth.getUser()`. 세션 없거나 목록 0 → empty. `/review`는 세션을 새로 만들지 않는다(볼 게 없음).
9. **저장소 경계 예외** — 기존 eslint `no-restricted-paths` 예외에 `differenceRepository.ts` 추가(경계가 조립, memoryRepository와 동형).
10. **커밋 단위** — 태스크마다 1커밋. push/merge 안 함.

## File Structure

| 경로 | 책임 |
|------|------|
| `lib/services/difference.ts` | 전이 규칙(순수) + 목록 항목 타입 |
| `lib/services/difference.test.ts` | 전이 규칙 단위 |
| `lib/repositories/differenceRepository.ts` | 세션 클라이언트: updateStatus·listCandidatesForReview(user 스코프) |
| `lib/repositories/difference.integration.test.ts` | 조회·수정·RLS 통합 |
| `app/api/differences/[id]/route.ts` | PATCH 경계(zod·await params·에러 매핑) |
| `app/api/differences/[id]/route.integration.test.ts` | 라이브 PATCH(본인·타인·잘못된 전이) |
| `eslint.config.mjs`(수정) | differenceRepository 예외 |
| `app/globals.css`(수정) | success/danger/border 색 토큰 |
| `components/ui/Button.tsx`·`Card.tsx` | primitive(Tailwind v4) |
| `components/common/ConfirmActions.tsx` | 맞아요/아니에요 액션 쌍(변형 A) |
| `components/common/StateView.tsx` | empty/error/loading 재사용 뷰 |
| `components/common/ConfirmActions.test.tsx` | a11y·라벨·콜백 단위 |
| `app/review/page.tsx` | 서버 컴포넌트, 목록 패칭 |
| `app/review/_components/ReviewList.tsx` | 클라이언트: 카드·낙관적제거·undo·PATCH |
| `app/review/_components/ReviewList.test.tsx` | 낙관적 제거·undo·실패 복구 |
| `app/review/loading.tsx`·`error.tsx` | 상태뷰 |
| `vitest.config.mts`(수정) | react 플러그인·tsx include |

---

## Task 1: 전이 규칙 서비스 (순수)

**Files:** Create `lib/services/difference.ts`, `lib/services/difference.test.ts`

**Interfaces — Produces:**
```ts
export type DiffStatus = "candidate" | "confirmed" | "dismissed";
export interface ReviewItem { id: string; headline: string; category: string; evidence: string[]; }
export class InvalidTransitionError extends Error {}
export function assertValidTransition(current: DiffStatus, target: DiffStatus): void
```

- [ ] **Step 1: 실패 테스트** — `lib/services/difference.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { assertValidTransition, InvalidTransitionError } from "./difference";

describe("assertValidTransition", () => {
  it("candidate → confirmed/dismissed 허용", () => {
    expect(() => assertValidTransition("candidate", "confirmed")).not.toThrow();
    expect(() => assertValidTransition("candidate", "dismissed")).not.toThrow();
  });
  it("confirmed/dismissed → candidate(undo) 허용", () => {
    expect(() => assertValidTransition("confirmed", "candidate")).not.toThrow();
    expect(() => assertValidTransition("dismissed", "candidate")).not.toThrow();
  });
  it("confirmed → dismissed 직접 전이 거부", () => {
    expect(() => assertValidTransition("confirmed", "dismissed")).toThrow(InvalidTransitionError);
  });
  it("동일 상태 전이 거부", () => {
    expect(() => assertValidTransition("candidate", "candidate")).toThrow(InvalidTransitionError);
  });
});
```

- [ ] **Step 2: 실패 확인** — `worker` 아님. 앱 단위: `npx vitest run lib/services/difference.test.ts`. Expected: FAIL(모듈 없음).

- [ ] **Step 3: 구현** — `lib/services/difference.ts`:
```ts
export type DiffStatus = "candidate" | "confirmed" | "dismissed";

export interface ReviewItem {
  id: string;
  headline: string;
  category: string;
  evidence: string[];
}

export class InvalidTransitionError extends Error {
  constructor() {
    super("허용되지 않은 상태 전이");
    this.name = "InvalidTransitionError";
  }
}

const ALLOWED: Record<DiffStatus, DiffStatus[]> = {
  candidate: ["confirmed", "dismissed"],
  confirmed: ["candidate"],
  dismissed: ["candidate"],
};

/** 확정(candidate→confirmed/dismissed)과 되돌리기(→candidate)만 허용한다. */
export function assertValidTransition(current: DiffStatus, target: DiffStatus): void {
  if (!ALLOWED[current]?.includes(target)) {
    throw new InvalidTransitionError();
  }
}
```

- [ ] **Step 4: 통과 확인** — `npx vitest run lib/services/difference.test.ts` → 4 PASS. `npm run lint`.

- [ ] **Step 5: 커밋**
```powershell
git add lib/services/difference.ts lib/services/difference.test.ts
git commit -m "feat(api): 차이 상태 전이 규칙 (순수 서비스)

확정(candidate→confirmed/dismissed)과 되돌리기(→candidate)만 허용,
그 외 전이는 InvalidTransitionError. DB·프레임워크 모르는 순수 로직.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: 저장소 + PATCH 라우트 (RLS·통합)

**Files:** Create `lib/repositories/differenceRepository.ts`, `lib/repositories/difference.integration.test.ts`, `app/api/differences/[id]/route.ts`, `app/api/differences/[id]/route.integration.test.ts`; Modify `eslint.config.mjs`

**Interfaces — Consumes:** Task 1(`DiffStatus`,`ReviewItem`,`assertValidTransition`), 기존 `createServerSupabase`. **Produces:**
```ts
export function createDifferenceRepository(client: SupabaseClient): {
  updateStatus(id: string, status: DiffStatus): Promise<boolean>;   // 영향 행 있으면 true(RLS로 타인 것은 0행)
  listCandidatesForReview(): Promise<ReviewItem[]>;
};
```

- [ ] **Step 1: 저장소 구현** — `lib/repositories/differenceRepository.ts`:
```ts
import type { SupabaseClient } from "@supabase/supabase-js";
import type { DiffStatus, ReviewItem } from "@/lib/services/difference";

const MAX_EVIDENCE = 3;

/** 세션 클라이언트로 차이를 조회/수정한다. RLS(user_id=auth.uid())가 소유권을 강제하므로
 * service_role을 쓰지 않는다. */
export function createDifferenceRepository(client: SupabaseClient) {
  return {
    async updateStatus(id: string, status: DiffStatus): Promise<boolean> {
      const { data, error } = await client
        .from("differences")
        .update({ status })
        .eq("id", id)
        .select("id");
      if (error) throw error;
      return (data?.length ?? 0) > 0; // RLS로 타인 차이는 0행
    },

    async listCandidatesForReview(): Promise<ReviewItem[]> {
      const { data, error } = await client
        .from("differences")
        .select(
          "id, category, difference_narrations!inner(headline), " +
            "difference_evidence(memories(raw_text, is_locked, deleted_at))",
        )
        .eq("status", "candidate")
        .eq("evidence_state", "intact")
        .order("date", { ascending: false });
      if (error) throw error;
      return (data ?? []).map((row) => {
        const headline = (row.difference_narrations as { headline: string }[] | { headline: string })
          ? (Array.isArray(row.difference_narrations)
              ? row.difference_narrations[0]?.headline
              : (row.difference_narrations as { headline: string }).headline) ?? ""
          : "";
        const evidence = ((row.difference_evidence ?? []) as {
          memories: { raw_text: string | null; is_locked: boolean; deleted_at: string | null } | null;
        }[])
          .map((e) => e.memories)
          .filter((m): m is { raw_text: string; is_locked: boolean; deleted_at: string | null } =>
            !!m && !m.is_locked && !m.deleted_at && !!m.raw_text && m.raw_text.trim().length > 0)
          .map((m) => m.raw_text.trim())
          .slice(0, MAX_EVIDENCE);
        return { id: row.id as string, headline, category: row.category as string, evidence };
      });
    },
  };
}
```
> 구현자 주의: Supabase 중첩 select의 반환 형태(배열 vs 객체)는 관계 카디널리티에 따라 다르다. Step 2 통합 테스트로 실제 형태를 확인하고 위 매핑을 실데이터에 맞춘다(형태가 다르면 매핑만 조정, 쿼리 필터는 유지).

- [ ] **Step 2: 저장소 통합 테스트** — `lib/repositories/difference.integration.test.ts` (기존 `memory.integration.test.ts` 패턴: `adminClient`·`generateLink`·`verifyOtp`로 인증 클라이언트, `pg`로 시드):
```ts
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { Client } from "pg";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { adminClient, SUPABASE_URL, ANON_KEY } from "./testSupport";
import { createDifferenceRepository } from "./differenceRepository";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let admin: SupabaseClient, db: Client, alice: string, bob: string;

async function clientFor(email: string): Promise<SupabaseClient> {
  const { data } = await admin.auth.admin.generateLink({ type: "magiclink", email });
  const c = createClient(SUPABASE_URL, ANON_KEY, { auth: { autoRefreshToken: false, persistSession: false } });
  await c.auth.verifyOtp({ token_hash: data.properties.hashed_token, type: "magiclink" });
  return c;
}

async function seedCandidate(user: string, headline: string, memoText: string): Promise<string> {
  const ent = (await db.query(
    "insert into public.entities (user_id, entity_type, name, normalized_name) values ($1,'thing',$2,$2) returning id",
    [user, headline])).rows[0].id;
  const diff = (await db.query(
    "insert into public.differences (user_id, date, entity_id, dimension, description, detection_method, category, status, evidence_state) " +
    "values ($1, current_date, $2, 'thing', 'x', 'freq_shift', '오늘의다른점', 'candidate', 'intact') returning id",
    [user, ent])).rows[0].id;
  await db.query("insert into public.difference_narrations (user_id, difference_id, headline, body, evidence_text, model) values ($1,$2,$3,'b','e','m')",
    [user, diff, headline]);
  const mem = (await db.query("insert into public.memories (user_id, raw_text, source_type, memory_type) values ($1,$2,'manual','moment') returning id",
    [user, memoText])).rows[0].id;
  await db.query("insert into public.difference_evidence (difference_id, memory_id) values ($1,$2)", [diff, mem]);
  return diff;
}

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING }); await db.connect();
  alice = (await admin.auth.admin.createUser({ email: "alice-diff@example.com", email_confirm: true })).data.user!.id;
  bob = (await admin.auth.admin.createUser({ email: "bob-diff@example.com", email_confirm: true })).data.user!.id;
});
afterAll(async () => {
  await admin.auth.admin.deleteUser(alice); await admin.auth.admin.deleteUser(bob); await db.end();
});

describe("차이 확인 저장소", () => {
  it("narrated candidate + 근거 메모를 조회한다", async () => {
    const diff = await seedCandidate(alice, "3일째 김밥", "점심에 김밥");
    const repo = createDifferenceRepository(await clientFor("alice-diff@example.com"));
    const items = await repo.listCandidatesForReview();
    const item = items.find((i) => i.id === diff);
    expect(item).toBeTruthy();
    expect(item!.headline).toBe("3일째 김밥");
    expect(item!.evidence).toContain("점심에 김밥");
  });

  it("본인 차이 status를 바꾼다", async () => {
    const diff = await seedCandidate(alice, "새 카페", "처음 간 카페");
    const repo = createDifferenceRepository(await clientFor("alice-diff@example.com"));
    expect(await repo.updateStatus(diff, "confirmed")).toBe(true);
    const row = await db.query("select status from public.differences where id=$1", [diff]);
    expect(row.rows[0].status).toBe("confirmed");
  });

  it("타인 차이는 RLS로 못 바꾼다(0행)", async () => {
    const diff = await seedCandidate(alice, "앨리스 차이", "앨리스 메모");
    const bobRepo = createDifferenceRepository(await clientFor("bob-diff@example.com"));
    expect(await bobRepo.updateStatus(diff, "confirmed")).toBe(false);
    const row = await db.query("select status from public.differences where id=$1", [diff]);
    expect(row.rows[0].status).toBe("candidate"); // 안 바뀜
  });
});
```

- [ ] **Step 3: PATCH 라우트** — `app/api/differences/[id]/route.ts`:
```ts
import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDifferenceRepository } from "@/lib/repositories/differenceRepository";
import { assertValidTransition, InvalidTransitionError, type DiffStatus } from "@/lib/services/difference";

const bodySchema = z.object({ status: z.enum(["candidate", "confirmed", "dismissed"]) });

export async function PATCH(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  let parsed;
  try {
    parsed = bodySchema.parse(await request.json());
  } catch {
    return NextResponse.json({ error: { code: "invalid_body", message: "요청 형식이 올바르지 않습니다" } }, { status: 400 });
  }

  const supabase = await createServerSupabase();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: { code: "unauthorized", message: "세션이 필요합니다" } }, { status: 401 });
  }

  const repo = createDifferenceRepository(supabase);
  // 현재 status를 읽어 전이를 검증한다(본인 것만 보임 — RLS).
  const { data: current } = await supabase.from("differences").select("status").eq("id", id).maybeSingle();
  if (!current) {
    return NextResponse.json({ error: { code: "not_found", message: "차이를 찾을 수 없습니다" } }, { status: 404 });
  }
  try {
    assertValidTransition(current.status as DiffStatus, parsed.status);
  } catch (e) {
    if (e instanceof InvalidTransitionError) {
      return NextResponse.json({ error: { code: "invalid_transition", message: "허용되지 않은 변경입니다" } }, { status: 400 });
    }
    throw e;
  }
  const changed = await repo.updateStatus(id, parsed.status);
  if (!changed) {
    return NextResponse.json({ error: { code: "not_found", message: "차이를 찾을 수 없습니다" } }, { status: 404 });
  }
  return new NextResponse(null, { status: 204 });
}
```

- [ ] **Step 4: 라우트 통합 테스트** — `app/api/differences/[id]/route.integration.test.ts` (라이브 서버 대상, `memories/route.integration.test.ts` 패턴). 본인 인증 쿠키로 PATCH 200/204, 잘못된 전이 400, 없는 id 404. (인증 쿠키 세팅은 memories 통합 테스트의 방식을 따른다. 서버가 안 떠 있으면 skip 가드.)
```ts
import { describe, it, expect } from "vitest";
const BASE = process.env.APP_BASE_URL ?? "http://localhost:3000";

describe("PATCH /api/differences/[id] (라이브)", () => {
  it("잘못된 status는 400", async () => {
    const res = await fetch(`${BASE}/api/differences/00000000-0000-0000-0000-000000000000`, {
      method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ status: "bogus" }),
    });
    expect(res.status).toBe(400);
  });
});
```
> 구현자: 인증된 PATCH의 종단 검증은 저장소 통합 테스트(Step 2)가 이미 RLS·전이 경로를 덮으므로, 라우트 테스트는 검증/에러 매핑에 집중한다(과잉 구성 금지).

- [ ] **Step 5: eslint 예외** — `eslint.config.mjs`의 `no-restricted-paths` `except`에 `"./differenceRepository.ts"` 추가(memoryRepository와 동형; 주석: 경계가 client→repository 조립).

- [ ] **Step 6: 실행·커밋**
```powershell
npx supabase db reset; npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
npx vitest run --config vitest.integration.config.mts lib/repositories/difference.integration.test.ts
npm run lint
git add lib/repositories/differenceRepository.ts lib/repositories/difference.integration.test.ts app/api/differences eslint.config.mjs
git commit -m "feat(api): 차이 확인 저장소·PATCH 라우트 (RLS)

세션 클라이언트로 narrated 후보 조회·status 변경. RLS가 교차 사용자
차단(타인 차이 0행). 라우트는 zod·전이 검증·에러 매핑, params는 await.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: UI primitive + 색 토큰

**Files:** Modify `app/globals.css`; Create `components/ui/Button.tsx`, `components/ui/Card.tsx`

- [ ] **Step 1: 색 토큰** — `app/globals.css`의 `@theme inline` 아래에 추가(라이트) + 다크 미디어쿼리에도:
```css
@theme inline {
  --color-success-bg: #e1f5ee;
  --color-success-text: #0f6e56;
  --color-danger-text: #a32d2d;
  --color-line: #e5e5e5;
}
```
다크(`@media (prefers-color-scheme: dark)` `:root`)에:
```css
  --color-success-bg: #08302a;
  --color-success-text: #5dcaa5;
  --color-danger-text: #f09595;
  --color-line: #2a2a2a;
```

- [ ] **Step 2: Button** — `components/ui/Button.tsx`:
```tsx
import type { ButtonHTMLAttributes } from "react";

type Variant = "neutral" | "success";

/** 최소 primitive. 44px 터치 타깃, 포커스 링, prefers-reduced-motion 존중(트랜지션 없음). */
export function Button({ variant = "neutral", className = "", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const base =
    "inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-lg px-4 text-[15px] " +
    "border outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:opacity-50";
  const styles =
    variant === "success"
      ? "border-[var(--color-success-text)] bg-[var(--color-success-bg)] text-[var(--color-success-text)] font-medium"
      : "border-[var(--color-line)] bg-transparent text-[var(--foreground)]";
  return <button className={`${base} ${styles} ${className}`} {...props} />;
}
```

- [ ] **Step 3: Card** — `components/ui/Card.tsx`:
```tsx
import type { HTMLAttributes } from "react";
export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`rounded-xl border border-[var(--color-line)] p-4 ${className}`} {...props} />;
}
```

- [ ] **Step 4: 확인·커밋** — `npm run lint` (JSX 타입 통과). 시각 검증은 Task 5 이후 브라우저에서.
```powershell
git add app/globals.css components/ui/Button.tsx components/ui/Card.tsx
git commit -m "feat(ui): Tailwind v4 primitive(Button·Card)와 색 토큰

shadcn 없이 최소 hand-roll. 44px·포커스 링. success/danger/line 토큰
(라이트·다크). 첫 UI 기반.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: 공통 컴포넌트 + 컴포넌트 테스트 도입

**Files:** Modify `vitest.config.mts`, `package.json`; Create `components/common/ConfirmActions.tsx`, `components/common/StateView.tsx`, `components/common/ConfirmActions.test.tsx`

- [ ] **Step 1: 테스트 인프라** — devDep 설치 + vitest 설정:
```powershell
npm i -D @testing-library/react @testing-library/jest-dom jsdom @vitejs/plugin-react
```
`vitest.config.mts`를 수정: `react()` 플러그인 추가, `include`에 `.tsx`·`components/**` 포함.
```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  resolve: { tsconfigPaths: true },
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts", "app/**/*.test.{ts,tsx}", "components/**/*.test.tsx"],
    exclude: ["**/node_modules/**", "**/.next/**", "**/*.integration.test.*"],
  },
});
```
컴포넌트 테스트 파일 상단에 `// @vitest-environment jsdom` + `import "@testing-library/jest-dom/vitest";`.

- [ ] **Step 2: ConfirmActions 실패 테스트** — `components/common/ConfirmActions.test.tsx`:
```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmActions } from "./ConfirmActions";

describe("ConfirmActions", () => {
  it("맞아요/아니에요 라벨과 접근가능 이름이 있다", () => {
    render(<ConfirmActions onConfirm={() => {}} onDismiss={() => {}} />);
    expect(screen.getByRole("button", { name: "맞아요" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "아니에요" })).toBeInTheDocument();
  });
  it("탭하면 콜백이 불린다", async () => {
    const onConfirm = vi.fn(), onDismiss = vi.fn();
    render(<ConfirmActions onConfirm={onConfirm} onDismiss={onDismiss} />);
    await userEvent.click(screen.getByRole("button", { name: "맞아요" }));
    await userEvent.click(screen.getByRole("button", { name: "아니에요" }));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
```
> `@testing-library/user-event`는 `@testing-library/react`에 포함되지 않으면 함께 설치한다: `npm i -D @testing-library/user-event`.

- [ ] **Step 3: ConfirmActions 구현** — `components/common/ConfirmActions.tsx`:
```tsx
import { Button } from "@/components/ui/Button";

const IconCheck = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M5 12l4 4L19 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
);
const IconX = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
);

/** 차이 확정 액션 쌍. 아니에요(왼쪽)·맞아요(오른쪽), 색+아이콘+라벨로 구분(색만 X),
 * 44px, 사이 간격으로 오탭 방지. frontend.md 공통 컴포넌트. */
export function ConfirmActions({ onConfirm, onDismiss }: { onConfirm: () => void; onDismiss: () => void }) {
  return (
    <div className="flex gap-3">
      <Button variant="neutral" className="flex-1" onClick={onDismiss}>
        <span className="text-[var(--color-danger-text)]"><IconX /></span>아니에요
      </Button>
      <Button variant="success" className="flex-1" onClick={onConfirm}>
        <IconCheck />맞아요
      </Button>
    </div>
  );
}
```

- [ ] **Step 4: StateView** — `components/common/StateView.tsx`:
```tsx
/** empty/error/loading 재사용 뷰. 담담한 문구(죄책감·독려 금지). */
export function EmptyState({ message = "확인할 차이가 없어요" }: { message?: string }) {
  return <p className="py-16 text-center text-[15px] text-[var(--foreground)] opacity-60">{message}</p>;
}
export function ErrorState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div className="py-16 text-center">
      <p className="text-[15px] opacity-70">불러오지 못했어요.</p>
      {onRetry && <button className="mt-2 underline" onClick={onRetry}>다시 시도</button>}
    </div>
  );
}
export function LoadingState() {
  return <div className="space-y-3 py-4" aria-hidden="true">
    {[0, 1, 2].map((i) => <div key={i} className="h-24 rounded-xl border border-[var(--color-line)]" />)}
  </div>;
}
```

- [ ] **Step 5: 실행·커밋** — `npx vitest run components/common/ConfirmActions.test.tsx` → PASS. `npm run lint`.
```powershell
git add package.json package-lock.json vitest.config.mts components/common
git commit -m "feat(ui): ConfirmActions·상태뷰 공통 컴포넌트 + 컴포넌트 테스트 도입

맞아요/아니에요 액션 쌍(색+아이콘+라벨 구분·44px·오탭 방지), empty/error/
loading 재사용 뷰. Vitest에 react 플러그인·jsdom 도입.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: /review 페이지 + ReviewList (낙관적·undo)

**Files:** Create `app/review/page.tsx`, `app/review/_components/ReviewList.tsx`, `app/review/_components/ReviewList.test.tsx`, `app/review/loading.tsx`, `app/review/error.tsx`

- [ ] **Step 1: 서버 페이지** — `app/review/page.tsx`:
```tsx
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDifferenceRepository } from "@/lib/repositories/differenceRepository";
import { EmptyState } from "@/components/common/StateView";
import { ReviewList } from "./_components/ReviewList";

export default async function ReviewPage() {
  const supabase = await createServerSupabase();
  const { data: { user } } = await supabase.auth.getUser();
  const items = user ? await createDifferenceRepository(supabase).listCandidatesForReview() : [];
  return (
    <main className="mx-auto max-w-md p-4">
      <h1 className="mb-4 text-lg font-medium">오늘의 다른 점</h1>
      {items.length === 0 ? <EmptyState /> : <ReviewList items={items} />}
    </main>
  );
}
```

- [ ] **Step 2: ReviewList 실패 테스트** — `app/review/_components/ReviewList.test.tsx`:
```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReviewList } from "./ReviewList";

const items = [{ id: "d1", headline: "3일째 김밥", category: "오늘의다른점", evidence: ["점심에 김밥"] }];

beforeEach(() => { vi.restoreAllMocks(); });

describe("ReviewList", () => {
  it("맞아요 탭하면 카드가 사라지고 되돌리기 바가 뜬다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    render(<ReviewList items={items} />);
    await userEvent.click(screen.getByRole("button", { name: "맞아요" }));
    expect(screen.queryByText("3일째 김밥")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "되돌리기" })).toBeInTheDocument();
  });
  it("되돌리기 탭하면 카드가 복원된다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    render(<ReviewList items={items} />);
    await userEvent.click(screen.getByRole("button", { name: "아니에요" }));
    await userEvent.click(screen.getByRole("button", { name: "되돌리기" }));
    expect(screen.getByText("3일째 김밥")).toBeInTheDocument();
  });
  it("PATCH 실패면 카드가 복원되고 에러가 뜬다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    render(<ReviewList items={items} />);
    await userEvent.click(screen.getByRole("button", { name: "맞아요" }));
    await waitFor(() => expect(screen.getByText("3일째 김밥")).toBeInTheDocument());
    expect(screen.getByText(/다시 시도/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: ReviewList 구현** — `app/review/_components/ReviewList.tsx`:
```tsx
"use client";
import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { ConfirmActions } from "@/components/common/ConfirmActions";
import type { ReviewItem, DiffStatus } from "@/lib/services/difference";

async function patch(id: string, status: DiffStatus): Promise<boolean> {
  const res = await fetch(`/api/differences/${id}`, {
    method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ status }),
  });
  return res.ok;
}

export function ReviewList({ items }: { items: ReviewItem[] }) {
  const [list, setList] = useState(items);
  const [undo, setUndo] = useState<ReviewItem | null>(null);
  const [error, setError] = useState(false);

  async function act(item: ReviewItem, status: "confirmed" | "dismissed") {
    setError(false);
    setList((l) => l.filter((x) => x.id !== item.id)); // 낙관적 제거
    setUndo(item);
    if (!(await patch(item.id, status))) {
      setList((l) => [item, ...l]); // 복원
      setUndo(null);
      setError(true);
    }
  }
  async function doUndo() {
    if (!undo) return;
    const item = undo;
    setUndo(null);
    if (await patch(item.id, "candidate")) setList((l) => [item, ...l]);
    else setError(true);
  }

  return (
    <div className="space-y-3">
      {error && <p role="alert" className="text-[13px] text-[var(--color-danger-text)]">바꾸지 못했어요. 다시 시도해 주세요.</p>}
      {list.map((item) => (
        <Card key={item.id}>
          <span className="inline-block rounded-full bg-[var(--color-success-bg)] px-2.5 py-0.5 text-[12px] text-[var(--color-success-text)]">오늘의 다른 점</span>
          <p className="mt-2 text-[16px] font-medium">{item.headline}</p>
          {item.evidence.length > 0 && (
            <>
              <p className="mt-2 text-[13px] opacity-60">이 기록에서 찾았어요</p>
              <div className="mb-4 mt-1.5 flex flex-wrap gap-1.5">
                {item.evidence.map((e, i) => (
                  <span key={i} className="rounded-lg border border-[var(--color-line)] px-2.5 py-1 text-[13px] opacity-70">{e}</span>
                ))}
              </div>
            </>
          )}
          <div className={item.evidence.length > 0 ? "" : "mt-4"}>
            <ConfirmActions onConfirm={() => act(item, "confirmed")} onDismiss={() => act(item, "dismissed")} />
          </div>
        </Card>
      ))}
      {undo && (
        <div className="flex items-center justify-between rounded-lg border border-[var(--color-line)] px-4 py-3 text-[14px]">
          <span className="opacity-70">처리했어요</span>
          <button className="font-medium underline" onClick={doUndo}>되돌리기</button>
        </div>
      )}
    </div>
  );
}
```
> undo 바의 5초 자동 소멸은 MVP에서 생략 가능(바는 다음 액션 시 대체되고, 남아 있어도 무해). 구현자가 `useEffect` 타이머로 5초 후 `setUndo(null)`를 추가해도 되며, 테스트는 타이머에 의존하지 않는다.

- [ ] **Step 4: loading·error** —
`app/review/loading.tsx`:
```tsx
import { LoadingState } from "@/components/common/StateView";
export default function Loading() {
  return <main className="mx-auto max-w-md p-4"><LoadingState /></main>;
}
```
`app/review/error.tsx`:
```tsx
"use client";
import { ErrorState } from "@/components/common/StateView";
export default function Error({ reset }: { error: Error; reset: () => void }) {
  return <main className="mx-auto max-w-md p-4"><ErrorState onRetry={reset} /></main>;
}
```

- [ ] **Step 5: 실행·시각 확인·커밋** — `npx vitest run app/review` → PASS. `npm run lint && npm run build`(타입 체크). 로컬에서 `/review` 육안 확인(시드 데이터로 카드·맞아요/아니에요·undo 동작).
```powershell
git add app/review
git commit -m "feat(ui): /review 확인 화면 — 카드·낙관적 제거·undo

서버 컴포넌트가 narrated 후보를 패칭해 주입, 클라이언트는 맞아요/아니에요
낙관적 제거 + 되돌리기 + 실패 복구. loading/error/empty 상태.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: 문서·검증·마무리

**Files:** Modify `README.md`

- [ ] **Step 1: README** — 구조 절에 `app/review/`(확인 화면)·`components/{ui,common}/`·`app/api/differences/`를 추가하고, 확인 UI 한 줄 설명.

- [ ] **Step 2: 전체 검사**
```powershell
npm run lint
npx vitest run                       # 앱 단위(서비스·컴포넌트)
npx supabase db reset; npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
npx vitest run --config vitest.integration.config.mts
npm run build                        # 타입·빌드
```
Expected: 전부 통과.

- [ ] **Step 3: 커밋**
```powershell
git add README.md
git commit -m "docs: 확인 UI(/review) 구조 안내

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 4: 보안 리뷰** — 인증·소유권 변경이므로 `/security-review`(privacy.md). 중점: PATCH가 본인 차이만(RLS·전이 검증), 세션 없을 때 401, 목록이 타 사용자 데이터 안 섞임, 본문·헤드라인을 로그에 안 남김.

- [ ] **Step 5: 브랜치 마무리** — `/superpowers:finishing-a-development-branch`. rebase 후 `merge --no-ff`(squash 금지). 병합·push는 사람.

---

## 완료 기준
- `/review`가 narrated 후보를 카드로 보여주고 맞아요/아니에요로 확정, undo·실패 복구 동작.
- PATCH가 본인 차이만 변경(RLS)·전이 검증, 세션/에러 상태 처리.
- empty/loading/error 상태, ConfirmActions 색+아이콘+라벨 구분·44px.
- 단위(서비스·컴포넌트) + 통합(저장소·RLS) + lint + build 통과. 스키마 변경 없음.

## 이번 범위 밖
- 홈·일기·기록 화면 · offline·애니메이션 · 원본/생성물 구분 표식 · shadcn 도입.
- 파이프라인 트리거 배선(추출·detector 자동 구동) · 실데이터 · 확정 후 일기 재생성.
