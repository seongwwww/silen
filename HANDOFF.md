# HANDOFF — 활성 작업 인수인계 허브 (모든 AI 공용)

> 여러 AI(Claude · Codex · Gemini · Cursor)가 번갈아 작업하는 저장소의 **단일 인수인계 파일**이다.
> `AGENTS.md`(진입점·규칙)를 먼저 읽고, **"지금 무엇을 어떻게 할지"는 이 파일**을 본다.
> 역할 구분: `AGENTS.md`=변하지 않는 규칙 · `PROJECT_STATE.md`=전체 로드맵 · **`HANDOFF.md`=현재 작업+실행법+상태(매번 갱신)**.
> **작업을 멈추거나 세션 한도(≈80%)에 닿으면 아래 "상태"를 갱신하고 커밋한다** — 추적 안 된 변경은 다음 세션·에이전트에서 보이지 않는다.

---

## 현재 활성 작업 (Active Work Order)

**목표:** `docs/superpowers/plans/2026-07-27-diary-view.md`(일기 보기 화면 `/diary`) 구현.
**성격:** 계획 확정 완료 — **"코드만 짜면 되는" 상태**. 재설계하지 말고 계획을 그대로 따른다(10개 Locked Decisions로 모호함 제거됨).
**스펙 배경:** `docs/superpowers/specs/2026-07-27-diary-view-design.md`.
**브랜치:** **`feat/diary-view`를 `main`에서 새로 만들어** 작업한다(`git checkout -b feat/diary-view main`). 스펙·계획은 이미 `main`에 있다.
**왜 이게 지금 중요한가:** 파이프라인이 일기를 만들지만 **볼 화면이 없다.** 기록(`/`)과 확인(`/review`)은 있는데 끝단 산출물이 사용자에게 도달하지 않는다. 이 화면이 루프를 닫는다.

### 실행 방식 (플러그인 없이 수동)
Claude는 Superpowers 스킬로 수행하지만, **다른 AI(Codex 등)는 스킬이 없으니 아래를 수동으로** 밟는다. 계획 헤더의 "REQUIRED SUB-SKILL"은 무시. **Task 1 → 5 순서, TDD:**
- 태스크마다: ① 실패 테스트 작성 → ② 실행해 실패 확인 → ③ 계획의 코드 그대로 구현 → ④ 테스트 통과 → ⑤ lint clean → ⑥ **그 태스크 단위로 1커밋**.
- 계획 안의 명령을 그대로 실행한다. 코드·테스트를 임의로 바꾸지 않는다.

### 환경 (Windows, 프론트 슬라이스)
- Node/npm. **앱 코드 작성 전 Next.js 16 문서**(`node_modules/next/dist/docs/01-app/`) 필독 — 학습데이터와 API·관례가 다르다.
- **로컬 Supabase 스택이 떠 있어야 한다**(Task 1 통합 테스트). `npx supabase status`로 확인.
  `npx supabase db reset` 후에는 반드시 `npx supabase stop; Start-Sleep -Seconds 3; npx supabase start`로 auth 502를 복구한다.
- **Vertex/ADC 불필요** — 이 기능은 LLM을 부르지 않는다.
- 테스트: `npx vitest run`(단위) · `npm run lint` · `npm run build`(타입) · `npx vitest run --config vitest.integration.config.mts`(통합).
- shadcn은 이미 도입돼 있다(button·card·sonner·textarea). 새로 추가할 게 없다.

