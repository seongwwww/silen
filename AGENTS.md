# AGENTS.md — 모든 AI 에이전트 진입점 (silen)

> 이 저장소는 여러 AI(Claude · ChatGPT/Codex · Gemini · Cursor 등)가 번갈아 이어서 작업한다.
> **어떤 에이전트든 세션을 시작할 때 이 파일을 먼저 읽는다.** 여기 규칙은 특정 AI 전용이 아니라 모두에게 적용된다.

## 제품 한 줄

"실은 아무것도 아니지 않았다." — 똑같다고 느낀 하루에서 **놓친 작은 차이**를 찾아 담담하게 보여주는 모바일 우선 PWA 일기 앱(한국어). 핵심 원칙: **탐지=통계(결정적 detector), 서술=LLM.** LLM은 검증된 차이만 문장화하고 추측하지 않는다.

## 시작할 때 (모든 세션, 이 순서로)

1. **`AGENTS.md`** (이 파일) — 진입점·규칙·워크플로·핸드오프.
2. **`CLAUDE.md`** — 항상 적용되는 핵심 원칙(제품·프라이버시·엔지니어링 불변). 이름은 CLAUDE지만 **모든 AI가 지킨다.**
3. **`.claude/rules/*.md`** — 도메인별 상세 규칙(frontend/backend/database/privacy/ai-evals/testing/git). 평범한 마크다운이라 어떤 에이전트든 읽을 수 있다.
4. **`PROJECT_STATE.md`** — 지금 어느 단계인지(로드맵·현재 브랜치·다음 착수).
5. 손대는 기능의 스펙·계획: `docs/superpowers/specs/`, `docs/superpowers/plans/`.
6. 최근 히스토리: `git log --oneline -15`.

그다음 `PROJECT_STATE.md`의 "다음 착수" 또는 미완 작업을 이어간다.

## 반드시 지키는 규칙 (요약 — 상세는 `CLAUDE.md`·`.claude/rules/`)

- **탐지=통계, 서술=LLM.** LLM에게 "차이를 찾아줘" 금지. 근거 없는 문장 금지 — 출력의 모든 사실이 입력 근거(memory_id/difference_id)에 존재해야 하고, 출력에 그 ID를 포함한다.
- **프라이버시는 제약이다.** 사용자 기록 본문을 로그·APM·에러추적·커밋 메시지·브랜치명·fixture 파일명에 남기지 않는다. 학습에 사용자 데이터 미사용. 센서·사진은 opt-in 기본 OFF. 삭제는 DB·Storage·임베딩·검색 인덱스를 모두 처리.
- **멱등**(모든 큐/비동기), **타임존 경계**(사용자 로컬 자정, 단일 유틸), **user_id 스코프 강제**(교차 사용자 조회 불가 — 워커는 RLS를 우회하므로 코드 필터가 유일한 방어선).
- **완료(DoD) = lint + typecheck + unit + integration + eval 전부 통과.**
- 커밋: `<type>(<scope>): <한국어 요약>`, AI 작성 시 `Co-Authored-By` 트레일러. squash merge 금지, `--no-verify` 금지.

## 개발 워크플로 (플러그인 없이도 따라할 수 있게)

Claude 세션은 이 절차를 **Superpowers 스킬**로 자동 수행한다(`brainstorming` → `writing-plans` → `subagent-driven-development`/`executing-plans` → `finishing-a-development-branch`, 버그는 `systematic-debugging`). 이 스킬들은 Claude 플러그인이라 다른 AI엔 없다 — **다른 AI는 아래 절차를 수동으로 동일하게** 밟는다:

1. **브레인스토밍 → 설계 스펙**을 `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`에 쓰고 사람 승인을 받는다(코드 전 설계 게이트).
2. **구현 계획**을 `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`에 태스크·스텝 단위로 쓴다(파일 경로·테스트·완료 기준 명시).
3. 기능 브랜치(`feat/<topic>`, kebab-case)에서 **TDD**로 구현 — 실패 테스트 → 최소 구현 → 테스트 통과 지점마다 작은 커밋.
4. **리뷰**(변경 성격에 맞게): 코드 리뷰 → Auth·삭제·RAG 변경 시 보안 리뷰.
5. **종료**: main 위로 rebase → `merge --no-ff`(squash 금지) 또는 PR.
- 진행 중 기능의 태스크 상태·커밋 SHA는 `.superpowers/sdd/progress.md` 원장에 남는다(있으면 여기서 복원).

## 세션 연속성 · 핸드오프 (중요)

여러 에이전트가 이어받으므로 **상태를 문서·git에 남긴다.** 대화 컨텍스트는 세션이 끝나면 사라진다.

- **세션이 한도에 근접(≈80%)하거나 작업을 멈출 때**, 다음 에이전트가 즉시 이어받도록 정리한다:
  1. `PROJECT_STATE.md`를 현재 기준으로 갱신(현재 목표·단계·브랜치·다음 착수·최근 변경).
  2. 기능 진행 중이면 `.superpowers/sdd/progress.md` 원장에 완료 태스크·커밋 SHA·남은 것을 기록.
  3. 새 설계 결정은 스펙/계획 문서 또는 `docs/decisions/ADR-xxxx.md`에 남긴다.
  4. 문서·설정 변경은 커밋한다(문서·설정은 main 직접 커밋 허용, `.claude/rules/git.md`). 코드는 브랜치/PR로.
- **상태의 단일 출처는 git이다.** 추적되지 않은 로컬 파일은 다른 세션·머신·에이전트에서 보이지 않는다 — 이어받게 하려면 반드시 커밋한다.
- 검증 기준: "다음 AI가 대화 기록 없이 위 문서들만 읽고 이어서 작업할 수 있는가?" 아니라면 부족한 걸 채운다.

## 안전 가드 (AI 자동 실행 금지 — 사람이 실행)

- 데이터 삭제 · DB 마이그레이션 적용 · 배포 · production DB 접근은 AI가 자동 실행하지 않는다.
- **커밋·push·병합은 사람이 요청할 때만.** AI가 임의로 하지 않는다.
- 마이그레이션은 up/down을 함께 작성하고 staging에서 dry-run.

<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->
