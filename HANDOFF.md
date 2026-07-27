# HANDOFF — 활성 작업 인수인계 허브 (모든 AI 공용)

> 여러 AI(Claude · Codex · Gemini · Cursor)가 번갈아 작업하는 저장소의 **단일 인수인계 파일**이다.
> `AGENTS.md`(진입점·규칙)를 먼저 읽고, **"지금 무엇을 어떻게 할지"는 이 파일**을 본다.
> 역할 구분: `AGENTS.md`=변하지 않는 규칙 · `PROJECT_STATE.md`=전체 로드맵 · **`HANDOFF.md`=현재 작업+실행법+상태(매번 갱신)**.
> **작업을 멈추거나 세션 한도(≈80%)에 닿으면 아래 "상태"를 갱신하고 커밋한다** — 추적 안 된 변경은 다음 세션·에이전트에서 보이지 않는다.

---

## 현재 활성 작업 (Active Work Order)

**두 가지다. 순서대로 한다: ⓪ 파이프라인 1회 실전 실행 → ① 일기 날짜 이동 구현.**

---

### ⓪ 선행 — 파이프라인 1회 실전 실행 (사람이 지시함)

**목적:** 지금까지 만든 파이프라인을 **실데이터로 한 번 끝까지 돌려** 실제로 도는지 확인한다. 코드 변경 없음, 검증만.

**⚠️ 실 Vertex LLM 호출이라 비용이 발생한다.** 사람이 이번 1회를 명시적으로 지시했다. **딱 한 번만** 돌리고, 실패해도 반복 실행하지 마라 — 원인을 보고하라.

**env(ADC):**
```powershell
$env:GOOGLE_GENAI_USE_VERTEXAI = "true"
$env:GOOGLE_CLOUD_PROJECT = "project-58561b19-fb35-4c01-bb2"
$env:GOOGLE_CLOUD_LOCATION = "global"
```

**순서:**
1. **대상 날짜부터 확인한다.** `run-daily`·`run-diary`의 기본 대상은 **사용자 로컬 "어제"** 다. 로컬 DB의 메모가 오늘 것이면 기본값으로는 아무것도 안 잡힌다. 먼저 메모가 어느 날짜에 있는지 확인하고, 그 날짜를 `--date`로 명시해라.
   ```powershell
   worker\.venv\Scripts\python.exe -c "import psycopg; c=psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres'); print(c.execute('select user_id::text, date(captured_at at time zone (select timezone from public.users u where u.id=m.user_id))::text, count(*) from public.memories m where deleted_at is null and is_locked=false group by 1,2 order by 2').fetchall())"
   ```
2. `run-pending` — 큐를 소비해 엔티티를 추출한다(인자 없음).
3. `run-daily --date <위에서 확인한 날짜>` — 차이 검출 + 서술.
4. **여기서 멈추고 보고한다.** 일기는 사용자가 확인 UI(`/review`)에서 차이를 확정한 뒤에 만들어야 의미가 있다(확정 차이만 일기에 녹는다). `run-diary`는 사람이 확정한 뒤 지시할 때 돌린다.

**확인·보고할 것(본문은 싣지 말 것 — 카운트·id만):**
- 각 명령의 종료 코드와 JSON 로그 요약
- `entities`·`memory_entities`·`differences`·`difference_narrations` 각 건수 변화
- `/review`에 확인할 차이 카드가 보이는지(dev 서버로 육안, 선택)
- 실패했다면 어느 단계에서 어떤 에러인지(스택 전체 말고 요약)

---

### ① 본 작업 — 일기 날짜 이동

