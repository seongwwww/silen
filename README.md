# 실은 (silen)

똑같다고 생각한 하루에서 놓친 차이를 찾아주는 앱. "실은 아무것도 아니지 않았다."

핵심 원칙은 [`CLAUDE.md`](./CLAUDE.md), 도메인 규칙은 [`.claude/rules/`](./.claude/rules/), 설계 문서는 [`docs/`](./docs/)에 있다.

## 저장소 구조

```
CLAUDE.md               # 항상 적용되는 개발 원칙 (200줄 이하)
AGENTS.md               # Next.js 16 버전 고지 (코드 작성 전 필독)
.claude/rules/          # 도메인별 규칙 (프론트/백엔드/DB/프라이버시/AI-eval/테스트/git)
app/                    # 경계 계층 — Route Handler·페이지
app/page.tsx            # 홈 = 발견·Daily Wrap·오늘 기록 요약
app/record/             # 5초 기록 화면 (텍스트 + 감정 칩)
app/_components/        # 홈 전용 컴포넌트 — 발견 카드·Daily Wrap
app/api/memories/       # 기록 생성 API (텍스트·감정·사진)
app/api/differences/    # 차이 확인 PATCH API (전이 검증·RLS)
app/api/export/         # 본인 데이터 JSON 내보내기
app/api/account/data/   # 전체 기록 삭제 요청(실제 삭제는 워커)
app/review/             # 오늘의 다른 점 확인 화면
app/diary/              # 일기 보기 (최신 · 근거 접기 · 날짜 이동 /diary/[date])
app/report/             # 주간 리포트(7일 막대·3개 고정 슬롯)
app/recall/             # 본인 기록 키워드 회고
app/settings/           # 톤·JSON 내보내기·전체 기록 삭제
app/demo/               # 실제 API를 쓰지 않는 Daily Wrap·리포트 목데이터
lib/time/               # "하루" 경계 단일 유틸
lib/services/           # 서비스 계층 (프레임워크 타입을 모름)
lib/repositories/       # 저장소 계층 (쿼리·user 스코프 강제)
components/ui/          # shadcn/ui primitive
components/common/      # 실은 도메인 공통 컴포넌트
worker/                 # Python 워커 (차이 탐지·AI 잡)
worker/src/silen_worker/tasks/        # 큐 소비 잡 진입점(process_pending)
worker/src/silen_worker/extraction/   # 엔티티 추출 (가드레일·정규화·Vertex Gemini)
worker/src/silen_worker/cli.py        # 파이프라인 CLI(run-pending·run-scheduled·run-daily·run-diary·run-weekly·stats)
worker/src/silen_worker/db.py         # 워커 DB 접근(user 스코프 강제)
fixtures/               # 두 자산이 공유하는 골든 케이스
evals/entities/         # 엔티티 추출 골든셋 (환각·빈날·조사·병합·4종)
evals/narration/        # 차이 서술 골든셋 (조언·인과·감정승격 방지)
evals/diary/            # 일기 생성 골든셋 (환각·평범한날·근거정합)
supabase/migrations/    # 마이그레이션 (down/ 에 보상 스크립트)
docs/
  planning/서비스_기획서.md   # 제품 기획 (단일 출처)
  design/ERD.mermaid         # 데이터 모델
  design/wireframes.html     # 화면 와이어프레임
  design/prompts-draft.md    # 탐지→서술 프롬프트 초안
  decisions/                 # ADR (중요 결정 기록)
  superpowers/               # 스펙·구현 계획
```

확인 UI(`/review`)는 narrated 후보를 보여주고 [맞아요]/[아니에요] 피드백과
5초 undo를 제공한다. 확인은 일기 반영의 관문이 아니며, [아니에요]로 기각한
차이만 일기에서 제외한다.
일기 화면(`/diary`)은 가장 최근 일기와 무엇을 보고 썼는지(근거 메모)를 접어서 함께 보여준다. AI 초안을 고치거나 확정할 수 있고, 늦은 기록을 반영하려면 다시 만들기를 요청할 수 있다. 이전/다음 버튼으로 과거 일기(`/diary/[date]`)를 오갈 수 있으며, 일기가 없는 날은 건너뛰고 실제 일기가 있는 날짜로 점프한다. 처음 등장한 것은 "오늘 처음" 목록으로 모아 보여주고, 그중 하나에 대해 부담 없는 질문을 한 번 건넨다(답하면 새 기록이 된다). 일기 생성은 `run-diary`(§4)가 하며 화면의 다시 만들기는 즉시 생성하지 않고 다음 실행에 반영할 요청만 남긴다.

주간 리포트(`/report`)는 첫 활성 기록일부터 완결된 7일 블록을 묶고, 회고
(`/recall`)는 잠기거나 삭제되지 않은 본인 기록만 최신순 키워드로 찾는다.
화면 검수용 `/demo`와 `/report?demo=1`은 프런트 fixture만 사용하며 실제
사용자 데이터나 API를 건드리지 않는다.

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

# 차이 서술 eval — 실 Vertex Gemini 호출(비용), ADC + env 3종 필요
worker\.venv\Scripts\python.exe evals/narration/run.py

