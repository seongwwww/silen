# HANDOFF — 활성 작업 인수인계 허브 (모든 AI 공용)

> 여러 AI(Claude · Codex · Gemini · Cursor)가 번갈아 작업하는 저장소의 **단일 인수인계 파일**이다.
> `AGENTS.md`(진입점·규칙)를 먼저 읽고, **"지금 무엇을 어떻게 할지"는 이 파일**을 본다.
> 역할 구분: `AGENTS.md`=변하지 않는 규칙 · `PROJECT_STATE.md`=전체 로드맵 · **`HANDOFF.md`=현재 작업+실행법+상태(매번 갱신)**.
> **작업을 멈추거나 세션 한도(≈80%)에 닿으면 아래 "상태"를 갱신하고 커밋한다** — 추적 안 된 변경은 다음 세션·에이전트에서 보이지 않는다.

---

## 현재 활성 작업 (Active Work Order)

**목표:** `docs/superpowers/plans/2026-07-27-diary-recap-followup.md`(일기 정화 · 오늘의 처음 recap · 꼬리 질문) 구현.
**성격:** 계획 확정 완료 — **"코드만 짜면 되는" 상태**. 재설계하지 말고 계획을 그대로 따른다(12개 Locked Decisions).
**스펙 배경:** `docs/superpowers/specs/2026-07-27-diary-recap-followup-design.md`.
**브랜치:** **`feat/diary-recap-followup`을 `main`에서 새로 만들어** 작업한다. 스펙·계획은 이미 `main`에 있다.
**왜 이게 지금 중요한가:** 파이프라인 첫 실데이터 완주에서 **출력 품질이 무너졌다.** 일기 본문이 *"~한 것도 오늘이 처음이다"* 를 6번 반복했고, *"일기에 출근이라는 행동이 기록된 것도 처음"* 처럼 **사용자의 하루가 아니라 시스템의 기록 상태**를 서술했다. 본문과 아래 목록이 완전히 중복됐고, `여친`을 `여자친구`로 확장했다. **기존 eval을 통과하고도 실데이터에서 터졌다.**

### 실행 방식 (플러그인 없이 수동)
계획 헤더의 "REQUIRED SUB-SKILL"은 무시. **Task 1 → 7 순서, TDD:**
- 태스크마다: ① 실패 테스트 → ② 실패 확인 → ③ 계획의 코드 그대로 → ④ 통과 → ⑤ ruff/lint + build → ⑥ **그 태스크 단위로 1커밋**.

### 환경 (Windows)
- 파이썬은 `worker\.venv\Scripts\python.exe` 직접 호출. 프론트는 Node/npm.
- **로컬 Supabase 필요.** `db reset` 후엔 `npx supabase stop; Start-Sleep -Seconds 3; npx supabase start`.
- **앱 코드 전 Next.js 16 문서**(`node_modules/next/dist/docs/01-app/`) 확인 — `searchParams`도 **Promise**다.
- Vertex/ADC는 **Task 7(eval)에만** 필요하다. Task 1~6은 스텁으로 검증한다.

### 어기면 안 되는 것 (hard rules)
- ⚠️ **detector 변경과 프롬프트 변경을 같은 커밋에 섞지 마라**(git.md — eval 회귀를 이분 탐색해야 한다). Task 1은 반드시 단독 커밋.
- ⚠️ **detector 판정 로직·임계값·confidence를 바꾸지 마라.** Task 1은 `description` **문구만** 바꾼다.
- ⚠️ **URL에 사용자 콘텐츠·엔티티명을 넣지 마라.** 질문 링크는 `?section=<uuid>` — **id만**. 질문 텍스트엔 사람 이름이 들어갈 수 있다(privacy.md).
- ⚠️ **새 `section_type`을 만들지 마라.** recap은 기존 `다른점` 목록을 재사용한다(확정 차이 전부를 쓰도록 바꾼다). 추가되는 건 `'질문'` 하나뿐이다.
- ⚠️ **`supabase.select()` 인자는 리터럴 타입 유지.** 이 오류는 lint·단위로 안 잡히고 **`npm run build`(tsc)에서만** 드러난다 → **프론트 태스크마다 build를 돌려라.**
- ⚠️ **터치 타깃 44px**(`min-h-11`). `min-h-9` 금지.
- **로그에 기록 본문·일기·질문 텍스트를 남기지 마라.** id·카운트만.
- 🚫 **`run-diary`·`run-daily`를 임의로 실행하지 마라(실 LLM 비용).** Task 1~6은 스텁으로 검증한다. Task 7의 eval만 실 호출이며 **1회**다.
- **태스크마다 커밋만. push·merge 금지**(사람이 한다).
- 커밋의 `Co-Authored-By`는 **네 것으로**. 못 고치는 실패·모호한 점은 **멈추고 보고**.
- 완료(DoD) = ruff + pytest + lint + build + vitest(단위·통합) + eval(Task 7).

