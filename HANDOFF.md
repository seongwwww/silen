# HANDOFF — 활성 작업 인수인계 허브 (모든 AI 공용)

> 여러 AI(Claude · Codex · Gemini · Cursor)가 번갈아 작업하는 저장소의 **단일 인수인계 파일**이다.
> `AGENTS.md`(진입점·규칙)를 먼저 읽고, **"지금 무엇을 어떻게 할지"는 이 파일**을 본다.
> 역할 구분: `AGENTS.md`=변하지 않는 규칙 · `PROJECT_STATE.md`=전체 로드맵 · **`HANDOFF.md`=현재 작업+실행법+상태(매번 갱신)**.
> **작업을 멈추거나 세션 한도(≈80%)에 닿으면 아래 "상태"를 갱신하고 커밋한다** — 추적 안 된 변경은 다음 세션·에이전트에서 보이지 않는다.

---

## 현재 활성 작업 (Active Work Order)

**목표:** `docs/superpowers/plans/2026-07-28-diary-loop.md`(일기 루프 완성 — 기획서 §6) 구현.
**성격:** 계획 확정 — **"코드만 짜면 되는" 상태**. 재설계하지 말고 계획을 그대로 따른다(결정 고정 12항).
**스펙:** `docs/superpowers/specs/2026-07-28-diary-loop-design.md`.
**브랜치:** **`feat/diary-loop`을 `main`에서 새로 만들어** 작업한다.
**왜:** 일기가 **생성만** 된다. 고칠 수도, 톤을 정할 수도, 다시 만들 수도 없다. `diaries.edited_text`·`status`·`style_profile` 컬럼은 **이미 있는데 아무도 쓰지 않고**, 워커는 톤을 `담백`으로 하드코딩한다. 기획서 §6 루프가 반쪽이다.

**F1~F3을 하나로 묶었다:** 초안 수정·확정 + 다시 만들기 + 톤. 기획서 §6이 원래 한 덩어리다.

### 실행 방식
**Task 1 → 8 순서, TDD.** 태스크마다 ① 실패 테스트 → ② 실패 확인 → ③ 계획 코드 그대로 → ④ 통과 → ⑤ lint/ruff + build → ⑥ 1커밋.

### 환경 (Windows)
- 파이썬 `worker\.venv\Scripts\python.exe` 직접 호출. 프론트는 Node/npm.
- **로컬 Supabase 필요.** `db reset` 후엔 `npx supabase stop; Start-Sleep -Seconds 3; npx supabase start`.
- **앱 코드 전 Next.js 16 문서** 확인 — `params`·`searchParams`는 **Promise**.
- Vertex/ADC는 **Task 8(eval)에만**. Task 1~7은 스텁으로 검증한다.

### 어기면 안 되는 것 (hard rules)
- ⚠️ **편집은 `edited_text`에만.** `generated_text`(AI 초안)를 **절대 덮어쓰지 마라** — 원본↔생성물 분리 원칙이다.
- ⚠️ **TOCTOU 방어**: 읽은 status를 기대값으로 넘겨 원자적 업데이트, 0행이면 **409**(`differences` 선례).
- ⚠️ **재생성은 요청만 남긴다.** 즉시 재생성·큐·폴링·처리중 UI를 만들지 마라. 다음 `run-diary`가 1회 반영하고 **요청을 비운다**.
- ⚠️ **편집본에 다시 만들기를 누르면** "고친 내용이 사라져요"를 알리고 **한 번 더 확인**받는다.
- ⚠️ **톤은 문체만 바꾼다. 사실은 그대로다**(기획서 §4-9). 기존 가드레일(근거 정합·메타 표현·엔티티 표현)을 **약화하지 마라**.
- ⚠️ **프리셋은 `담백`·`따뜻` 둘뿐.** 늘리지 마라.
- ⚠️ **`supabase.select()` 인자는 리터럴 타입 유지**(상수면 `as const`). lint·단위로 안 잡히고 **`build`(tsc)에서만** 드러난다 → 프론트 태스크마다 build.
- ⚠️ **터치 타깃 44px**(`min-h-11`). 색만으로 의미 전달 금지. 죄책감·독려 문구 금지.
- **저장소는 세션 클라이언트 + RLS.** `service_role` 금지.
- 🚫 **실 LLM 호출 금지**(스텁). eval만 Task 8에서 1회.
- **태스크마다 커밋만. push·merge 금지.** `Co-Authored-By`는 네 것으로.
- 못 고치는 실패·모호한 점은 **멈추고 보고**하라.

---

## 상태 (Status) — 멈출 때 여기를 갱신하고 커밋

- **진행:** **Task 1~8 완료. DoD 전 항목 통과.** 병합 준비 완료.
- **최종 검증:** 프론트 단위 **84** · 통합 **53** · 워커 **135** · lint · **typecheck** · build · **eval 6/6**(실 Vertex 1회).
- **톤 불변성 확인:** 담백/따뜻이 문체만 다르고 **사실 집합은 동일**했다(같은 메모·같은 근거).
- **고친 것:** `tsc --noEmit`이 통합 테스트 3곳의 `data.properties` nullable에서 실패했다. `next build`는 테스트 파일을 타입체크하지 않아 그동안 안 잡혔고 `main`에도 같은 패턴이 있었다 — 링크 발급 실패 시 던지도록 고쳤다(`d0fc5cf`).
- **막힘/결정 필요:** (없음)

> 직전 완료: 질문 세션 이어 쓰기(`feat/question-session`) — 병합·push 완료(PR #9, `02e0add`).

> 직전 완료: 일기 루프(`feat/diary-loop`) — 초안 편집·확정·재생성 요청·기본 톤, 워커 요청 소비와 톤 사실 불변성 eval까지 완료. 리뷰·병합 대기.

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
