# PROJECT STATE — 실은 (silen)

> 로드맵·현재 상태 스냅샷. 진입점·규칙·핸드오프 절차는 `AGENTS.md`, 핵심 원칙은 `CLAUDE.md`.
> 진행 중 기능의 태스크별 상태는 `.superpowers/sdd/progress.md`(있을 때).

## 제품 한 줄

"실은 아무것도 아니지 않았다." — 똑같다고 느낀 하루에서 **놓친 작은 차이**를 찾아 담담하게 보여주는 모바일 우선 PWA 일기 앱. (한국어 서비스)

핵심 불변 원칙: **차이 탐지는 통계·규칙(detector)이, 서술은 LLM이.** LLM은 검증된 차이만 문장화하고 추측하지 않는다. 죄책감 유도(스트릭 등)·과잉해석 금지.

## 현재 단계

**백엔드 파이프라인 전 구간 완성 + 프론트 입구 열림.** 기록(memory) → 큐 → 엔티티 추출 → detector(차이 검출) → 차이 서술(LLM) → 일기 생성까지 모두 main에 병합됐고, 사람이 기록할 **홈 기록 화면**과 차이를 확정하는 **확인 UI**도 병합됐다.

**파이프라인이 실제로 돈다.** 워커 CLI가 붙어(`python -m silen_worker run-pending|run-daily|run-diary`) 메모가 쌓이면 추출 → 차이 검출·서술 → (사람 확정) → 일기까지 명령으로 흐른다. 이미 서술된 차이는 LLM을 다시 부르지 않아 스케줄러가 자주 돌아도 새 차이에만 비용이 든다.

**남은 운영 작업(사람):** 스케줄러 실제 등록(`README.md` §4에 Windows 작업 스케줄러 예시). 등록 전까지는 사람이 명령을 직접 실행한다.

**MVP 루프가 닫혔다.** 기록(`/`) → 확인(`/review`) → **일기 보기(`/diary`)** 까지 화면이 이어져, 사용자가 남긴 기록이 파이프라인을 거쳐 다시 사용자에게 돌아온다.

**⚠️ 파이프라인은 아직 실데이터로 끝까지 검증되지 않았다.** CLI 명령은 정상 동작하지만(종료 코드 0), 실행 시점에 큐가 비어 있어 데이터가 흐르지 않았다. 현재 큐에 미처리 메모 1건이 `read_ct=0`으로 대기 중이라 `run-pending`부터 다시 돌리면 된다.

**다음 후보:** 일기 편집·확정 · 목록 · 기록 열람 · 사진 첨부.

## 기능 로드맵

| # | 기능 | 상태 | 위치 |
|---|------|------|------|
| 1 | 스캐폴딩(Next.js+워커+Supabase) | ✅ main 병합 | PR #1 |
| 2 | ADR-0002 스키마 게이트(근거 조인·삭제 원장 등) | ✅ main 병합 | PR #2 |
| 3 | 인증(익명 시작 + 매직링크 연결 + RLS) | ✅ main 병합 | PR #3 |
| 4 | 기록 백엔드(POST /api/memories, 텍스트·감정·사진) | ✅ main 병합 | PR #4 |
| 5 | 워커 파이프라인(pgmq 트리거 + process_pending) | ✅ main 병합 | PR #5 |
| 6 | **엔티티 추출(Vertex Gemini + 가드레일 + eval)** | ✅ main 병합 | PR #6 |
| 7 | detector(first_occurrence·freq_shift 통계 차이 검출) | ✅ main 병합 | PR #7 |
| 8 | 차이 서술(LLM, 근거 연결·가드레일·eval) | ✅ main 병합 | PR #8 |
| 8b | 일기 생성(메모+확정차이 → 하루 일기, 하루 1건 멱등) | ✅ main 병합 | `b94d03c` |
| 9a | 확인 UI(차이 카드 맞아요/아니에요) | ✅ main 병합 | `ecfa6f2` |
| 9b | 기록 화면(홈을 메모 입력으로 — 파이프라인 입구) | ✅ main 병합 | `d42906b` |
| 10 | 파이프라인 트리거(워커 CLI · 재실행 안전) | ✅ main 병합 | `3c90e5d` |
| 11 | 일기 보기 화면(`/diary` · 근거 접기 · 상태 구분) | ✅ main 병합 | `e0e701d` |
| 12 | 일기 날짜 이동(`/diary/[date]` · 존재하는 일기로 점프) | ✅ main 병합 | `d0b5aed` |
| **13** | **일기 편집·확정 · 목록 · 기록 열람 · 사진 첨부** | 🔧 **다음 착수** | — |
| — | 스케줄러 실제 등록(운영) | ⬜ 사람이 실행 | `README.md` §4 |