---

## 상태 (Status) — 멈출 때 여기를 갱신하고 커밋

- **스펙·계획 커밋:** `docs: 일기 정화·recap·꼬리 질문 설계 스펙` / `docs: 일기 정화·recap·꼬리 질문 구현 계획`. 둘 다 **`main`에 있다**.
- **진행:** `feat/diary-recap-followup`에서 **Task 1~6 완료**, Task 7(eval·문서) 시작 전 결정 대기.
- **태스크별 커밋:**
  - Task 1 detector description 정화 — `d7d70f2`
  - Task 2 질문 section_type 마이그레이션(up/down) — `202fcd0`
  - Task 3 본문(freq_shift)·recap(확정 차이 전부) 분리 — `13d6ff8`
  - Task 4 메타 서술·엔티티 표현 가드레일 — `b29ed81`
  - Task 5 꼬리 질문 생성·저장 — `343e3e9`
  - Task 6 recap·질문 카드·기록 화면 맥락 — `e79f952`
- **현재 검증:** 워커 **131 PASS** · ruff clean · 프론트 단위 **59 PASS** · 통합 **49 PASS** · lint clean · build/TypeScript PASS(`/` 동적 렌더 포함).
- **DB:** 승인 후 로컬 Supabase를 초기화해 `20260727070737_diary_question.sql`까지 적용했고, stop/start로 auth를 복구했다. 기존 로컬 사용자·큐·일기 데이터는 초기화됐다.
- **파이프라인은 실데이터로 완주 검증됨:** 메모 4 → entities 7 → differences 7 → narrations 7 → 확정 6 → 일기 1건(다른점 6·근거 4). 서술 품질(엔티티명 정합·조언/인과 0)도 실출력에서 통과. **다만 일기 본문 품질이 무너져 이번 작업으로 고친다.**
- **막힘/결정 필요(Task 7 실행 전):**
  1. `DiaryDifference`가 Task 3에서 `(id, headline, entity_name)` 3필드가 됐지만 `evals/diary/run.py`와 fixture는 여전히 2필드라 현재 계획 코드로는 LLM 호출 전에 TypeError가 난다. fixture 차이를 `[id, headline, entity_name]`으로 확장하고 러너를 맞출지 승인 필요.
  2. 기존 eval 러너가 `one_line`·`body`를 stdout에 출력한다. 이번 작업의 hard rule “로그에 일기 텍스트 금지”와 충돌한다. 케이스명·PASS/FAIL·실패 유형·카운트만 출력하도록 바꿀지 승인 필요.
  - **실 Vertex eval은 아직 실행하지 않았다(0회).** 결정 뒤 코드를 고치고 계획된 1회만 실행한다.
- **다음 시작점:** 위 두 수정 방향을 사람에게 확인받은 뒤 Task 7 fixture·러너·문서를 구현하고 실 eval 1회 → 전체 검사 → Task 7 커밋 → HANDOFF 최종 갱신.
- **알려진 문제(이번 범위 밖):** ① 통합 테스트가 개발 DB의 auth 사용자 전체와 큐를 지운다(`schema.integration.test.ts`·`queue.integration.test.ts`) — 실데이터 검증 재료가 날아간다. ② 워커 CLI가 stdout을 UTF-8로 reconfigure하지 않아 cp949 콘솔에서 한글 출력이 깨진다. ③ 엔티티 추출이 `시간` 같은 일반명사도 잡는다.

> 직전 완료: 일기 날짜 이동(`feat/diary-navigation`) — 병합·push 완료(`d0b5aed`).

> 직전 완료: 일기 보기 화면(`feat/diary-view`) — 병합·push 완료(`e0e701d`). MVP 루프(기록→확인→일기)가 닫혔다.

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
