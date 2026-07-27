# HANDOFF — 활성 작업 인수인계 허브 (모든 AI 공용)

> 여러 AI(Claude · Codex · Gemini · Cursor)가 번갈아 작업하는 저장소의 **단일 인수인계 파일**이다.
> `AGENTS.md`(진입점·규칙)를 먼저 읽고, **"지금 무엇을 어떻게 할지"는 이 파일**을 본다.
> 역할 구분: `AGENTS.md`=변하지 않는 규칙 · `PROJECT_STATE.md`=전체 로드맵 · **`HANDOFF.md`=현재 작업+실행법+상태(매번 갱신)**.
> **작업을 멈추거나 세션 한도(≈80%)에 닿으면 아래 "상태"를 갱신하고 커밋한다** — 추적 안 된 변경은 다음 세션·에이전트에서 보이지 않는다.

---

## 현재 활성 작업 (Active Work Order)

**목표:** ESLint가 파이썬 디렉터리(`worker/`·`evals/`)를 훑지 않게 한다. **`eslint.config.mjs` 2줄.**
**브랜치:** **`fix/eslint-ignore-python`을 `main`에서 새로 만들어** 작업한다.
**왜:** `npm run lint`가 `EPERM: scandir 'worker/.pytest_cache'`로 **크래시한다.** ESLint 9 flat config는 `.gitignore`를 자동으로 따르지 않아 파이썬 트리까지 걸어 들어간다. 캐시 디렉터리 권한이 한 번 깨지면 lint 전체가 죽는다 — DoD(`lint + build + test`)를 검증할 수 없게 된다.

### 무엇을 (전부다)

`eslint.config.mjs`의 `globalIgnores([...])`에 두 줄을 추가한다:

```js
    // worker·evals는 파이썬이다. 1차 JS/TS가 없고, .venv·캐시까지 훑다가
    // 권한이 깨진 디렉터리를 만나면 lint 전체가 EPERM으로 죽는다.
    // (.gitignore를 따르게 하는 방식은 worker/src·tests가 추적 파일이라 안 통한다.)
    "worker/**",
    "evals/**",
```

### 검증
- `npm run lint` — **크래시 없이 통과**해야 한다(지금은 EPERM으로 죽는다).
- `npx eslint app lib components` — 여전히 exit 0.
- `npm run build`·`npx vitest run` 회귀 확인.

### 어기면 안 되는 것
- **다른 ignore 패턴을 추가하지 마라.** `worker/**`·`evals/**` 둘뿐이다.
- **`@eslint/compat`·`includeIgnoreFile` 같은 의존성을 추가하지 마라.** `worker/src`·`worker/tests`는 git 추적 파일이라 `.gitignore` 연동으로는 문제가 안 풀린다.
- **기존 규칙(`import/no-restricted-paths`·`no-restricted-imports`)을 건드리지 마라.**
- `worker/.pytest_cache` 디렉터리 자체는 **잠겨 있어 삭제되지 않는다.** 지우려 하지 마라 — 사람이 프로세스를 닫고 처리한다.
- **커밋만. push·merge 금지.** `Co-Authored-By`는 네 것으로.

---

## 상태 (Status) — 멈출 때 여기를 갱신하고 커밋

- **진행:** `fix/eslint-ignore-python`에서 구현·검증 완료 — `5f1db3c`.
- **검증:** `npm run lint` PASS · `npx eslint app lib components` PASS · build/TypeScript PASS · 프론트 단위 **59 PASS**.
- **참고:** 이번 세션에서는 변경 전 lint도 통과해 EPERM을 재현하지 못했다. 캐시 잠금 상태에 따라 간헐적인 문제이며, `worker/**`·`evals/**`만 전역 제외해 해당 경로 순회를 차단했다.
- **막힘/결정 필요:** (없음)
- **다음 시작점:** 사람이 `5f1db3c`를 리뷰한 뒤 push·merge한다. AI는 push·merge하지 않았다.
- **알려진 문제(범위 밖):** ① 통합 테스트가 개발 DB의 auth 사용자 전체와 큐를 지운다(`schema.integration.test.ts`·`queue.integration.test.ts`). ② 워커 CLI가 stdout을 UTF-8로 reconfigure하지 않아 cp949 콘솔에서 한글이 깨진다. ③ 엔티티 추출이 `시간` 같은 일반명사도 잡는다. ④ **일기 품질 개선(`599be4b`)이 실데이터로는 아직 재검증되지 않았다** — eval 5/5는 합성 기준이고, Task 2의 db reset으로 로컬 데이터가 초기화됐다.

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
