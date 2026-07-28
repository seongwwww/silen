# HANDOFF — 활성 작업 인수인계 허브 (모든 AI 공용)

> 여러 AI(Claude · Codex · Gemini · Cursor)가 번갈아 작업하는 저장소의 **단일 인수인계 파일**이다.
> `AGENTS.md`(진입점·규칙)를 먼저 읽고, **"지금 무엇을 어떻게 할지"는 이 파일**을 본다.
> 역할 구분: `AGENTS.md`=변하지 않는 규칙 · `PROJECT_STATE.md`=전체 로드맵 · **`HANDOFF.md`=현재 작업+실행법+상태(매번 갱신)**.
> **작업을 멈추거나 세션 한도(≈80%)에 닿으면 아래 "상태"를 갱신하고 커밋한다** — 추적 안 된 변경은 다음 세션·에이전트에서 보이지 않는다.

---

## 현재 활성 작업 (Active Work Order)

**목표:** `docs/superpowers/plans/2026-07-28-mvp-full-build.md`의 Phase 0~6을
검증 게이트까지 닫고 `feat/mvp-shell`을 main 병합 가능한 상태로 만든다.

**성격:** Phase -1은 `main`의 `d9a18ff`에 병합됐다. 현재
`feat/mvp-shell`에는 **Phase 0~6 제품 코드와 프런트 목데이터까지 전부
커밋**돼 있다. 남은 것은 사람 승인이 필요한 스키마·파괴 테스트·실 LLM eval이다.

**왜:** 화면과 기능이 존재하는 것만으로 삭제 완전성·감정축 멱등성과 모델 품질이
검증되지는 않는다. 코드 완료를 MVP 완료로 과장하지 않고 남은 게이트를 명시한다.

### 다음 시작점

1. 명시 승인 후 격리된 `destructive` 삭제 통합 테스트·잔존 검증
2. 비용 승인 후 실제 Vertex diary eval 실행
3. production 전에는 두 신규 마이그레이션을 staging dry-run
4. 최종 리뷰 후 사용자 요청 시 main 위 rebase → `merge --no-ff` → push

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

- **코드 완료:** Phase 0~6. 놀라움(bits)·기록 부재·감정축·top 3·기각학습,
  일기 opt-out·톤 주문, 7일 리포트, 키워드 회고, JSON 내보내기, 재개 가능한
  전체 삭제, 읽기 전용 `stats`까지 구현·커밋했다.
- **웹 확인:** `/demo` Daily Wrap 8상태와 `/report?demo=1` 완성 리포트는
  실제 API 없이 볼 수 있다. `/settings` 내보내기·2단계 삭제 확인,
  `/report` 빈 상태와 목데이터 상태를 375px 모바일에서 확인했다.
- **현재 작업트리:** 제품 변경은 모두 커밋됐다. `.claude/orchestration/`,
  `.claude/settings.local.json`만 기존 사용자/도구의 untracked 파일이라
  건드리지 않는다.
- **검증:** `npm run check` 37 files/**167 tests**, production build 17 pages,
  worker ruff·단위 **139**, 프런트 통합 **62/62**, worker 비파괴 통합
  **92/92** 통과.
- **로컬 스키마:** 승인 후 `20260728170000`, `20260728230000`을 적용했고
  local migration list가 19/19 일치한다.
- **대기:** 실제 Vertex eval은 비용, `destructive` 삭제 통합은 격리 fixture라도
  실제 DB·Storage 삭제를 수반하므로 실행하지 않았다.
- **막힘/결정 필요:** AGENTS 규칙상 파괴 테스트와 유료 eval은 각각 명시
  승인이 필요하다. 두 게이트 전에는 Phase 6/MVP 완료로 표시하지 않는다.

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
  → `run-daily` 통계 차이 검출·서술 → candidate·confirmed를 바로
  `run-diary`에 반영하고 dismissed·stale만 제외 → `run-weekly` 7일 집계.
- **앱과 워커 경계:** 둘은 큐·DB로만 통신한다. 수동 일기는 요청 원장과 기존
  `memory_jobs(job_type='diary')`로 연결됐다. `run-weekly` 명령은 있지만
  야간 자동 스케줄러는 아직 없다. processing/failed는 원장에 실제 상태가
  있을 때만 표시한다.
- **계획 완료와 베타 완료는 다르다:** 야간 자동 실행·알림·PWA·계정 연결은
  여전히 베타 운영 게이트다. 지금은 웹 버튼과 CLI로 수동 실행한다.
- Claude 세션이 서브에이전트 주도(SDD)로 돌 땐 `.superpowers/sdd/progress.md`에 더 세밀한 태스크 원장을 둔다(선택). **공용 진행 상태의 기준은 이 파일의 "상태" 절**이다.
