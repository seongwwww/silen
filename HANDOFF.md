# HANDOFF — 활성 작업 인수인계 허브 (모든 AI 공용)

> 여러 AI(Claude · Codex · Gemini · Cursor)가 번갈아 작업하는 저장소의 **단일 인수인계 파일**이다.
> `AGENTS.md`(진입점·규칙)를 먼저 읽고, **"지금 무엇을 어떻게 할지"는 이 파일**을 본다.
> 역할 구분: `AGENTS.md`=변하지 않는 규칙 · `PROJECT_STATE.md`=전체 로드맵 · **`HANDOFF.md`=현재 작업+실행법+상태(매번 갱신)**.
> **작업을 멈추거나 세션 한도(≈80%)에 닿으면 아래 "상태"를 갱신하고 커밋한다** — 추적 안 된 변경은 다음 세션·에이전트에서 보이지 않는다.

---

## 현재 활성 작업 (Active Work Order)

**목표:** `docs/superpowers/plans/2026-07-26-confirm-ui.md`(확인 UI — 차이 맞아요/아니에요) 구현.
**성격:** 계획 확정 완료 — **"코드만 짜면 되는" 상태**. 재설계하지 말고 계획을 그대로 따른다(Locked Decisions로 모호함 제거됨).
**스펙 배경:** `docs/superpowers/specs/2026-07-26-confirm-ui-design.md`.
**브랜치:** `feat/confirm-ui`.

### 실행 방식 (플러그인 없이 수동)
Claude는 Superpowers 스킬로 수행하지만, **다른 AI(Codex 등)는 스킬이 없으니 아래를 수동으로** 밟는다. 계획 헤더의 "REQUIRED SUB-SKILL"은 무시. **Task 1 → 6 순서, TDD:**
- 태스크마다: ① 실패 테스트 작성 → ② 실행해 실패 확인 → ③ 계획의 코드 그대로 구현 → ④ 테스트 통과 → ⑤ lint clean → ⑥ **그 태스크 단위로 1커밋**.
- 계획 안의 명령을 그대로 실행한다. 코드·테스트를 임의로 바꾸지 않는다.

### 환경 (Windows, 프론트/앱 — 워커 아님)
- Node/npm. **앱 코드 작성 전 Next.js 16 문서**(`node_modules/next/dist/docs/01-app/`) 필독 — 동적 `params`는 Promise(`await ctx.params`) 등 학습데이터와 다르다.
- 로컬 Supabase `127.0.0.1:54322`. `npx supabase db reset` 뒤 auth 502 → 반드시 `npx supabase stop` → `npx supabase start` 후 통합 테스트. **로컬만, production 금지.**
- **Vertex/ADC 불필요**(이 기능은 앱·UI, 워커 아님).
- 테스트: `npx vitest run`(단위: 서비스·컴포넌트) · `npx vitest run --config vitest.integration.config.mts`(통합: 저장소·RLS, DB 필요) · `npm run lint` · `npm run build`(타입).
- Task 3 `npx shadcn@latest init -d`가 대화형으로 멈추면 기본값으로 답한다(Tailwind v4 자동 감지).

### 어기면 안 되는 것 (hard rules)
- **스키마 변경 없음** — 기존 `differences`·`difference_narrations`·`difference_evidence`·`memories`(RLS)를 재사용. 새 마이그레이션 만들지 마라.
- **태스크마다 커밋만. push·merge 금지**(사람이 한다).
- 이미 병합된 기능(**extraction·detector·narration·diary**)을 수정하지 마라 — 계획이 지정한 파일만 추가한다.
- 커밋 메시지의 `Co-Authored-By` 트레일러는 **네 것으로** 바꿔라(네가 저자다). git.md 규약.
- 못 고치는 테스트 실패나 모호한 점이 있으면 **멈추고 보고**하라. 추측하거나 테스트를 약화시키지 마라.
- 완료(DoD) = lint + typecheck(build) + unit + integration.

---

