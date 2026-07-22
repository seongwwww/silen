# 실은 (silen) — 개발 원칙

> "실은 아무것도 아니지 않았다." 똑같다고 생각한 하루에서 놓친 차이를 찾아주는 앱.
> 이 파일은 **항상 적용되는 핵심 원칙**만 담는다. 세부 규칙은 `.claude/rules/`, 절차는 Skill, 강제 검사는 Hook으로 분리한다. 200줄 이하 유지.

## 제품 불변 원칙 (product invariants)

- **탐지는 통계·규칙이, 서술은 LLM이.** deterministic detector만 차이를 검출한다. LLM에게 "차이를 찾아줘"라고 시키지 않는다.
- **LLM은 사실·행동·장소·감정·인과를 추측하지 않는다.** 검증된 차이(evidence)만 담백하게 문장화한다.
- **원본 기록과 AI 생성물은 분리 저장한다.** memories/assets ↔ diaries/differences.
- **모든 생성 결과에는 근거가 있어야 한다.** 출력에 memory_id / difference_id를 반드시 포함(추적성).
- **의무가 아니라 선물.** 스트릭·연속 기록 압박 등 죄책감 유도 UI 금지. 평범한 날은 평범하게.
- **과잉해석 금지.** 자기계발 앱화 금지. 이미 있었던 작은 변화를 발견해줄 뿐.

## 프라이버시 불변 원칙

- 사용자 기록 **본문을 로그·에러 추적 서비스에 남기지 않는다.**
- 센서·사진 데이터는 **명시적 동의(opt-in) 없이 수집하지 않는다.** 기본 OFF.
- **파생 신호만 저장**한다(연속 GPS 대신 방문 장소 라벨 등).
- **삭제는 DB · Storage · Embedding · 검색 인덱스를 모두 처리**한다. 동의 철회 시 파생 삭제.
- AI 학습에 사용자 데이터를 쓰지 않는다.

## 엔지니어링 불변 원칙

- **모든 비동기/큐 작업은 멱등(idempotent)** 해야 한다. 재시도가 중복 레코드를 만들지 않는다.
- **타임존 경계를 명시적으로 다룬다.** "하루"의 정의(사용자 로컬 자정)를 한 곳에서 관리한다.
- **멀티테넌시 격리.** 모든 쿼리·검색·임베딩은 user_id로 필터. 교차 조회 불가.
- **완료(Definition of Done) = lint + typecheck + unit + integration + eval 전부 통과.**

## 기술 스택

- 프론트: Next.js(App Router) · TypeScript · Tailwind · shadcn/ui · 모바일 우선 PWA
- 백엔드: 앱·API는 Next.js Route Handlers / 차이 탐지·AI 잡은 **Python 워커**(numpy/scipy/pandas)
- DB: PostgreSQL + pgvector + PostGIS / 인증·파일: Supabase
- 상세는 `.claude/rules/{frontend,backend,database}.md` 참조.

## 규칙 파일 (항상 함께 로드)

- `.claude/rules/frontend.md` — UI/UX·접근성·상태 처리·죄책감 유발 금지
- `.claude/rules/backend.md` — API·워커·멱등성·에러 처리·로깅
- `.claude/rules/database.md` — 스키마·마이그레이션·삭제 추적·근거 연결
- `.claude/rules/privacy.md` — 동의·삭제·RAG·민감 데이터
- `.claude/rules/ai-evals.md` — 탐지/서술 분리·골든셋·프롬프트 회귀
- `.claude/rules/testing.md` — 테스트 전략·커버리지 기준
- `.claude/rules/git.md` — 커밋 단위·메시지 규약·브랜치·히스토리 프라이버시
- `AGENTS.md` — Next.js 16 버전 고지. **앱 코드 작성 전 `node_modules/next/dist/docs/`의 해당 문서를 먼저 읽는다.** 이 버전은 학습 데이터와 API·관례가 다르다.

## 표준 개발 루프 (기능 단위)

1. `/superpowers:brainstorming` — 기획서·ERD·유저 흐름으로 모호한 요구사항 정리
2. `/superpowers:writing-plans` → `/superpowers:using-git-worktrees` — 기능별 worktree 분리
3. TDD로 구현 (테스트 통과 지점마다 작은 commit)
4. 리뷰: `/superpowers:requesting-code-review` → `/code-review high` → `/security-review`(Auth·삭제·RAG 변경 시) → `/simplify`
5. 피드백: `/superpowers:receiving-code-review` 로 각 항목 Accept/Reject/Defer/Experiment 분류
6. 중요 결정은 `docs/decisions/ADR-xxxx.md` 로 남긴다
7. 종료: `/superpowers:finishing-a-development-branch` 로 merge/PR/keep/discard

## 안전 가드 (Claude 자동 실행 금지)

- 데이터 삭제, DB 마이그레이션 적용, 배포(deploy), production DB 접근은 **자동 승인 금지.** 사람이 실행.
- `/rewind`는 로컬 편집 실수 복구 전용 — Bash·DB·Storage 변경은 되돌리지 못한다. 롤백은 Git으로.
- 마이그레이션에는 대응되는 down/보상 전략을 함께 작성하고 staging에서 dry-run.

## 디버깅

앱 버그는 `/superpowers:systematic-debugging`: 재현 → 경계에서 증거 수집 → 단일 가설 → 최소 수정 → 회귀 테스트 → 전체 검사.
주의 시나리오: 일기 중복 생성 · 타 사용자 embedding 검색 · 삭제 후 Storage/pgvector 잔존 · 타임존 경계 메모 누락 · detector에 없는 해석이 일기에 추가 · 재시도 큐 중복 레코드.