### 어기면 안 되는 것 (hard rules)
- **스키마 변경·마이그레이션·API 라우트·워커 변경 없음.** 읽기 전용 프론트 슬라이스다. 서버 컴포넌트가 저장소를 직접 부른다(`/review` 선례) — 새 라우트를 만들지 마라.
- ⚠️ **`components/common/StateView.tsx`를 수정하지 마라.** "아직 일기가 만들어지지 않았어요"는 기존 `EmptyState`에 `message`를 넘겨 쓴다. 기본 문구만 다른 컴포넌트를 새로 만들면 **verbatim 중복**이다(Locked Decision — 스펙 §5).
- ⚠️ **"오늘의 일기"가 아니라 "가장 최근 일기"다.** `run-diary`는 사용자 로컬 **어제**를 대상으로 돌아 최신 일기는 보통 어제 것이다. 오늘 날짜로 필터하면 화면이 거의 항상 비어 있게 된다(Locked Decision 1).
- ⚠️ **터치 타깃 44px** — 토글은 `min-h-11`을 쓴다. `min-h-9`(36px)는 `frontend.md` 위반이다(record-screen에서 같은 실수가 한 번 났다).
- **잠긴(`is_locked`)·삭제된(`deleted_at`) 메모를 근거에 노출하지 마라**(privacy.md — 잠근 기억은 노출 경로에서 빠진다). 저장소 계층에서 거른다.
- **죄책감 유도 문구 금지**(frontend.md): "일기를 써보세요"·"N일째 비어 있어요" 같은 독려·압박 표현을 쓰지 마라. 없으면 담담히 없다고 말한다.
- **색만으로 의미를 전달하지 마라** — AI 생성물/원본 구분에 라벨을 병행한다.
- **저장소는 세션 클라이언트 + RLS.** `service_role`을 쓰지 마라(`differenceRepository` 선례).
- 🚫 **`run-diary`를 실행하지 마라(실 LLM 비용).** 육안 확인용 일기가 필요하면 사람에게 요청하라.
- **태스크마다 커밋만. push·merge 금지**(사람이 한다).
- 이미 병합된 기능(**extraction·detector·narration·diary·confirm-ui·record-screen·pipeline-trigger**)을 수정하지 마라 — 계획이 지정한 파일만 추가한다.
- 커밋 메시지의 `Co-Authored-By` 트레일러는 **네 것으로** 바꿔라(네가 저자다). git.md 규약.
- 못 고치는 테스트 실패나 모호한 점이 있으면 **멈추고 보고**하라. 추측하거나 테스트를 약화시키지 마라.
- 완료(DoD) = lint + typecheck(build) + unit + integration. **eval은 이 기능 대상 아님**(프롬프트·모델 미변경).

---

## 상태 (Status) — 멈출 때 여기를 갱신하고 커밋

- **스펙 커밋:** `4a4bd0d` 계열(일기 보기 설계) · **계획 확정 커밋:** 최신 `docs: 일기 보기 화면 구현 계획`. 둘 다 **`main`에 있다**(문서는 main 직접 커밋 허용, git.md).
- **구현 진행:** `feat/diary-view`에서 **Task 1~5 전체 완료**.
  - Task 1 저장소·통합 테스트 완료 — 커밋 `8d0cbbb`
  - Task 2 근거 메모 접기 완료 — 커밋 `7acdfbf`
  - Task 3 일기 표시 컴포넌트 완료 — 커밋 `d502b0d`
  - Task 4 페이지 배선·상태 분기·계층 예외·select 타입 수정 완료 — 커밋 `cec3bb8`
  - Task 5 README 안내 완료 — 커밋 `8832130`
- **시작 전 확인 결과:** 최신 `main`에서 브랜치를 만들었고 로컬 Supabase API·DB가 실행 중이다. 선택 서비스(`imgproxy`·`edge_runtime`·`pooler`) 정지는 Task 1 통합 테스트에 영향 없었다.
- **최종 검증 결과:** `npm run lint` PASS · `npm run build` PASS(`/diary` 동적 라우트 생성) · 프론트 단위 **49 PASS**(기준선 40 + 새 9) · 통합 **44 PASS**(기존 39 + 새 5).
  - 최초 최종 통합 실행에서 기존 `/api/differences/[id]` 라이브 테스트가 500을 반환했으나, 응답은 코드 오류가 아니라 장시간 실행 중이던 dev 서버의 `Jest worker encountered 2 child process exceptions`였다. dev 서버만 재시작하자 같은 요청이 400으로 정상화됐고 통합 44건 전체가 통과했다.
- **✅ 해결된 결정 — 불릿 충돌(Codex 캐치가 옳았음).** 계획 Task 3의 테스트는 정확 일치를 요구하는데 같은 계획의 구현이 `<li>· {d}</li>`로 불릿을 텍스트에 넣어 모순이었다. **계획의 버그였고 (A)로 확정** — 불릿을 CSS `::marker`(`list-disc`)로 옮겨 접근 가능한 텍스트에 차이 문장만 남긴다.
  - 근거: `·`는 장식이라 접근 가능한 텍스트에 있으면 스크린리더가 "가운데점 …"으로 읽는다. `<ul>/<li>`가 이미 목록 의미를 전달하므로 문자 불릿은 중복이다. (B)는 접근성 노이즈를 남기면서 테스트도 약화시켜 둘 다 잃는다.
  - 조치: 계획 Task 3 구현 코드를 `list-disc pl-5`로 고치고 **Locked Decision #11**("장식 문자를 접근 가능한 텍스트에 넣지 마라 — 계획 예시 코드와 접근성 규칙이 어긋나면 규칙이 이긴다")을 추가했다. record-screen의 44px 선례와 같은 판단이다.
  - **`app/diary/_components/DiaryView.tsx`에 적용해 검증했고(5/5 PASS), Task 3 커밋 `d502b0d`에 포함했다.**