**목표:** `docs/superpowers/plans/2026-07-27-diary-navigation.md`(일기 날짜 이동 `/diary/[date]`) 구현.
**성격:** 계획 확정 완료 — **"코드만 짜면 되는" 상태**. 재설계하지 말고 계획을 그대로 따른다(10개 Locked Decisions로 모호함 제거됨).
**스펙 배경:** `docs/superpowers/specs/2026-07-27-diary-navigation-design.md`.
**브랜치:** **`feat/diary-navigation`을 `main`에서 새로 만들어** 작업한다(`git checkout -b feat/diary-navigation main`). 스펙·계획은 이미 `main`에 있다.
**왜 이게 지금 중요한가:** `/diary`는 `findLatest()` — 최신 일기 **하나만** 보여준다. 새 일기가 만들어지면 **어제 일기는 도달할 수 없게 된다.** 파이프라인은 계속 쌓는데 사용자는 마지막 하나만 본다. "돌아본다"는 제품 컨셉의 핵심이 빠져 있다.

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
- **스키마 변경·마이그레이션·API 라우트·워커 변경 없음.** 읽기 전용 프론트 슬라이스다. `eslint.config.mjs`도 `diaryRepository.ts`가 이미 예외에 있어 **수정 불필요**.
- ⚠️ **`DiaryArticle`·`EvidenceDisclosure`·`StateView`를 수정하지 마라.** 그대로 재사용한다.
- ⚠️ **`/diary`를 목록으로 바꾸지 마라.** 최신 일기를 바로 보여주는 주 흐름을 유지하고, 과거 접근은 `/diary/[date]`로만 붙인다(Locked Decision 1).
- ⚠️ **리다이렉트를 쓰지 마라.** `/diary` → 최신 날짜로 `redirect()`하면 뒤로가기가 꼬인다. 두 라우트가 `DiaryScreen`을 공유한다(Locked Decision 2).
- ⚠️ **이전/다음은 "존재하는 일기로 점프"** 다. 날짜−1이 아니다 — 빈 날엔 일기가 없어 날짜 단위로 넘기면 계속 지나가야 한다(Locked Decision 3).
- ⚠️ **`supabase.select()` 인자는 리터럴 타입이어야 한다.** 상수로 뽑을 땐 `as const`. `+`로 이어붙이면 타입 추론이 깨지고 **이 오류는 lint·단위로 안 잡히고 `npm run build`(tsc)에서만** 드러난다 → **태스크마다 build를 돌려라**(지난 기능에서 실제로 겪은 함정).
- ⚠️ **터치 타깃 44px** — `min-h-11`. `min-h-9`(36px)는 `frontend.md` 위반이다(record-screen에서 같은 실수가 한 번 났다).
- **색만으로 의미를 전달하지 마라** — 이전/다음에 텍스트 라벨을 병행하고 비활성은 `aria-disabled`로 알린다.
- **잠긴·삭제된 메모를 근거에 노출하지 마라**(privacy.md). 기존 필터를 그대로 유지한다.
- **저장소는 세션 클라이언트 + RLS.** `service_role`을 쓰지 마라.
- 🚫 **`run-diary`를 임의로 실행하지 마라(실 LLM 비용).** ⓪에서도 `run-diary`는 사람이 확정한 뒤 지시할 때만 돌린다.
- **태스크마다 커밋만. push·merge 금지**(사람이 한다).
- 이미 병합된 기능(**extraction·detector·narration·diary·confirm-ui·record-screen·pipeline-trigger·diary-view**)을 수정하지 마라 — 계획이 지정한 파일만 손댄다.
- 커밋 메시지의 `Co-Authored-By` 트레일러는 **네 것으로** 바꿔라(네가 저자다). git.md 규약.
- 못 고치는 테스트 실패나 모호한 점이 있으면 **멈추고 보고**하라. 추측하거나 테스트를 약화시키지 마라.
- 완료(DoD) = lint + typecheck(build) + unit + integration. **eval은 이 기능 대상 아님**(프롬프트·모델 미변경).

---

## 상태 (Status) — 멈출 때 여기를 갱신하고 커밋

- **스펙 커밋:** `docs: 일기 날짜 이동 설계 스펙` · **계획 확정 커밋:** `docs: 일기 날짜 이동 구현 계획`. 둘 다 **`main`에 있다**(문서는 main 직접 커밋 허용, git.md).
- **진행:** ⓪ 파이프라인 1회 실행 완료 · ① 일기 날짜 이동 **Task 1~4 전체 완료**(`feat/diary-navigation`).
- **⓪ 실행 결과(각 명령 정확히 1회):**
  - 대상 날짜 `2026-07-27` — 활성 메모가 사용자 `4a83fd9b-28c2-41ff-aade-8d7a02d45104`, `dd3f3f24-ae7c-43c4-a3c4-86c7096cda52`에 각 1건.
  - `run-pending` 종료 코드 0, `{"event":"run_pending.done","processed":0}`. 큐가 비어 있어 엔티티 추출·Vertex 요청은 발생하지 않았다.
  - `run-daily --date 2026-07-27` 종료 코드 0, 사용자 5명 모두 `differences=0`, `narrated=0`, 최종 `ok=5`, `failed=0`. 새 차이가 없어 Vertex 서술 요청은 발생하지 않았다.
  - 전후 건수: `entities` 0→0 · `memory_entities` 0→0 · `differences` 0→0 · `difference_narrations` 0→0. 새 ID 없음. `/review` 육안 확인은 생략(차이 0건). **재실행·`run-diary` 실행 없음.**
- **① 태스크별 커밋:**
  - Task 1 날짜 조회·실재 이웃 조회 — `94ced2e`
  - Task 2 이전/다음 네비게이션 — `94a5296`
  - Task 3 공통 화면·`/diary/[date]` 라우트 — `cc7a222`
  - Task 4 README 안내 — `2908cc7`
- **최종 검증:** `npm run lint` PASS · `npm run build` PASS(`/diary`, `/diary/[date]`) · 단위 **53 PASS** · 통합 **49 PASS**.
- **막힘/결정 필요:** 없음. 스키마·마이그레이션·API 라우트·워커·`eslint.config.mjs`·기존 `DiaryArticle`/`EvidenceDisclosure`/`StateView` 변경 없음. push·merge도 하지 않았다.
- **다음 시작점:** 사람이 `feat/diary-navigation`을 검토한 뒤 push·merge한다.
- **참고:** 사용자 소유 미추적 `.claude/orchestration/`·`.claude/settings.local.json`은 건드리지 않았다.

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
