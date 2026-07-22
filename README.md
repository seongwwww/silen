# 실은 (silen)

똑같다고 생각한 하루에서 놓친 차이를 찾아주는 앱. "실은 아무것도 아니지 않았다."

핵심 원칙은 [`CLAUDE.md`](./CLAUDE.md), 도메인 규칙은 [`.claude/rules/`](./.claude/rules/), 설계 문서는 [`docs/`](./docs/)에 있다.

## 저장소 구조

```
CLAUDE.md               # 항상 적용되는 개발 원칙 (200줄 이하)
.claude/rules/          # 도메인별 규칙 (프론트/백엔드/DB/프라이버시/AI-eval/테스트)
docs/
  planning/서비스_기획서.md   # 제품 기획 (단일 출처)
  design/ERD.mermaid         # 데이터 모델
  design/wireframes.html     # 화면 와이어프레임
  design/prompts-draft.md    # 탐지→서술 프롬프트 초안
  decisions/                 # ADR (중요 결정 기록)
```

## 개발 환경 세팅

### 1. 워크플로 플러그인 설치 (Claude Code / Cowork)

```
/plugin install superpowers@claude-plugins-official
/plugin install frontend-design@claude-plugins-official
```

- **superpowers** — 요구사항 인터뷰·계획·git worktree·TDD·체계적 디버깅·코드 리뷰·병합 결정.
- **frontend-design** — 타이포·색·레이아웃·반응형·접근성 점검(화면 구현/리뷰 시).
- ECC는 전체 설치하지 않고 PostgreSQL·Python·eval·security 부분만 참고. Ralph는 완료 조건이 기계적으로 확인되는 좁은 작업에만 제한적으로.

### 2. 앱 스캐폴딩 (아직 미생성)

```
# 프론트/API
npx create-next-app@latest . --typescript --tailwind --app --eslint
# shadcn/ui
npx shadcn@latest init
# Python 워커 (별도 디렉터리, 예: worker/)
python3 -m venv .venv && source .venv/bin/activate
pip install numpy scipy pandas
```

> DB(Supabase/Postgres+pgvector+PostGIS), 큐, 워커 배선은 ADR-0002(설계 리뷰 게이트) 이후 착수.

## 표준 개발 루프 (기능 단위)

1. `/superpowers:brainstorming` — 기획서·ERD·유저 흐름으로 요구사항 정리
2. `/superpowers:writing-plans` → `/superpowers:using-git-worktrees`
3. TDD 구현 (테스트 통과 지점마다 작은 commit)
4. `/superpowers:requesting-code-review` → `/code-review high` → `/security-review`(Auth·삭제·RAG 변경 시) → `/simplify`
5. `/superpowers:receiving-code-review` — 피드백을 Accept/Reject/Defer/Experiment로 분류
6. 중요 결정은 `docs/decisions/ADR-xxxx.md`
7. `/superpowers:finishing-a-development-branch` — merge/PR/keep/discard

버그: `/superpowers:systematic-debugging` (재현→증거→단일 가설→최소 수정→회귀 테스트→전체 검사).

## 자동 진행 · 반복

- `/goal` — 완료 조건이 명확한 작업을 여러 턴에 걸쳐 완성.
- `/loop` — CI·PR·리뷰 상태 반복 확인.
- 둘 다 **삭제·배포·마이그레이션·production 접근은 자동 금지**로 지시.

## 안전 · 롤백

- 기능마다 worktree/branch, 테스트 통과 지점마다 작은 commit.
- 마이그레이션엔 down/보상 전략 + staging dry-run.
- `/rewind`는 로컬 편집 복구 전용(Bash·DB·Storage는 못 되돌림). 롤백은 Git으로.
- 데이터 삭제·배포·마이그레이션은 사람이 실행.

## Definition of Done

lint + typecheck + unit + integration + eval 전부 통과.
