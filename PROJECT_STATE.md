# PROJECT STATE — 실은 (silen)

> 로드맵·현재 상태 스냅샷. 진입점·규칙·핸드오프 절차는 `AGENTS.md`, 핵심 원칙은 `CLAUDE.md`.
> 진행 중 기능의 태스크별 상태는 `.superpowers/sdd/progress.md`(있을 때).

## 제품 한 줄

"실은 아무것도 아니지 않았다." — 똑같다고 느낀 하루에서 **놓친 작은 차이**를 찾아 담담하게 보여주는 모바일 우선 PWA 일기 앱. (한국어 서비스)

핵심 불변 원칙: **차이 탐지는 통계·규칙(detector)이, 서술은 LLM이.** LLM은 검증된 차이만 문장화하고 추측하지 않는다. 죄책감 유도(스트릭 등)·과잉해석 금지.

## 현재 단계

MVP 백엔드 파이프라인 구축 중. 기록(memory) → 큐 → 워커 처리 → **엔티티 추출** → **detector(통계 차이 검출: first_occurrence·freq_shift)**까지 완성돼 main에 병합됨(최신 PR #7). 이제 `differences(candidate)`가 쌓인다. 다음은 그 차이를 **LLM으로 담백하게 서술**(근거 연결)해 일기·차이 카드를 만드는 단계. detector의 **스케줄 트리거**(일 배치 구동)는 아직 배선 안 됨(호출 가능한 `detect_day` 함수만 존재). LLM 서술·일기·프론트는 아직 없음.

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
| 8 | 차이 서술(LLM, 근거 연결) · 일기 생성 | 🔧 다음 착수 | — |
| 9 | 프론트엔드 UI(기록·차이 카드·일기·상태 5종) | ⬜ 미착수 | — |
| — | detector 스케줄 트리거(일 배치 구동) | ⬜ 유예(범위 밖) | — |

## 지금 브랜치

- `main` (병합 지점 `53e5209`, PR #7 merge). 엔티티 추출 + detector까지 완료.
- 다음: 차이 서술(#8)을 새 기능 브랜치(`feat/…`)로 분기해 착수. 표준 루프(`AGENTS.md`의 워크플로: 브레인스토밍 → 계획 → 브랜치 → TDD → 리뷰 → PR).

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
