# HANDOFF — 활성 작업 인수인계 허브 (모든 AI 공용)

> 여러 AI(Claude · Codex · Gemini · Cursor)가 번갈아 작업하는 저장소의 **단일 인수인계 파일**이다.
> `AGENTS.md`(진입점·규칙)를 먼저 읽고, **"지금 무엇을 어떻게 할지"는 이 파일**을 본다.
> 역할 구분: `AGENTS.md`=변하지 않는 규칙 · `PROJECT_STATE.md`=전체 로드맵 · **`HANDOFF.md`=현재 작업+실행법+상태(매번 갱신)**.
> **작업을 멈추거나 세션 한도(≈80%)에 닿으면 아래 "상태"를 갱신하고 커밋한다** — 추적 안 된 변경은 다음 세션·에이전트에서 보이지 않는다.

---

## 현재 활성 작업 (Active Work Order)

**목표:** `docs/superpowers/plans/2026-07-27-pipeline-trigger.md`(파이프라인 트리거 — 워커 CLI 엔트리포인트) 구현.
**성격:** 계획 확정 완료 — **"코드만 짜면 되는" 상태**. 재설계하지 말고 계획을 그대로 따른다(14개 Locked Decisions로 모호함 제거됨).
**스펙 배경:** `docs/superpowers/specs/2026-07-27-pipeline-trigger-design.md`.
**브랜치:** **`feat/pipeline-trigger`를 `main`에서 새로 만들어** 작업한다(`git checkout -b feat/pipeline-trigger main`). 스펙·계획은 이미 `main`에 있다.
**왜 이게 지금 중요한가:** 워커 진입점 4개(`process_pending`·`detect_day`·`narrate_difference`·`generate_diary`)가 전부 "호출 가능한 함수"일 뿐 **CLI도 엔트리포인트도 없어 아무도 부를 수 없다.** 기록 화면이 생겨 메모가 쌓여도 차이·일기가 만들어지지 않는다. 이걸 붙여야 제품이 실제로 돈다.

### 실행 방식 (플러그인 없이 수동)
Claude는 Superpowers 스킬로 수행하지만, **다른 AI(Codex 등)는 스킬이 없으니 아래를 수동으로** 밟는다. 계획 헤더의 "REQUIRED SUB-SKILL"은 무시. **Task 1 → 6 순서, TDD:**
- 태스크마다: ① 실패 테스트 작성 → ② 실행해 실패 확인 → ③ 계획의 코드 그대로 구현 → ④ 테스트 통과 → ⑤ ruff clean → ⑥ **그 태스크 단위로 1커밋**.
- 계획 안의 명령을 그대로 실행한다. 코드·테스트를 임의로 바꾸지 않는다.

### 환경 (Windows, Python 워커 슬라이스)
- 파이썬은 **`worker\.venv\Scripts\python.exe`를 직접 호출**한다(venv 활성화 대신).
- **로컬 Supabase 스택이 떠 있어야 한다**(통합 테스트). `npx supabase status`로 확인.
  `npx supabase db reset` 후에는 반드시 `npx supabase stop; Start-Sleep -Seconds 3; npx supabase start`로 auth 502를 복구한다.
- **Vertex/ADC 불필요** — 이 기능의 테스트는 LLM을 전부 스텁으로 주입한다. ADC env를 셋업할 필요가 없다.
- 테스트: `worker\.venv\Scripts\python.exe -m pytest worker`(전체) · `-m "not integration"`(단위만, DB 불필요) · `-m integration`(DB 필요) · `-m ruff check worker`(lint).
- 프론트는 이 기능과 무관하지만 Task 6에서 회귀만 확인한다(`npx vitest run`).