# 일기 생성 eval — 실 Vertex Gemini 호출(비용), ADC + env 3종 필요
worker\.venv\Scripts\python.exe evals/diary/run.py
```

### 4. 파이프라인 실행

워커 함수는 CLI로 구동한다. **주기 실행은 OS 스케줄러에 위임**한다(상주 데몬 없음).

```powershell
# 큐 소비 → 엔티티 추출 (실 Vertex 호출·비용)
worker\.venv\Scripts\python.exe -m silen_worker run-pending

# 사용자 로컬 설정 시각이 지난 오늘 일기 요청을 기존 큐에 멱등 등록
worker\.venv\Scripts\python.exe -m silen_worker run-scheduled

# 차이 검출 → 서술 (실 Vertex 호출·비용). 기본 대상: 전체 사용자 × 각자 로컬 어제
worker\.venv\Scripts\python.exe -m silen_worker run-daily

# 일기 생성 (candidate·confirmed 중 기각하지 않은 intact 차이 반영)
worker\.venv\Scripts\python.exe -m silen_worker run-diary

# 주간 리포트 (첫 기록일 기준 방금 끝난 7일 블록만, 기본: 각자 로컬 오늘)
worker\.venv\Scripts\python.exe -m silen_worker run-weekly

# 읽기 전용 MVP 운영 지표(명시적 피드백·차이 수·일기·관측일수)
worker\.venv\Scripts\python.exe -m silen_worker stats

# 특정 사용자·날짜만 (디버깅·재실행)
worker\.venv\Scripts\python.exe -m silen_worker run-daily --user <uuid> --date 2026-07-26
worker\.venv\Scripts\python.exe -m silen_worker run-weekly --user <uuid> --date 2026-07-29
```

전제: Vertex ADC env 3종(`GOOGLE_GENAI_USE_VERTEXAI`·`GOOGLE_CLOUD_PROJECT`·`GOOGLE_CLOUD_LOCATION`).

`run-diary`는 사용자의 확인을 기다리지 않는다. `run-daily`가 만든 candidate도
바로 일기 재료가 되며, [아니에요]로 기각한 차이와 근거가 stale인 차이만 빠진다.
`run-scheduled`는 기록이 있는 오늘 날짜의 요청만 기존 요청 원장과 `memory_jobs`
큐에 등록한다. 실제 생성은 기존 `run-pending`이 맡으며, 같은 날 반복 실행해도
`(user_id, date)` 유니크 제약으로 요청과 일기는 하나만 생긴다.
`run-weekly`는 첫 활성 메모의 로컬 날짜를 기준으로 완결된 7일 블록만 집계한다.
매일 실행해도 경계가 아닌 날은 건너뛰며, 같은 블록 재실행은 기존 리포트와
하이라이트를 멱등 갱신한다.
차이를 먼저 계산하려면 아래 순서로 실행하되, 사이에 사람의 확인 단계는 필요 없다:

```
run-daily (자정 이후)  →  run-diary (그날 밤)
```

차이를 일기에 쓸 때는 생활 전체의 사실로 승격하지 않고 반드시
*"최근 기록에서"*처럼 기록 범위를 유지한다. 이 가드레일을 통과하지 못한 출력은
status와 관계없이 저장하지 않는다.

**재실행 안전:** 이미 서술된 차이는 LLM을 다시 부르지 않는다. 스케줄러가 자주 돌아도 새 차이에만 비용이 든다.

**종료 코드:** 전부 성공 `0`, 사용자 처리 실패가 하나라도 있으면 `1`.

#### 스케줄 등록 (사람이 실행)

Windows 작업 스케줄러 예시 — **아래는 안내이며 등록은 사람이 직접 한다.**

```powershell
# 5분마다 큐 소비
schtasks /create /tn "silen-run-pending" /sc minute /mo 5 ^
  /tr "C:\workspace\silen\worker\.venv\Scripts\python.exe -m silen_worker run-pending"

# 5분마다 사용자별 일기 예약 시각 확인
schtasks /create /tn "silen-run-scheduled" /sc minute /mo 5 ^
  /tr "C:\workspace\silen\worker\.venv\Scripts\python.exe -m silen_worker run-scheduled"

# 매일 00:30 차이 검출·서술
schtasks /create /tn "silen-run-daily" /sc daily /st 00:30 ^
  /tr "C:\workspace\silen\worker\.venv\Scripts\python.exe -m silen_worker run-daily"

# 매일 22:00 일기 생성
schtasks /create /tn "silen-run-diary" /sc daily /st 22:00 ^
  /tr "C:\workspace\silen\worker\.venv\Scripts\python.exe -m silen_worker run-diary"

# 매일 01:00, 해당 사용자에게 막 끝난 7일 블록이 있으면 주간 리포트 생성
schtasks /create /tn "silen-run-weekly" /sc daily /st 01:00 ^
  /tr "C:\workspace\silen\worker\.venv\Scripts\python.exe -m silen_worker run-weekly"
```

작업 스케줄러는 작업의 "시작 위치"를 저장소 루트로 두고, ADC env가 필요한 작업은 사용자 계정 컨텍스트로 실행해야 한다.

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
