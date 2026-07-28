# HANDOFF — 활성 작업 인수인계 허브 (모든 AI 공용)

> 여러 AI(Claude · Codex · Gemini · Cursor)가 번갈아 작업하는 저장소의 **단일 인수인계 파일**이다.
> `AGENTS.md`(진입점·규칙)를 먼저 읽고, **"지금 무엇을 어떻게 할지"는 이 파일**을 본다.
> 역할 구분: `AGENTS.md`=변하지 않는 규칙 · `PROJECT_STATE.md`=전체 로드맵 · **`HANDOFF.md`=현재 작업+실행법+상태(매번 갱신)**.
> **작업을 멈추거나 세션 한도(≈80%)에 닿으면 아래 "상태"를 갱신하고 커밋한다** — 추적 안 된 변경은 다음 세션·에이전트에서 보이지 않는다.

---

## 현재 활성 작업 (Active Work Order)

**목표:** 와이어프레임 7화면과 핵심 탐지 루프를
`docs/superpowers/plans/2026-07-28-mvp-full-build.md` 순서로 구현한다.

**성격:** Phase -1은 `ffc8a3c`로 커밋해 `main`의 `d9a18ff`에
`merge --no-ff` 완료. 현재 `feat/mvp-shell`에서 **Phase 0~1 + Daily Wrap
데모 확장 구현·검증 완료, 미커밋** 상태다.

**왜:** 기반 파이프라인과 일기 루프는 완료됐지만 화면 간 이동이 없고, 홈은 발견
중심이 아니며, 현재 detector는 first occurrence·반복만 다룬다. 와이어프레임의
주간 리포트·회고·데이터 제어 화면도 아직 없다.

### 다음 시작점

1. `feat/mvp-shell` 변경 리뷰
2. 사람이 신규 일기 요청 마이그레이션을 staging dry-run 후 적용
3. 사용자 요청 시 Phase 0~1 변경 커밋 → `main`에 `merge --no-ff`
4. 이후 detector → diary opt-out → weekly → recall → data controls를
   **각각 짧은 브랜치**로 진행

### v2 검토에서 바로잡은 결정

- 부재는 생활의 부재가 아니라 **기록 부재**다. 빈 날에는 탐지하지 않는다.
- surprisal의 분모는 달력 경과일이 아니라 **과거 활성 기록일**이다.
- `first_occurrence`는 저장하되 매일 카드 랭킹·서술에서만 제외한다.
- 감정 차이(`entity_id is null`) 멱등성을 위해 부분 유니크 인덱스가 필요하다.
- `weekly_report_highlights`는 `difference_id`를 요구하므로 주간 패턴도
  deterministic difference+evidence로 먼저 저장한다.
- 사진은 Storage 기반만 있고 완성된 업로드 UI가 없어 이번 범위에서 뺀다.
- 담백·따뜻은 기본 프리셋, 짧게·유머는 1회 재생성 주문이다.
- 삭제 요청은 앱 service role이 아니라 security-definer RPC로 만든다.
- 야간 스케줄러·잡 상태·알림·PWA·계정 연결은 화면 구현 뒤의 베타 운영 게이트다.
- 추가 요청으로 수동 일기 생성에 필요한 **durable 잡 상태만** 먼저 구현했다.
  `Daily Wrap`은 새 테이블 산출물이 아니라 완성된 일기의 도착 상태다.
- 시간만으로 “하루가 끝났다”고 단정하지 않고 “오늘을 정리할 시간이에요”라고 한다.
- `/demo`는 프론트 목 데이터만 쓰며 실제 API·사용자 데이터를 건드리지 않는다.

### 실행 방식

- Phase -1→6 의존 순서. 각 브랜치에서 TDD → 검증 → 리뷰 → `merge --no-ff`.
- 통합 테스트를 생략한 Phase는 완료가 아니다. 먼저 테스트 격리를 끝낸다.
- 실제 Vertex eval과 삭제 파괴 테스트는 사람의 명시적 승인을 받아 실행한다.
- 커밋·push·병합은 사람이 요청할 때만 한다.

---

## 상태 (Status) — 멈출 때 여기를 갱신하고 커밋

- **진행:** Phase 0의 `lang=ko`·따뜻한 토큰·하단 3탭, Phase 1의 `/record`
  분리와 발견 우선 홈을 구현했다. 홈은 사용자 타임존 날짜, 3일 학습 게이트,
  차이 확인, 20자 메모 미리보기, 일기 상태, 큰 기록 CTA를 제공한다.
- **추가 완료:** Daily Wrap 도착/차이 발견/정리 시간 문구, 수동 첫 일기 생성
  API, `(user_id,date)` 요청 원장, pgmq 타입 분기 워커, 실제 상태 기반
  queued/processing/done/failed UI를 구현했다. 설정의 **데모 상태 보기**에서
  `/demo` 목 상태 8종을 전환할 수 있다.
- **현재 변경:** 위 Phase 0~1·Daily Wrap 코드/테스트/ADR/마이그레이션이
  `feat/mvp-shell`에 **미커밋** 상태다. `.claude/orchestration/`,
  `.claude/settings.local.json`은 기존 사용자/도구 파일이므로 건드리지 않는다.
- **검증:** frontend lint·typecheck 통과, 단위 **117**, 통합 **53**,
  worker **139**, ruff, production build 통과. 모바일 `/demo?state=arrived`
  DOM·시각 확인 완료. 실 Vertex eval은 프롬프트 변경이 없고 비용이 발생하므로
  명시 승인 없이 재실행하지 않았다.
- **다음:** 코드 리뷰 → 사람의
  `20260728143000_diary_generation_requests.sql` staging dry-run/적용 →
  사용자 요청 시 커밋·병합 → Phase 2.
- **막힘/결정 필요:** 신규 마이그레이션은 AI 적용 금지. 적용 전에는 실제 웹의
  수동 일기 요청은 500이지만 `/demo`는 독립적으로 동작한다.

> 직전 완료: 질문 세션 이어 쓰기(`feat/question-session`) — 병합·push 완료(PR #9, `02e0add`).

> 직전 완료: 일기 루프(`feat/diary-loop`) — 초안 편집·확정·재생성 요청·기본 톤,
> 워커 요청 소비와 톤 사실 불변성 eval까지 완료·`main` 병합(`16a676c`).

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

- **현재 파이프라인:** 메모 insert → pgmq `memory_jobs` → `run-pending` 엔티티 추출
  → `run-daily` 차이 검출·서술 → 사람이 확인·기각 → `run-diary` 일기 생성.
  Phase 3에서 candidate도 일기에 쓰고 dismissed만 제외하는 opt-out으로 바꿀 계획이다.
- **앱과 워커 경계:** 둘은 큐·DB로만 통신한다. 수동 일기는 요청 원장과 기존
  `memory_jobs(job_type='diary')`로 연결됐다. 야간 자동 스케줄러와 주간 잡은
  아직 없다. processing/failed는 원장에 실제 상태가 있을 때만 표시한다.
- **계획 완료와 베타 완료는 다르다:** 7화면 뒤에도 야간 자동 실행·잡 재시도·알림·
  PWA·계정 연결이 베타 운영 게이트로 남는다.
- Claude 세션이 서브에이전트 주도(SDD)로 돌 땐 `.superpowers/sdd/progress.md`에 더 세밀한 태스크 원장을 둔다(선택). **공용 진행 상태의 기준은 이 파일의 "상태" 절**이다.