### 어기면 안 되는 것 (hard rules)
- **스키마 변경·마이그레이션 없음.** 새 도메인 로직도 없다 — 이건 기존 함수를 부르는 **배선 계층**이다.
- ⚠️ **`process_pending`만 `conn`을 받지 않는다**(자체 `connect()`). 나머지 셋은 `conn`을 받는다. **이 불일치를 통일하지 마라** — 병합된 코드 회귀 위험이고 이 기능의 목적과 무관하다(Locked Decision 1).
- ⚠️ **Task 2가 이 기능의 핵심이다.** `narrate_difference`는 지금 기존 서술이 있어도 **매번 LLM을 부른다** — 스케줄러가 반복 호출하면 전체 재서술로 **반복 과금**이 된다. `skip_if_exists=True` 기본값으로 막는다.
- ⚠️ **Task 2가 기존 `test_narration_integration.py`의 재서술 테스트를 깨뜨릴 수 있다.** 그 테스트는 같은 차이를 두 번 서술해 내용이 덮어써지는지 본다. 깨지면 **테스트를 약화시키지 말고** 그 호출에 `skip_if_exists=False`를 넘겨라(그 테스트의 의도가 "명시적 재서술"이므로 의도를 명확히 하는 수정이다). 판단이 안 서면 멈추고 보고하라.
- 🚫 **실 LLM을 부르는 실행을 하지 마라(비용).** 스모크는 `python -m silen_worker --help`까지만. `run-daily`/`run-pending`을 인자 없이 실행하면 실제 Vertex 호출이 발생한다.
- 🚫 **스케줄러에 실제로 등록하지 마라.** `schtasks`·`crontab`을 실행하지 마라 — 계획 Task 6은 **문서만** 쓴다. 등록은 사람이 한다(안전 가드).
- **로그에 사용자 기록 본문·일기 텍스트를 넣지 마라.** `user_id`·카운트·id·**예외 타입명**만. 예외 메시지에 프롬프트/본문이 섞여 나올 수 있어 `str(exc)`를 로그에 넣지 않는다.
- **태스크마다 커밋만. push·merge 금지**(사람이 한다).
- 이미 병합된 기능(**extraction·detector·narration·diary·confirm-ui·record-screen**)을 수정하지 마라 — 계획이 지정한 파일만 추가/교체한다(`db.py`·`tasks/narrate.py`는 계획이 지정한 범위에서만).
- 커밋 메시지의 `Co-Authored-By` 트레일러는 **네 것으로** 바꿔라(네가 저자다). git.md 규약.
- 못 고치는 테스트 실패나 모호한 점이 있으면 **멈추고 보고**하라. 추측하거나 테스트를 약화시키지 마라.
- 완료(DoD) = ruff + pytest(단위+통합). **eval은 이 기능 대상 아님**(프롬프트·모델 미변경).

---

## 상태 (Status) — 멈출 때 여기를 갱신하고 커밋

- **스펙 커밋:** `e0a6b30` · **계획 확정 커밋:** `f032570`. 둘 다 **`main`에 있다**(문서는 main 직접 커밋 허용, git.md).
- **구현 진행:** **Task 1~6 완료 (6 / 6).** 브랜치 `feat/pipeline-trigger`; push·merge 안 함.
- **태스크별 커밋:** Task 1 DB 함수 `d182292` · Task 2 서술 재실행 안전 `53cbc02` · Task 3 대상 계산·파서 `f9b7a64` · Task 4 세 CLI 명령 `1e756ae` · Task 5 module 엔트리포인트 `2e903ba` · Task 6 실행 문서 `39c7cb7`.
- **검증:** 로컬 Supabase 상태 확인. `python -m silen_worker --help`와 `run-daily --help` 성공(실 명령·실 LLM 미호출). 워커 전체 **113 PASS**(기준선 94 + 새 테스트 19), ruff clean, 프론트 단위 **40 PASS**.
- **안전 확인:** 스키마·마이그레이션 변경 없음. `schtasks`·`crontab` 미실행. CLI 로그는 user_id·날짜·카운트·id·예외 타입명만 포함하고 본문·일기 텍스트·예외 메시지를 싣지 않는다.
- **다음 시작점:** 사람이 변경을 리뷰한 뒤 `main` 기준 rebase와 `merge --no-ff` 또는 PR을 진행한다(squash·push 자동 실행 금지).
- **막힘/결정 필요:** 없음. pytest가 `.pytest_cache` 쓰기 권한 경고 1건을 내지만 테스트 결과에는 영향 없음.
- **참고:** 로컬 개발 DB에 합성 기록 1건(`브라우저 확인용 기록`)이 남아 있다(로컬 dev DB라 무해). 사용자 소유 미추적 `.claude/orchestration/`·`.claude/settings.local.json`은 건드리지 않았다.

> 직전 완료: 기록 화면(`feat/record-screen`) — 병합·push 완료(`d42906b`). 44px 규칙 준수로 확정.

> 직전 완료: 확인 UI(`feat/confirm-ui`) — 병합됨. TOCTOU 보안 수정 포함. 상세는 git 히스토리.

> 직전 완료: 일기 생성(diary) 기능 — 병합됨(`main`). 상세는 git 히스토리.

> 갱신 예: `Task 1 완료 (커밋 abc1234). 다음: Task 2 저장소.`

---

## 참고 (context)

- **파이프라인 순서(이 기능이 여는 것):** 메모 insert → DB 트리거가 pgmq `memory_jobs`에 적재 → `run-pending`이 소비해 엔티티 추출 → `run-daily`가 차이 검출·서술 → **사람이 확인 UI에서 확정** → `run-diary`가 확정 차이를 녹인 일기 생성.
  일기는 `status='confirmed'` 차이만 쓰므로 `run-daily`와 `run-diary` 사이에 **사람의 확정**이 들어가야 한다. 그래서 명령이 둘로 나뉜다.
- **이 기능 병합 후 후보:** 일기 보기 화면 · 기록 열람/목록 · 사진 첨부. 전체 로드맵은 `PROJECT_STATE.md`.
- Claude 세션이 서브에이전트 주도(SDD)로 돌 땐 `.superpowers/sdd/progress.md`에 더 세밀한 태스크 원장을 둔다(선택). **공용 진행 상태의 기준은 이 파일의 "상태" 절**이다.
