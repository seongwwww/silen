# PROJECT STATE — 실은 (silen)

> 로드맵·현재 상태 스냅샷. 진입점·규칙·핸드오프 절차는 `AGENTS.md`, 핵심 원칙은 `CLAUDE.md`.
> 진행 중 기능의 태스크별 상태는 `.superpowers/sdd/progress.md`(있을 때).

## 제품 한 줄

"실은 아무것도 아니지 않았다." — 똑같다고 느낀 하루에서 **놓친 작은 차이**를 찾아 담담하게 보여주는 모바일 우선 PWA 일기 앱. (한국어 서비스)

핵심 불변 원칙: **차이 탐지는 통계·규칙(detector)이, 서술은 LLM이.** LLM은 검증된 차이만 문장화하고 추측하지 않는다. 죄책감 유도(스트릭 등)·과잉해석 금지.

## 현재 단계

**핵심 질문:** *"사용자가 7일 안에 단 한 번이라도 «이건 내가 놓쳤던 진짜 변화다»라고 느끼는가?"*

기반과 파이프라인은 돌아간다. **그런데 사용자가 그 결과에 도달할 길이 없다** — 하단 내비게이션이 없어 `/review`·`/diary`·`/settings`를 발견할 수 없고, "자동 일기"는 사람이 CLI를 쳐야 한다.

**지금부터는 "돌아가게" 만드는 것만 한다.** 보안·인프라·테스트 격리는 뒤로 미룬다.

## 로드맵 — 핵심 루프부터

### 최소 검증 루프 (이것만 되면 제품이다)

```
5초 기록  →  차이 1개 발견  →  확인  →  자동 일기  →  7일 리포트
```

### 완료

| 기획서 | 기능 |
|--------|------|
| W1 | 데이터모델 · 익명 인증 · 텍스트 기록 + 감정 · eval 뼈대 |
| W2 | 엔티티 추출 · 차이 탐지(first_occurrence · freq_shift) · 탐지↔서술 분리 |
| W3 | 일기 생성 · 오늘의 다른 점 · 오늘의 한 문장 |
| W4 | 차이 확인 UI · 일기 보기·날짜 이동 · **일기 편집·확정·톤·다시 만들기** |
| — | 파이프라인 CLI 3명령 |

### 남은 것 — 이 순서로 간다

| # | 기능 | 왜 지금 |
|---|------|---------|
| **N1** | **하단 내비게이션 + 발견 중심 홈** | 화면을 다 만들어놨는데 **갈 길이 없다.** 와이어프레임의 홈은 "오늘의 다른 점"이 먼저인데 구현은 입력창만 있다 |
| **N2** | **야간 자동 실행 + 처리 상태** | "밤에 자동으로 일기를 만들어 준다"가 **수동 CLI**다. 스케줄 등록 + 처리중/실패/빈날 상태 표시 |
| **N3** | **7일 리포트** | 첫 보상. "당신이 몰랐던 이번 주" = aha moment |
| **N4** | **차이 품질 — 의미 필터** | 하루 몇 개까지 보여줄지, 무엇을 숨길지. 지금은 처음 등장한 모든 명사가 올라온다 |
| **N5** | **확인·기각 학습** | "아니에요"가 다음 탐지에 반영되게. 이 제품의 장기 경쟁력 |
| **N6** | 탐지 축 확장 (시간·감정 중 하나) | 지금은 엔티티 축뿐. `baselines`·`signals`는 비어 있다 |
| **N7** | 기록 목록 · 계정 연결 화면 | |
| **N8** | 7일 온보딩 · 공유 카드 | |
| **N9** | 회고 검색 · RAG | |
| **N10** | 사진 · 음성 · 걸음 센서 | |
| **N11** | 프라이버시 UI(잠금·삭제·내보내기) · PWA | |

### 미루는 것 (기능 아님)

통합 테스트 격리 · 워커 CLI UTF-8 · 추출 일반명사 억제 · z-score · 디자인 시스템 정비 · 보안 리뷰.
스펙·계획 문서는 `docs/superpowers/`에 남아 있다.

### 아직 정하지 않은 제품 결정

N4·N5에서 답해야 한다 — 지금 답하지 않는다.
- 하루에 차이를 최대 몇 개 보여줄까
- 처음 등장한 모든 명사가 의미 있나
- 기록 1~3일차(기준선 없음)엔 무엇을 보여줄까
- "아니에요"가 다음 탐지에 어떻게 반영되나

## 진행 방식

기능 하나 = 스펙 → 계획 → 브랜치 → TDD → PR. **구조·인프라 논의로 새지 않는다.**

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