## 상태 (Status) — 멈출 때 여기를 갱신하고 커밋

- **계획 확정 커밋:** `6b58e49` · **스펙 커밋:** `9a546b1`.
- **구현 진행:** Task 1~5 완료. Task 6 문서·전체 검사 완료, 보안 리뷰 Important 판단 대기.
- **커밋된 태스크:** Task 1 `1f0c34a` · Task 2 `f5b409a` · Task 3 `448d201` · Task 4 `e1935e8` · Task 5 `36f8beb` · Task 6 문서 `626d2c2`.
- **검증:** lint PASS · 앱 단위 28 PASS · 현재 로컬 Supabase+라이브 Next 기준 통합 38 PASS · production build PASS. `/review` 모바일 390px empty 상태 육안 확인. 카드·낙관적 제거·실패 복구·undo는 컴포넌트 테스트 3 PASS. DB reset은 `AGENTS.md`상 사람이 실행해야 하므로 이번 세션에서 미실행.
- **다음 시작점:** 아래 보안 Important를 Claude/컨트롤러가 해결 또는 명시 수용. 해결 시 TDD 회귀 추가 → 전체 검사 → Task 6 Step 5 브랜치 마무리(병합·push는 사람).
- **참고:** 파이프라인 트리거가 없어 라이브 차이 데이터가 없다 → 통합 테스트는 계획의 시드로. 브라우저에는 로그인 UI가 없고 로컬 매직링크가 implicit hash로 돌아 서버 세션을 만들지 못해 시드 카드 종단 육안 확인은 불가했음(인증 우회/테스트 전용 경로 추가 안 함).
- **막힘/결정 필요:** (1) **보안 리뷰 Important — 상태 전이 TOCTOU.** PATCH가 현재 status를 조회·검증한 뒤 `updateStatus(id,target)`를 조건 없이 실행한다. 동시에 candidate→confirmed와 candidate→dismissed 요청이 오면 둘 다 candidate를 읽고 둘 다 성공해 직접 전이 금지를 우회할 수 있음. 해결 후보: 저장소 update에 expected current status 조건(`.eq("status", current)`)을 포함하고 0행이면 conflict/invalid_transition으로 처리 + 동시성/낡은 상태 회귀 테스트(계획 인터페이스 변경 필요). (2) `npm audit --omit=dev`: HIGH 3(기존 pinned Next 16.2.11→내장 postcss/sharp), MODERATE 3(새 `shadcn@4.15.0`→MCP SDK/Hono). audit 제안은 Next 9.3.3·shadcn 3.8.3 major downgrade라 자동 적용 금지. shadcn CLI를 devDependency로 옮길지와 Next 보안 업데이트 경로를 별도 결정해야 함. 그 외 PATCH 본인 소유권(RLS)·세션 없음 401·목록 교차 사용자 차단·본문/헤드라인 무로그는 HIGH/MEDIUM 없음.

> 직전 완료: 일기 생성(diary) 기능 — PR 병합됨(`main`). 상세는 git 히스토리.

> 갱신 예: `Task 1 완료 (커밋 abc1234). 다음: Task 2 저장소.`

---

## 참고 (context)

- **이 기능이 confirmed를 세운다:** 지금까지 `status='confirmed'` 차이를 만드는 경로가 없었다(그래서 일기는 메모-only였다). 확인 UI가 그 경로다 — 병합되면 일기에 차이가 담기기 시작한다. 단, detector가 차이를 자동 생성하는 트리거는 아직 없어 개발/테스트는 시드 데이터로.
- **이 기능 병합 후 후보:** 프론트 일기·기록 화면 · detector/diary 스케줄 트리거(파이프라인 자동 구동) · offline. 전체 로드맵은 `PROJECT_STATE.md`.
- Claude 세션이 서브에이전트 주도(SDD)로 돌 땐 `.superpowers/sdd/progress.md`에 더 세밀한 태스크 원장을 둔다(선택). **공용 진행 상태의 기준은 이 파일의 "상태" 절**이다.