## 지금 브랜치

- `main` (병합 지점 `d0b5aed`, 일기 날짜 이동 merge). **origin/main과 동기화됨.** 검증: 프론트 단위 **53** · 통합 **49** · 워커 **113** · lint·build·ruff clean.
- 다음: **#13**(일기 편집·확정 등)를 새 기능 브랜치(`feat/…`)로 분기해 착수. 표준 루프(`AGENTS.md`의 워크플로: 브레인스토밍 → 계획 → 브랜치 → TDD → 리뷰 → PR).
- 미해결 사소 항목:
  - 워커 CLI가 stdout을 UTF-8로 reconfigure하지 않는다(eval 러너들은 함). 크래시는 없고 콘솔 코드페이지에 따라 한글 도움말이 깨져 보일 수 있다 — 다음 워커 작업 때 한 줄 추가하면 된다.
  - `eslint.config.mjs`의 `app → lib/repositories` 예외 목록이 읽기 화면마다 늘고 있다(현재 4개). 또 추가하게 되면 목록 대신 "`*Repository.ts` 팩토리 허용"으로 기준 자체를 다시 세울 것(해당 주석에도 기록됨).

## 빌드 · 테스트 (Windows)

```powershell
# Next.js 앱
npm install
npm run dev            # 개발 서버
npm run lint

# Python 워커 (venv: worker\.venv)
worker\.venv\Scripts\python.exe -m pytest worker                 # 전체(단위+통합)
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration"  # 단위만(DB 불필요)
worker\.venv\Scripts\python.exe -m ruff check worker

# 로컬 Supabase (통합 테스트 전제)
npx supabase start
# ⚠️ db reset 후에는 auth(Kong→GoTrue) 502가 생김 → 반드시:
npx supabase db reset; npx supabase stop; npx supabase start

# 엔티티 추출 eval (실제 Vertex 호출 — ADC 필요, 아래 참고)
$env:GOOGLE_GENAI_USE_VERTEXAI="true"; $env:GOOGLE_CLOUD_PROJECT="project-58561b19-fb35-4c01-bb2"; $env:GOOGLE_CLOUD_LOCATION="global"
worker\.venv\Scripts\python.exe evals/entities/run.py
```

## 기술 스택

- **프론트/API:** Next.js 16 (App Router, ⚠️ 학습데이터와 API 다름 — `AGENTS.md`·`node_modules/next/dist/docs/` 필독) · TypeScript · Tailwind · shadcn/ui · PWA · Vitest.
- **워커:** Python 3.12 (numpy/scipy/pandas 예정) · psycopg 3 · pgmq · **google-genai(Vertex AI)** · pytest.
- **데이터:** PostgreSQL + pgvector + PostGIS · Supabase(Auth·Storage·로컬 스택 127.0.0.1:54322).
- **LLM:** Vertex AI Gemini(`gemini-3.5-flash` @ `location=global`), **ADC 인증**(조직 정책이 API 키 금지). 무학습 구성.

## 아키텍처 한눈에

- **2자산:** Next.js 앱(인증·CRUD·큐 적재) ↔ Python 워커(탐지·서술·임베딩). **큐(pgmq)와 DB로만 통신.** 서로 직접 호출 안 함.
- **3계층(각 자산):** 경계(Route Handler/Task 진입점) → 서비스(순수 도메인) → 저장소(쿼리·user 스코프 강제).
- **원본 ↔ AI 생성물 분리:** memories/assets(원본) ↔ entities/differences/diaries(파생). 근거 추적 가능.
