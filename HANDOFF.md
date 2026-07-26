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
- **구현 진행:** 0 / 6 태스크.
- **커밋된 태스크:** (없음)
- **다음 시작점:** Task 1 — `lib/services/difference.ts` 전이 규칙(순수 단위 테스트부터).
- **참고:** 파이프라인 트리거가 없어 라이브 차이 데이터가 없다 → 통합 테스트는 계획의 시드로. Task 3 `shadcn@latest init -d`는 Tailwind v4 자동 감지(대화형이면 defaults).
- **막힘/결정 필요:** (없음)

> 직전 완료: 일기 생성(diary) 기능 — PR 병합됨(`main`). 상세는 git 히스토리.

> 갱신 예: `Task 1 완료 (커밋 abc1234). 다음: Task 2 저장소.`

---

## 참고 (context)

- **이 기능이 confirmed를 세운다:** 지금까지 `status='confirmed'` 차이를 만드는 경로가 없었다(그래서 일기는 메모-only였다). 확인 UI가 그 경로다 — 병합되면 일기에 차이가 담기기 시작한다. 단, detector가 차이를 자동 생성하는 트리거는 아직 없어 개발/테스트는 시드 데이터로.
- **이 기능 병합 후 후보:** 프론트 일기·기록 화면 · detector/diary 스케줄 트리거(파이프라인 자동 구동) · offline. 전체 로드맵은 `PROJECT_STATE.md`.
- Claude 세션이 서브에이전트 주도(SDD)로 돌 땐 `.superpowers/sdd/progress.md`에 더 세밀한 태스크 원장을 둔다(선택). **공용 진행 상태의 기준은 이 파일의 "상태" 절**이다.
