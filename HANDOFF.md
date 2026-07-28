# HANDOFF — 활성 작업 인수인계 허브 (모든 AI 공용)

> 여러 AI(Claude · Codex · Gemini · Cursor)가 번갈아 작업하는 저장소의 **단일 인수인계 파일**이다.
> `AGENTS.md`(진입점·규칙)를 먼저 읽고, **"지금 무엇을 어떻게 할지"는 이 파일**을 본다.
> 역할 구분: `AGENTS.md`=변하지 않는 규칙 · `PROJECT_STATE.md`=전체 로드맵 · **`HANDOFF.md`=현재 작업+실행법+상태(매번 갱신)**.
> **작업을 멈추거나 세션 한도(≈80%)에 닿으면 아래 "상태"를 갱신하고 커밋한다** — 추적 안 된 변경은 다음 세션·에이전트에서 보이지 않는다.

---

## 현재 활성 작업 (Active Work Order)

**목표:** `docs/superpowers/plans/2026-07-28-test-isolation.md`(통합 테스트 격리) 구현.
**성격:** 계획 확정 — **"코드만 짜면 되는" 상태**. 재설계하지 말고 계획을 그대로 따른다(결정 고정 9항).
**스펙:** `docs/superpowers/specs/2026-07-28-test-isolation-design.md`.
**브랜치:** **`fix/test-isolation`을 `main`에서 새로 만들어** 작업한다. 스펙·계획은 이미 `main`에 있다.
**왜:** 통합 테스트가 개발 DB의 **다른 데이터를 파괴한다.** 실데이터로 파이프라인을 검증하려면 테스트를 못 돌리고, 테스트를 돌리면 검증 재료가 사라진다 — 이 세션에서 **두 번** 잃었다. 파괴자는 둘뿐이다: `schema.integration.test.ts`의 전역 사용자 삭제, 그리고 `purge_queue` 8곳.

### 실행 방식
**Task 1 → 5 순서, TDD.** 태스크마다 ① 실패 테스트 → ② 실패 확인 → ③ 계획의 코드 그대로 → ④ 통과 → ⑤ ruff/lint → ⑥ 1커밋.

### 환경 (Windows)
- 파이썬은 `worker\.venv\Scripts\python.exe` 직접 호출. 프론트는 Node/npm.
- **로컬 Supabase 필요.** `db reset` 후엔 `npx supabase stop; Start-Sleep -Seconds 3; npx supabase start`.
- Vertex/ADC 불필요 — 모든 테스트가 스텁 추출기를 쓴다.

### 어기면 안 되는 것 (hard rules)
- ⚠️ **`process_pending`의 기본 동작을 바꾸지 마라.** `only_user_id=None`이면 지금과 **완전히 동일**해야 한다(프로덕션 CLI가 그대로 쓴다). 이걸 증명하는 테스트가 계획에 있다.
- ⚠️ **`only_user_id` 검사는 `try` 블록 앞에** 둔다. 그래야 예외 경로의 아카이브(데드레터)가 남의 메시지에 절대 닿지 않는다.
- ⚠️ **건너뛴 메시지는 삭제도 아카이브도 하지 마라.** `continue`만. 읽기로 vt(60초) 동안 안 보이지만 되돌아온다 — 의도된 동작이다.
- ⚠️ **큐 상태 단언에 `pgmq.read`를 쓰지 마라.** `read`는 vt를 세팅하는 **부작용**이 있어 남의 메시지를 60초 숨긴다. 큐 테이블을 직접 조회한다.
- ⚠️ **테스트를 약화하지 마라.** 전역 단언을 자기 것 단언으로 바꾸는 건 **정확화**지 완화가 아니다. 단언을 지우거나 무의미하게 만들지 마라. `schema` 테스트가 전역 비움 없이 실패하면 **어떤 단언이 왜 전역 상태에 기대는지 보고**하라.
- **스키마·마이그레이션·API·프론트 화면 코드 변경 없음.** 손대는 건 테스트와 `process_pending` 한 함수뿐이다.
- 🚫 **실 LLM 호출 금지.** 스텁만 쓴다.
- **태스크마다 커밋만. push·merge 금지.** `Co-Authored-By`는 네 것으로.
- 못 고치는 실패·모호한 점은 **멈추고 보고**하라.

---

## 상태 (Status) — 멈출 때 여기를 갱신하고 커밋

- **진행:** 미착수. Task 1부터.
- **기준선(main):** 프론트 단위 **63** · 통합 **49** · 워커 **131** · lint·build·ruff clean.
- **완료의 증거:** ① `purge_queue` 호출 0건 ② `listUsers` 전역 삭제 없음 ③ **"남의 메시지가 살아남는다" 회귀 테스트 통과** ④ 통합 테스트를 돌린 **뒤에도** 기존 사용자·메모·일기가 남아 있음(건수 보고).
- **막힘/결정 필요:** (없음)
- **알려진 문제(범위 밖):** ① 워커 CLI가 stdout을 UTF-8로 reconfigure하지 않아 cp949 콘솔에서 한글이 깨진다. ② 엔티티 추출이 `시간` 같은 일반명사도 잡는다. ③ `worker/.pytest_cache` 디렉터리 권한이 깨져 있다(잠겨서 삭제 불가 — 사람이 프로세스를 닫고 처리). ④ 검증 데이터 seed 스크립트가 없다(`supabase/seed.sql` 훅은 설정돼 있으나 파일 없음).

> 직전 완료: 질문 세션 이어 쓰기(`feat/question-session`) — 병합·push 완료(PR #9, `02e0add`).

> 직전 완료: 일기 품질 실데이터 재검증 — entities 6 → differences 6 →
> narrations 6 → 확정 6 → 일기 생성. 본문 `"처음"` 0회·메타 표현 0건,
> recap 6·질문 1·근거 3으로 개선 효과 확인.

> 직전 완료: 일기 품질 개선(`feat/diary-recap-followup`) — 병합·push 완료(`599be4b`). 본문/recap 분리·메타 서술 차단·꼬리 질문.

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
