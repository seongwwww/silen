# 확인 UI(confirm UI) 설계 스펙 — 차이 맞아요/아니에요

> 상태: 확정(브레인스토밍 승인). 다음 단계: 구현 계획(writing-plans).
> 핵심 원칙(frontend.md): 죄책감·독려 금지 · "AI가 발견" 표현 금지, "왜 찾았는지"를 사람 말로 · 맞아요/아니에요 명확 구분(색·위치·라벨, 오탭 방지) · 색만으로 의미 전달 금지 · 상태뷰 명시 · 공통 컴포넌트 분리.

## 1. 목적·경계

detector가 만든 후보 차이(`differences.status='candidate'`)를 사용자가 **맞아요/아니에요**로 확정한다. 이게 있어야 확정 차이가 일기(diary)에 들어간다. 이 저장소 **첫 실질 UI 기능**이라 shadcn·디자인 토큰·공통 컴포넌트를 여기서 세운다.

**경계:** 확정 UI만. 차이를 만들지도(detector), 서술하지도(narration), 일기를 만들지도 않는다. 파이프라인 트리거 배선은 범위 밖 → **시드 데이터로 개발·테스트**.

## 2. 라우트·데이터 (서버 패칭)

- 전용 라우트 **`/review`** — "오늘의 다른 점". **서버 컴포넌트가 목록을 서버에서 패칭**(frontend.md: 컴포넌트 안 패칭 금지, props 주입). 세션은 서버 Supabase 클라이언트에서. 세션 없으면 빈 상태(auth 미들웨어 규약 따름).
- **표시 대상 = narration headline 있는 candidate + intact.** 쿼리: `differences` where `user_id=auth.uid()` · `status='candidate'` · `evidence_state='intact'`, **INNER JOIN `difference_narrations`**(headline이 유일한 사람-표시 텍스트, 없으면 미표시) + 근거 메모(`difference_evidence`→`memories.raw_text`, 잠금·삭제 제외) → `{id, headline, category, evidence: string[]}`.

## 3. 변경 (확정/거부/undo) — PATCH Route Handler

- **`PATCH /api/differences/[id]` `{ status }`** — `confirmed`(맞아요)·`dismissed`(아니에요)·`candidate`(undo). 세션 클라이언트로 실행, **RLS(`for all ... using/with check user_id=auth.uid()`)가 소유권 강제**. 스키마 변경 없음.
- 3계층(backend.md): 경계(route: zod 검증·인증) → 서비스(전이 검증: candidate↔confirmed/dismissed, undo→candidate만 허용) → 저장소(differences.status 갱신, user 스코프).
- 응답: 200/204. 실패는 4xx/5xx 구조화 에러.

## 4. 상호작용 (frontend.md)

- 탭 → **낙관적 제거**(카드가 리스트에서 즉시 빠짐) + 하단 **"되돌리기" 토스트(~5s)**. status는 백그라운드 PATCH.
- 되돌리기 탭 → `candidate`로 PATCH, 카드 복원.
- PATCH 실패 → 카드 복구 + 에러 토스트("바꾸지 못했어요. 다시 시도"). 자동 무한 재시도 금지.
- 낙관적 UI는 **내 행동**에만(AI 생성 결과를 미리 보여주는 게 아니라 안전, frontend.md 취지 유지).

## 5. 상태뷰 (Next App Router 관례)

- `app/review/loading.tsx` — 스켈레톤.
- `app/review/error.tsx` — "불러오지 못했어요" + 재시도.
- **empty** — 리스트 0건: "확인할 차이가 없어요"(담담, 죄책감·독려 문구 금지). 다 확정했거나 애초에 없을 때 동일.
- offline·processing 상태는 재사용 컴포넌트에 자리만 두고 유예(스텁).

## 6. 공통 컴포넌트 (frontend.md "지금 뺌")

- **`components/common/ConfirmActions.tsx`** — 맞아요/아니에요 액션 쌍. 변형 A: 맞아요=옅은 초록 채움(`bg-success`)+체크 아이콘, 아니에요=중립 외곽선+X 아이콘. 순서 **아니에요(왼쪽)·맞아요(오른쪽)**, 각 44px+, 사이 간격으로 오탭 방지. 라벨+아이콘 병행(색만으로 전달 X). props: `onConfirm`·`onDismiss`. 접근성(라벨·포커스) 기본 제공.
- **`components/common/StateView`** — empty/error/loading 재사용 뷰(offline/processing 스텁).
- **디자인 토큰** — shadcn/Tailwind 테마 기반(spacing/color/typography). 매직넘버 금지.
- 원본/생성물 구분 표식은 순수 확인 화면엔 불필요 → 유예.

## 7. 아키텍처

- **프론트:** `app/review/page.tsx`(서버 컴포넌트, 목록 조회 후 주입) → `app/review/_components/ReviewList.tsx`(`"use client"`: 카드 렌더 + 낙관적 제거 + undo + PATCH 호출).
- **백엔드(앱, 3계층):** `app/api/differences/[id]/route.ts`(경계) → `lib/services/difference.ts`(전이 규칙) → `lib/repositories/differenceRepository.ts`(세션 클라이언트, user 스코프). 목록 조회도 서비스/저장소 경유(서버 컴포넌트가 호출).
- 첫 UI 세팅: shadcn init + `Button`·`Card`·`Sonner`(토스트).
- **Next.js 16 주의(AGENTS.md):** 앱 코드 전 `node_modules/next/dist/docs/`의 App Router 문서(route handler·server component·loading/error 규약)를 먼저 읽는다.

## 8. 테스트 (DoD = lint + typecheck + unit + integration)

- **백엔드 통합:** PATCH가 본인 차이만 변경, 타인 차이 거부(RLS), 잘못된 전이(예: confirmed→candidate 외 임의 값) 거부. 목록 조회 서비스: candidate+narrated+intact만·user 스코프·잠금/삭제 근거 제외.
- **프론트 단위(Vitest+testing-library):** `ConfirmActions` 라벨/아이콘/접근성/콜백. `ReviewList` 낙관적 제거·undo 복원·PATCH 실패 시 복구.
- 시드 데이터로 검증(파이프라인 트리거 없음).

## 9. 범위 밖
- 홈·일기·기록 화면 · offline·애니메이션 · 원본/생성물 구분 표식.
- 파이프라인 트리거 배선(추출·detector 자동 구동) · detector 실데이터 · 주간 리포트.
- 확정 이후 소비(일기 재생성 등)는 기존 diary 기능 소관.

## 10. 주요 결정 요약
- **`/review` 전용 라우트, 서버 컴포넌트 패칭**, 클라이언트는 상호작용만.
- **표시 = narrated candidate(intact) + headline + 근거 메모 스니펫.**
- **PATCH `/api/differences/[id]`**(3계층·RLS), 맞아요=confirmed·아니에요=dismissed·undo=candidate.
- **낙관적 제거 + undo 토스트(~5s)**, 실패 복구.
- **공통 컴포넌트 지금 분리:** `ConfirmActions`(변형 A) · 상태뷰 · 디자인 토큰. shadcn 도입.
- **스키마 변경 없음**(RLS가 이미 select/update 허용).
