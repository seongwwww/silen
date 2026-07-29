# PROJECT STATE — 실은 (silen)

> 로드맵·현재 상태 스냅샷. 진입점·규칙·핸드오프 절차는 `AGENTS.md`, 핵심 원칙은 `CLAUDE.md`.
> 진행 중 기능의 태스크별 상태는 `.superpowers/sdd/progress.md`(있을 때).

## 제품 한 줄

"실은 아무것도 아니지 않았다." — 똑같다고 느낀 하루에서 **놓친 작은 차이**를 찾아 담담하게 보여주는 모바일 우선 PWA 일기 앱. (한국어 서비스)

핵심 불변 원칙: **차이 탐지는 통계·규칙(detector)이, 서술은 LLM이.** LLM은 검증된 차이만 문장화하고 추측하지 않는다. 죄책감 유도(스트릭 등)·과잉해석 금지.

## 현재 단계

**핵심 질문:** *"사용자가 **3일** 안에 단 한 번이라도 «이건 내가 놓쳤던 진짜 변화다»라고 느끼는가?"*

Phase 0~6의 제품 코드와 화면은 `feat/mvp-shell`에 구현됐다. 사용자는
하단 내비게이션으로 기록·발견·일기·회고·설정에 도달하고, 놀라움·기록 부재·
감정축 탐지, 주간 리포트, 키워드 회고, 내보내기·전체 삭제 요청을 사용할 수 있다.

감정축 자연키와 삭제 요청 RPC 마이그레이션은 로컬 적용했고 비파괴 통합과
실제 로컬 DB·Storage 삭제 테스트도 통과했다. 실제 Vertex eval의 수동 검토에서
입력 밖 부재·기능/효과 해석 두 건을 찾아 결정적 가드레일로 보강했다. 마지막
실제 Vertex 6/6과 수동 검토까지 통과해 **Phase 0~6 MVP 구현 계획을 완료했다.**
자동 운영·배포는 별도 베타 게이트다. 현재 베타 게이트 P1 자동 일기는
`feat/schedule`에서 구현·검증을 마쳤고 사람의 `main` 병합을 기다린다.

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
| — | 파이프라인 CLI 5명령(run-pending·daily·diary·weekly·stats) |

### 보상 계단 (2026-07-28 v2 검토안)

기존 설계는 **7일 동안 사용자에게 줄 것이 없었다.** 차이를 주인공으로 두면
baseline이 쌓이기 전엔 화면이 비는데, 일기 앱 이탈은 대부분 3일 안에 일어난다.
**주인공을 일기로 바꿨다.**

| 시점 | 보상 | 무엇 |
|---|---|---|
| **Day 0** | **일기** | 흩어 쓴 메모를 한 편으로 묶어준다 — 매일의 보상 |
| **Day 3부터** | 첫 발견 | **기록에서 뜸해진 것·오랜만** — 놓치기 쉬운 변화 |
| **Day 7** | 주간 리포트 | 반복·빈도 — 모아야 보이는 것 |

**검증 질문은 7일이 아니라 3일이다:** *3일 안에 "어, 이건 몰랐네"가 한 번 나오는가?*

### 마스터 계획 — Phase 0~6 구현 완료

**계획:** `docs/superpowers/plans/2026-07-28-mvp-full-build.md`
**설계:** `docs/superpowers/specs/2026-07-28-mvp-full-design.md`

**현재 상태:** Phase -1은 `main` 병합 완료. `feat/mvp-shell`에서 Phase 0~6
코드와 프런트 목데이터(`/demo`, `/report?demo=1`)까지 구현·커밋했다. 로컬
마이그레이션·비파괴 통합·파괴 삭제·실제 LLM eval 검증을 모두 완료했다.

| Phase | 내용 | 와이어프레임 |
|---|---|---|
| **-1 완료** | 통합 테스트 격리 — 전역 사용자/메일 삭제·큐 purge 제거, 사용자별 claim·cleanup | — |
| **0 구현 완료** | 언어(`lang="ko"`)·베이지 토큰 · **하단 탭바** | — |
| **1 구현 완료** | 기록을 `/record`로 분리 · **홈을 발견 화면으로** · Daily Wrap · 수동 일기 · `/demo` | #1 #2 |
| **2 완료** | **탐지 재설계** — 놀라움(bits) · **기록 부재** · **감정축** · 랭킹·상한·기각학습 | #4 |
| **3 완료** | 일기 **opt-out 전환** · 기본 프리셋·1회 톤 주문 | #3 |
| **4 완료** | **주간 리포트** | #5 |
| **5 완료** | **회고 — 키워드 검색** | #6 |
| **6 완료** | 내보내기 · 전체 삭제 · `stats` · 보안 리뷰·파괴 테스트·실 LLM eval | #7 |

### 베타 게이트 — P1~P6

**계획:** `docs/superpowers/plans/2026-07-29-beta-gate.md`

| Phase | 상태 | 내용 |
|---|---|---|
| **P1** | `main` 병합 완료 | 사용자 로컬 시각 설정 · 멱등 자동 일기 예약 · 홈 예약 문구 |
| **P2** | `main` 병합 완료 | 일반명사·시간대어 불용어 · 기존 엔티티 탐지 제외 |
| **P3** | `main` 병합 완료 (`9230f0b`) | 메모 임베딩 · 근거 기반 회고 RAG |
| **P4** | `main` 병합 완료 (`b6e7440`) | 사진 업로드 · 실패/취소 시 기록 보존 |
| **P4 보강** | 커밋 완료, 병합 대기 (`db0f92a`) | Storage RLS·경로·만료·잠긴 사진 근거 실증 |
| **P5** | 커밋 완료, 병합 대기 (`83c27bb`) | 기억 잠금 UI · 탐지/검색/일기 실제 제외 · 회고 사진 |
| **P6** | 커밋 완료, 병합 대기 (`c16148d`) | 요약 슬롯 선택·미리보기·1080px PNG 다운로드 |

기존 마스터 계획의 **최소 마이그레이션 2건**에, 사용자 추가 요청인 수동 첫 일기
생성을 위해 `diary_generation_requests` + security-definer RPC 마이그레이션
1건이 먼저 추가됐다. 원래 2건은 감정 차이(`entity_id is null`)의 멱등 부분 인덱스와,
service role을 앱에 두지 않고 삭제 요청을 만드는 security-definer RPC가 필요하다.
기존 초안의 "마이그레이션 0건" 판단은 실제 unique/RLS 제약과 충돌해 수정했다.

### 뺀 것과 이유

| 뺀 것 | 이유 |
|---|---|
| 음성·위치 입력 · 걸음/방문장소 토글 | 완성된 수집 경로가 없다. 버튼만 두면 **거짓 약속** |
| 시간축(*"40분 일찍 퇴근"*) | `captured_at`만으론 "퇴근"이라는 사건을 모른다 |
| 공유 카드 | 베타 게이트 P6에서 구현 완료, `feat/share-card` 병합 대기 |
| PWA · 계정 연결 · 야간 스케줄러/잡 상태 | 화면 뒤의 별도 베타 운영 게이트 |

### 성공 지표 — 잴 수 있는 것만 (`stats` 명령)

**명시적 긍정 비율**(`confirmed/(confirmed+dismissed)`, 표본 20건 전 참고만) ·
하루 노출 차이 수(1~3) · 일기 확정률 · 3일·7일 도달자 수.
opt-out에서는 이 비율이 노출 대비 정확도가 아님을 명시한다. 재방문율·알림
해제율은 측정 수단이 생길 때 추가한다.

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
