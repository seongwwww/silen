# PROJECT STATE — 실은 (silen)

> 로드맵·현재 상태 스냅샷. 진입점·규칙·핸드오프 절차는 `AGENTS.md`, 핵심 원칙은 `CLAUDE.md`.
> 진행 중 기능의 태스크별 상태는 `.superpowers/sdd/progress.md`(있을 때).

## 제품 한 줄

"실은 아무것도 아니지 않았다." — 똑같다고 느낀 하루에서 **놓친 작은 차이**를 찾아 담담하게 보여주는 모바일 우선 PWA 일기 앱. (한국어 서비스)

핵심 불변 원칙: **차이 탐지는 통계·규칙(detector)이, 서술은 LLM이.** LLM은 검증된 차이만 문장화하고 추측하지 않는다. 죄책감 유도(스트릭 등)·과잉해석 금지.

## 현재 단계

**기획서 8주 계획 기준 W1 완료 · W2~W4 부분.** MVP 기능 기준 대략 **25~30%**.

기반(2자산 구조·RLS·가드레일·eval 하네스·파이프라인 CLI)은 서 있고 **더 손대지 않는다.**
지금부터는 **기획서 §13 구현 순서대로 기능만 채운다.**

## 로드맵 — 기획서 §13 구현 순서

### 완료

| 기획서 | 기능 | 상태 |
|--------|------|------|
| W1 | 데이터모델(ADR-0002 스키마) · 인증(익명+매직링크·RLS) | ✅ |
| W1 | 텍스트 기록 + 감정 태그 (`POST /api/memories`, 홈 기록 화면) | ✅ |
| W1 | eval 골든셋 뼈대 (추출·서술·일기 3종) | ✅ |
| W2 | 엔티티 추출(Vertex Gemini + 가드레일) | ✅ |
| W2 | 차이 탐지 — `first_occurrence`·`freq_shift` | 🔶 부분 |
| W2 | 탐지→서술 분리 (통계=detector, 서술=LLM) | ✅ |
| W3 | 일기 생성 (메모 + 확정 차이 → 하루 일기) | ✅ |
| W3 | 계층 산출물 — 오늘의 다른 점 · 오늘의 한 문장 | 🔶 부분 |
| W4 | 차이 확인 UI(맞아요/아니에요) · 일기 보기·날짜 이동 | ✅ |
| W4 | 파이프라인 구동 (워커 CLI 3명령) | 🔶 스케줄 등록은 수동 |

### 남은 MVP — 이 순서로 간다

| # | 기능 | 기획서 | 왜 |
|---|------|--------|-----|
| **F1** | **일기 초안 수정·확정** | §6 W4 | 지금 일기가 **읽기 전용**이다. `edited_text`·`status`는 있는데 UI가 없어 "AI 초안 → 내 확정본" 루프가 반쪽이다 |
| **F2** | **다시 만들기 1회** | §6 W4 | 늦은 메모 대응. 자동 재생성은 금지, 명시적 1회만 |
| **F3** | **톤 3층** | §4-8 §6 W3 | `[확정]` 항목. ①기본 프리셋 ②생성 전 주문 ③생성 후 대화형 수정 |
| **F4** | **일기 시간 설정 + 알림 1건** | §6 W4 | `users.diary_time` 있음. 스케줄 등록 + 알림 |
| **F5** | **계층 산출물 확장** | §5 W3 | 별거 아닌 성취(미뤄둔→닫힘) · 감정이 바뀐 순간 |
| **F6** | **7일 온보딩** | §8 W5 | Day0 첫 기록 5초 + 일기시간·톤 설정 / Day1~6 넛지 / Day7 리포트 |
| **F7** | **7일 리포트 + 공유 카드** | §8 W5 | "당신이 몰랐던 이번 주" = aha moment. 카드는 요약만·항목별 제외·미리보기 |
| **F8** | **임베딩 + 회고형 검색** | §9 W6 | pgvector 하이브리드 + 근거 카드 |
| **F9** | **회고 대화** | §9 W6 | 개인 기록 위 RAG. 관찰 제시, 단정 X |
| **F10** | **걸음 센서 + 동의 UI** | §7 W7 | opt-in 기본 OFF. Day 0에 안 물음 |
| **F11** | **사진 첨부 UI** | §7 W7 | API·Storage는 이미 있음 |
| **F12** | **음성 → 텍스트(STT)** | §12 W7 | |
| **F13** | **프라이버시 — 잠금·삭제·내보내기** | §7 W7 | `[확정]`. 삭제는 원본+임베딩+색인 함께 |
| **F14** | **가드레일 튜닝 + eval 회귀 + 베타** | W8 | |

### 미루는 것 (기능 아님)

통합 테스트 격리 · 워커 CLI UTF-8 · 엔티티 추출 일반명사 억제 · z-score(센서 없어 재료 부족) · baselines 테이블 적재.
스펙·계획 문서는 `docs/superpowers/`에 남아 있으니 필요할 때 꺼내 쓴다.

## 진행 방식

기능 하나 = 스펙 → 계획 → 브랜치 → TDD → 리뷰 → PR. `AGENTS.md` 워크플로 그대로.
**구조·인프라 논의로 새지 않는다.** 기존 구조는 돌아가는 대로 둔다.

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
