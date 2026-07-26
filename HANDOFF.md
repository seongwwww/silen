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
- **구현 진행:** 5 / 6 태스크 완료. Task 6 문서 수정 후 전체 검사에서 중단.
- **커밋된 태스크:** Task 1 `aa86eb3` · Task 2 `39e3477` · Task 3 `91ba74e` · Task 4 `6c946d1` · Task 5 `2fa7337`.
- **다음 시작점:** Task 6 Step 3 — `README.md`·`supabase/README.md` 수정은 계획대로 적용됐으나 미커밋. ruff clean·현재 로컬 DB 기준 전체 worker 테스트 93건 PASS. `npx supabase db reset`은 아직 실행되지 않음.
- **막힘/결정 필요:** (1) 사용자가 2026-07-24 로컬 DB reset을 명시 승인했으나, 실행 계층이 `AGENTS.md`의 “DB 삭제·마이그레이션 적용은 사람이 실행” 규칙으로 거부함. AI 재시도·우회 금지. 첫 수동 시도는 다른 폴더에서 실행돼 project id가 `s2608`로 잡혔고, 정상 실행 중인 `supabase_db_silen`이 점유한 54322와 충돌해 reset 전에 실패함. 사람이 반드시 `Set-Location C:\workspace\silen` 후 `npx.cmd supabase db reset` → `npx.cmd supabase stop` → 3초 후 `npx.cmd supabase start`를 실행하고 완료를 알려야 integration 재검증부터 이어갈 수 있음. (2) Task 4 첫 스모크의 `one_line`은 메모 “오늘 좀 일찍 나옴”을 “평소보다 일찍 나옴”으로 승격함(`평소보다` 근거는 퇴근 차이에만 존재). (3) Task 5 eval 자동 게이트는 4/4 PASS했으나 `hallucination-temptation` body의 “다른 일 없이”는 입력에 없는 부재 사실일 수 있음. (2)·(3)은 구현을 막지 않고 Claude 판단 사항으로 보류; 프롬프트·가드레일 임의 수정 금지. Task 4 스모크와 Task 5 eval은 각 허용 횟수 1회를 이미 소진했으므로 재호출하지 말 것.

> 갱신 예: `Task 1 완료 (커밋 abc1234). 다음: Task 2 저장소.`

---

## 참고 (context)

- **confirmed 차이 의존성:** 일기는 `status='confirmed'` 차이만 넣는데 확인 UI(맞아요/아니에요)가 아직 없어(#9 유예), 당분간 실제 일기는 메모-only가 정상이다(계획이 우아하게 처리 — 평범한 일기). 버그 아님.
- **이 기능 병합 후 후보:** 유저 확정 UI(#9) · 프론트 일기 UI · detector/diary 스케줄 트리거(일 배치). 전체 로드맵은 `PROJECT_STATE.md`.
- Claude 세션이 서브에이전트 주도(SDD)로 돌 땐 `.superpowers/sdd/progress.md`에 더 세밀한 태스크 원장을 둔다(선택). **공용 진행 상태의 기준은 이 파일의 "상태" 절**이다.
