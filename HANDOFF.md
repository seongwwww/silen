# HANDOFF — 활성 작업 인수인계 허브 (모든 AI 공용)

> 여러 AI(Claude · Codex · Gemini · Cursor)가 번갈아 작업하는 저장소의 **단일 인수인계 파일**이다.
> `AGENTS.md`(진입점·규칙)를 먼저 읽고, **"지금 무엇을 어떻게 할지"는 이 파일**을 본다.
> 역할 구분: `AGENTS.md`=변하지 않는 규칙 · `PROJECT_STATE.md`=전체 로드맵 · **`HANDOFF.md`=현재 작업+실행법+상태(매번 갱신)**.
> **작업을 멈추거나 세션 한도(≈80%)에 닿으면 아래 "상태"를 갱신하고 커밋한다** — 추적 안 된 변경은 다음 세션·에이전트에서 보이지 않는다.

---

## 현재 활성 작업 (Active Work Order)

**목표:** `docs/superpowers/plans/2026-07-24-diary-generation.md`(일기 생성) 구현.
**성격:** 계획 확정 완료 — **"코드만 짜면 되는" 상태**. 재설계하지 말고 계획을 그대로 따른다(16개 Locked Decisions로 모호함 제거됨).
**스펙 배경:** `docs/superpowers/specs/2026-07-24-diary-generation-design.md`.
**브랜치:** `feat/diary-generation`.

### 실행 방식 (플러그인 없이 수동)
Claude는 Superpowers 스킬로 수행하지만, **다른 AI(Codex 등)는 스킬이 없으니 아래를 수동으로** 밟는다. 계획 헤더의 "REQUIRED SUB-SKILL"은 무시. **Task 1 → 6 순서, TDD:**
- 태스크마다: ① 실패 테스트 작성 → ② 실행해 실패 확인 → ③ 계획의 코드 그대로 구현 → ④ 테스트 통과 → ⑤ ruff clean → ⑥ **그 태스크 단위로 1커밋**.
- 계획 안의 PowerShell 명령을 그대로 실행한다. 코드·테스트·가드레일을 임의로 바꾸지 않는다.

### 환경 (Windows)
- 파이썬은 `worker\.venv\Scripts\python.exe` 를 **직접** 호출(PATH의 `python` 가정 금지).
- 로컬 Supabase는 `127.0.0.1:54322`. `npx supabase db reset` 뒤 auth 502가 나므로 반드시 `npx supabase stop` → `npx supabase start` 후 통합 테스트. **로컬만, production 금지.**
- Task 4(Gemini)·5(eval)는 **실제 유료 Vertex 호출**. ADC는 이미 구성됨. env 3종:
  `GOOGLE_GENAI_USE_VERTEXAI=true` / `GOOGLE_CLOUD_PROJECT=project-58561b19-fb35-4c01-bb2` / `GOOGLE_CLOUD_LOCATION=global`. 스모크·eval은 각 **1회만**.
- 테스트: `worker\.venv\Scripts\python.exe -m pytest worker`(단위+통합) · `-m "not integration"`(단위만, DB 불필요) · lint `... -m ruff check worker`.

### 어기면 안 되는 것 (hard rules)
- **스키마 변경 없음** — 계획은 기존 `diaries/diary_sections/diary_sources`를 재사용한다. 새 마이그레이션 만들지 마라.
- **태스크마다 커밋만. push·merge 금지**(사람이 한다).
- 이미 병합된 기능(**extraction · detector · narration**)을 수정하지 마라 — 계획이 지정한 `diary` 패키지/파일만 추가한다.
- 커밋 메시지의 `Co-Authored-By` 트레일러는 **네 것으로** 바꿔라(네가 저자다). 형식은 `.claude/rules/git.md` 규약.
- 못 고치는 테스트 실패나 모호한 점이 있으면 **멈추고 보고**하라. 추측하거나 테스트/가드레일을 약화시키지 마라.
- 완료(DoD) = lint + typecheck + unit + integration (Task 4·5는 eval 포함).

---

## 상태 (Status) — 멈출 때 여기를 갱신하고 커밋

- **계획 확정 커밋:** `6fb49cb` · **스펙 커밋:** `9500086`.
- **구현 진행:** Task 1~6 완료 + 보안 리뷰 Important 해결. **브랜치 병합 준비 완료**(병합·push는 사람).
- **커밋된 태스크:** Task 1 `aa86eb3` · Task 2 `39e3477` · Task 3 `91ba74e` · Task 4 `6c946d1` · Task 5 `2fa7337` · Task 6 문서 `aed290e` · 보안 수정 `7682554`.
- **검증:** ruff clean · 전체 worker **94 PASS**(편집보호 통합 테스트 +1) · integration 48 PASS. 실 Vertex 스모크/eval 각 1회 소진(재호출 금지, 자동 게이트 4/4).
- **3개 판단 결과:**
  - **(1) 보안 Important — 해결.** `upsert_diary`에 `where diaries.status='draft'` 원자 조건(draft일 때만 덮어쓰기), 편집 행이면 미갱신·None → `generate_diary`가 섹션/출처 안 건드리고 기존 id 반환. TDD 통합 테스트로 고정. 커밋 `7682554`, 계획 Locked Decision #17.
  - **(2) “평소보다 일찍 나옴” — 위반 아님(수용).** “평소보다”는 확정 차이 d1 headline “평소보다 일찍 퇴근”에 실재하는 근거이고 used_diff⊆입력으로 붙는다. 일기가 메모+확정차이를 엮는 정상 범위. 가벼운 이벤트 결합(나옴↔퇴근)만 알려진 minor.
  - **(3) “다른 일 없이” — minor 위반(부재 사실 창작).** 기록 없음 ≠ 사건 없음. “과잉해석·없는 사실 창작 금지”에 걸린다. 자동 게이트로는 못 잡는 의미 문제 + 유료 eval 재호출 금지라 **지금 미수정**. **다음 승인된 eval 1회**에서 프롬프트에 “부재·총량 단정 금지(메모는 하루의 완전한 기록이 아님)” 규칙 + 골든 케이스 추가 후 재검증.
- **다음 시작점:** 사람이 `main` 위로 rebase → `merge --no-ff`(squash 금지) 병합. 병합 후 (3) 프롬프트 보강 + eval 1회(유료 승인 필요).
- **막힘/결정 필요:** (없음)

> 갱신 예: `Task 1 완료 (커밋 abc1234). 다음: Task 2 저장소.`

---

## 참고 (context)

- **confirmed 차이 의존성:** 일기는 `status='confirmed'` 차이만 넣는데 확인 UI(맞아요/아니에요)가 아직 없어(#9 유예), 당분간 실제 일기는 메모-only가 정상이다(계획이 우아하게 처리 — 평범한 일기). 버그 아님.
- **이 기능 병합 후 후보:** 유저 확정 UI(#9) · 프론트 일기 UI · detector/diary 스케줄 트리거(일 배치). 전체 로드맵은 `PROJECT_STATE.md`.
- Claude 세션이 서브에이전트 주도(SDD)로 돌 땐 `.superpowers/sdd/progress.md`에 더 세밀한 태스크 원장을 둔다(선택). **공용 진행 상태의 기준은 이 파일의 "상태" 절**이다.