- **✅ 해결된 결정 — Task 4 계층 lint 충돌(Codex 캐치가 옳았음). (A)로 확정** — `eslint.config.mjs` 예외 목록에 `./diaryRepository.ts`를 추가한다.
  - 근거: 규칙 주석이 예외 기준을 "경계가 조립하는 인프라(팩토리)"로 명시한다. `diaryRepository`는 세션 client를 받는 팩토리이고, `/diary`는 `/review`와 구조가 같은 RLS 스코프 읽기 전용 화면이다 — `differenceRepository.ts`가 예외에 있는 것과 같은 이유다.
  - (B)를 버린 이유: 읽기 화면엔 서비스에 넣을 도메인 로직이 없어 통과용 계층만 늘고, `/diary`만 `/review`와 다른 패턴이 되어 다음 사람이 어느 쪽을 따를지 알 수 없게 된다.
  - 예외 목록이 닳지 않도록 주석을 남겼다: 읽기 화면이 또 늘면 목록 대신 "`*Repository.ts` 팩토리 허용"으로 기준 자체를 다시 세울 것.
- **✅ 해결된 문제 — Task 1 타입 에러(계획 버그).** `diaryRepository`의 `select()` 인자를 가독성 때문에 `+`로 이어붙였더니 리터럴 타입이 아니라 `string`이 되어 supabase-js의 select 타입 추론이 깨졌다(`row.diary_sections`가 `GenericStringError`). **한 줄 문자열 리터럴로 고쳤다.**
  - 이 오류는 lint·단위 테스트로 안 잡히고 **`npm run build`(tsc)에서만** 드러난다. → **Locked Decision 13**: 태스크마다 build를 돌려라.
- **조치 완료:** `eslint.config.mjs` 예외 추가 + `lib/repositories/diaryRepository.ts` select 한 줄화는 Task 4 커밋 `cec3bb8`에 포함했다. 계획의 **Locked Decision 12·13**을 따랐다.
- **막힘:** 없음. `run-diary`·스키마 변경·API/워커 변경은 하지 않았고, push·merge도 하지 않았다.
- **다음 시작점:** 사람이 `feat/diary-view` 커밋들을 검토한 뒤 push·merge한다.
- **참고:** 로컬 개발 DB에 합성 기록 1건(`브라우저 확인용 기록`)이 남아 있다(로컬 dev DB라 무해). 사용자 소유 미추적 `.claude/orchestration/`·`.claude/settings.local.json`은 건드리지 마라.

> 직전 완료: 파이프라인 트리거(`feat/pipeline-trigger`) — 병합·push 완료(`3c90e5d`). 워커 CLI 3명령, 재실행 시 LLM 재과금 차단.

> 직전 완료: 기록 화면(`feat/record-screen`) — 병합·push 완료(`d42906b`). 44px 규칙 준수로 확정.

> 직전 완료: 확인 UI(`feat/confirm-ui`) — 병합됨. TOCTOU 보안 수정 포함. 상세는 git 히스토리.

> 직전 완료: 일기 생성(diary) 기능 — 병합됨(`main`). 상세는 git 히스토리.

> 갱신 예: `Task 1 완료 (커밋 abc1234). 다음: Task 2 저장소.`

---

## 참고 (context)

- **파이프라인 순서(이 기능이 여는 것):** 메모 insert → DB 트리거가 pgmq `memory_jobs`에 적재 → `run-pending`이 소비해 엔티티 추출 → `run-daily`가 차이 검출·서술 → **사람이 확인 UI에서 확정** → `run-diary`가 확정 차이를 녹인 일기 생성.
  일기는 `status='confirmed'` 차이만 쓰므로 `run-daily`와 `run-diary` 사이에 **사람의 확정**이 들어가야 한다. 그래서 명령이 둘로 나뉜다.
- **이 화면이 "지금 만들기" 버튼을 두지 않는 이유:** `backend.md` — 앱과 워커는 큐·DB로만 통신하고 서로 직접 호출하지 않는다. 현재 큐(`memory_jobs`)는 추출 전용이고 일기 잡 큐가 없다. 일기 생성은 사람이 `run-diary`를 실행하거나 스케줄러가 돈다.
- **이 기능 병합 후 후보:** 일기 편집·확정 · 날짜 이동/목록 · 기록 열람 · 사진 첨부. 전체 로드맵은 `PROJECT_STATE.md`.
- Claude 세션이 서브에이전트 주도(SDD)로 돌 땐 `.superpowers/sdd/progress.md`에 더 세밀한 태스크 원장을 둔다(선택). **공용 진행 상태의 기준은 이 파일의 "상태" 절**이다.
