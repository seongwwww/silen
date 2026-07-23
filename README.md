# 실은 (silen)

똑같다고 생각한 하루에서 놓친 차이를 찾아주는 앱. "실은 아무것도 아니지 않았다."

핵심 원칙은 [`CLAUDE.md`](./CLAUDE.md), 도메인 규칙은 [`.claude/rules/`](./.claude/rules/), 설계 문서는 [`docs/`](./docs/)에 있다.

## 저장소 구조

```
CLAUDE.md               # 항상 적용되는 개발 원칙 (200줄 이하)
AGENTS.md               # Next.js 16 버전 고지 (코드 작성 전 필독)
.claude/rules/          # 도메인별 규칙 (프론트/백엔드/DB/프라이버시/AI-eval/테스트/git)
app/                    # 경계 계층 — Route Handler·페이지
app/api/memories/       # 기록 생성 API (텍스트·감정·사진)
lib/time/               # "하루" 경계 단일 유틸
lib/services/           # 서비스 계층 (프레임워크 타입을 모름)
lib/repositories/       # 저장소 계층 (쿼리·user 스코프 강제)
components/ui|common/   # 공통 컴포넌트 (frontend.md)
worker/                 # Python 워커 (차이 탐지·AI 잡)
worker/src/silen_worker/tasks/        # 큐 소비 잡 진입점(process_pending)
worker/src/silen_worker/extraction/   # 엔티티 추출 (가드레일·정규화·Vertex Gemini)
worker/src/silen_worker/db.py         # 워커 DB 접근(user 스코프 강제)
fixtures/               # 두 자산이 공유하는 골든 케이스
evals/entities/         # 엔티티 추출 골든셋 (환각·빈날·조사·병합·4종)
supabase/migrations/    # 마이그레이션 (down/ 에 보상 스크립트)
docs/
  planning/서비스_기획서.md   # 제품 기획 (단일 출처)
  design/ERD.mermaid         # 데이터 모델
  design/wireframes.html     # 화면 와이어프레임
  design/prompts-draft.md    # 탐지→서술 프롬프트 초안
  decisions/                 # ADR (중요 결정 기록)
  superpowers/               # 스펙·구현 계획
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

### 2. 로컬 개발

전제: Node 20+, **Python 3.11+**, Docker Desktop 실행.

```powershell
# 앱 (저장소 루트)
npm install
# `.env.local`을 만든다(`.env.example` 참고). 값은 `npx supabase status`로 확인.

# Python 워커 — `python`이 다른 버전을 가리킬 수 있으므로 py launcher 사용
py -3.12 -m venv worker\.venv
worker\.venv\Scripts\python.exe -m pip install -e "worker[dev]"

# 로컬 DB (Supabase 스택 — Docker 필요)
npx supabase start
npx supabase db reset
```

### 3. 검사

```powershell
npm run check              # lint + typecheck + unit
npm run test:integration   # 통합 (Supabase 스택 기동 필요)
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration"   # 단위(DB 불필요)
worker\.venv\Scripts\python.exe -m pytest worker -m integration          # 통합(Supabase 스택 필요)

# 엔티티 추출 eval — 실 Vertex Gemini 호출(비용 발생), ADC + env 3종 필요
$env:GOOGLE_GENAI_USE_VERTEXAI="true"; $env:GOOGLE_CLOUD_PROJECT="<PROJECT>"; $env:GOOGLE_CLOUD_LOCATION="global"
worker\.venv\Scripts\python.exe evals/entities/run.py
```

> shadcn/ui는 첫 화면 작업 시 도입.

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
