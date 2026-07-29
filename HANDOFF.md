# HANDOFF — 활성 작업 인수인계 허브 (모든 AI 공용)

> 여러 AI(Claude · Codex · Gemini · Cursor)가 번갈아 작업하는 저장소의 **단일 인수인계 파일**이다.
> `AGENTS.md`(진입점·규칙)를 먼저 읽고, **"지금 무엇을 어떻게 할지"는 이 파일**을 본다.
> 역할 구분: `AGENTS.md`=변하지 않는 규칙 · `PROJECT_STATE.md`=전체 로드맵 · **`HANDOFF.md`=현재 작업+실행법+상태(매번 갱신)**.
> **작업을 멈추거나 세션 한도(≈80%)에 닿으면 아래 "상태"를 갱신하고 커밋한다.**

---

## 현재 상태 (2026-07-29)

**계획:** `docs/superpowers/plans/2026-07-29-beta-gate.md`

| Phase | 내용 | 상태 |
|---|---|---|
| P1 | 스케줄링 — `diary_hour` · `run-scheduled` | ✅ `main` |
| P2 | 탐지 품질 — 일반명사 억제 | ✅ `main` |
| P3 | 회고 벡터 RAG 채팅 · `run-pending --watch` | ✅ `main` (`9230f0b`) |
| P4 | 사진 첨부 + 근거 썸네일 + 경로 검증 | ✅ `main` (`e2b4f7c`) |
| P4+ | 사진 경로·만료·잠금 근거 보강 | ✅ 커밋, 병합 대기 (`fix/photo-hardening` · `db0f92a`) |
| P5 | 기억 잠금 UI | ✅ `main` (`535832f`) |
| P6 | 공유 카드 | ✅ `main` (`c2c2e10`) |

**임베딩 결정:** `docs/decisions/ADR-0004-embeddings.md`
모델 `gemini-embedding-001` · **768차원**(기본 3072은 HNSW 상한 2000 초과) · cosine · HNSW.

### 이번 Codex 작업에서 끝낸 것

- **P4 더블체크:** 실제 Storage RLS로 본인 UUID 경로 업로드·타 사용자 경로
  업로드/다운로드 차단·서명 URL 만료를 검증했다. 잠긴 사진 근거도 일기에서
  빠지는 통합 회귀를 추가했다. 만료 사진은 깨진 이미지 대신 새로고침 안내를 보인다.
- **P5:** `PATCH /api/memories/[id]`가 기대 잠금값과 RLS로 원자 갱신한다.
  일기·회고 근거 카드에서 잠금/즉시 해제하며, 성공 응답 전에는 잠긴 척하지 않는다.
  회고 사진 경로는 워커 후보에서 오되 서버가 10분 서명 URL로 바꾸고 내부 경로를
  제거한다. 잠금 시 `memory_embeddings.is_searchable=false`, 해제 시 복귀,
  `run-daily` 입력·회고 검색 복귀를 실제 Postgres 통합으로 검증했다.
- **P6:** 주간 리포트 요약 슬롯만 항목별 제외해 미리보고, 브라우저 메모리에서
  1080×1080 PNG로 다운로드한다. 서버 업로드·공개 링크·원문·식별 정보는 없다.
  리포트가 없으면 버튼도 없다.

**검사:** 세 브랜치 모두 `check`·프로덕션 빌드·ruff·worker 단위·프런트 통합·
비파괴 worker 통합 통과. P6 최종은 프런트 201 단위 + 61 통합, worker
163 단위 + 101 비파괴 통합.

**브라우저 확인:** 375px에서 일기·회고 잠금→본문/사진 가림→해제 복원과 DB 상태를
확인했다. 회고 실제 서명 썸네일도 보였다. `/report?demo=1`에서 항목 제외 후
`C:\Users\s2608\Downloads\silen-week-2026-07-21.png`를 실제 저장했고
1080×1080 PNG임을 열어 확인했다. 미리보기 세 항목·브랜드·저장 버튼이 탭바에
가리지 않는다.

---

## 다음 작업자에게

**사람이 할 일:** 아래 순서로 `main`에 `merge --no-ff` 한다(squash 금지).

1. `fix/photo-hardening` (`db0f92a`)
2. `feat/memory-lock` (`83c27bb`)
3. `feat/share-card` (`c16148d`)

세 브랜치는 push하지 않았다. `merge-tree` 사전 확인에서는 P4+P5 충돌 표식이
없었지만, 둘 다 사진 근거 컴포넌트를 개선하므로 병합 후 전체 검사를 다시 돌린다.

**의심/이월:**
- 앱이 완전히 종료된 정확한 순간이 Storage 업로드 뒤·DB 저장 전이면 고아 객체가
  남을 수 있다. 현재 구조에서 저장 버튼을 누르기 전에는 업로드하지 않아 창을 좁혔다.
- 잠긴 기억은 새 조회에서 의도적으로 사라진다. 기록 목록이 없는 현재 UI에서는
  잠근 직후 같은 카드에서는 해제할 수 있지만, 새 세션의 잠긴 기억 관리 화면은 없다.
- 전체 worker `-m integration`은 사람 전용 `destructive` 테스트까지 포함한다.
  P4에서 그대로 실행했을 때 삭제 전 `storage_credentials_missing`으로 실패했다.
  자격증명을 억지로 넣거나 삭제를 재시도하지 않았고,
  `-m "integration and not destructive"`는 모두 통과했다.

---

## 환경 (Windows) — 이미 밟은 지뢰, 반복하지 마라

1. **`npx`가 PowerShell 실행 정책에 막힌다. `npx.cmd`를 써라.**
   `Set-ExecutionPolicy`를 실행하지 마라(시스템 보안 설정).
2. **Supabase `select()` 인자는 리터럴이어야 한다**(상수면 `as const`).
   문자열 결합은 타입 추론을 깨고 **`npm run build`에서만** 드러난다.
3. `db reset` 뒤 auth 502 → `npx.cmd supabase stop; npx.cmd supabase start`.
4. **회고를 쓰려면 `run-pending --watch`를 띄워 둬라.** 안 띄우면 화면이
   계속 "찾고 있어요"에 머문다 — 고장이 아니다.
5. **파이썬 3.11 호환**: f-string 안 백슬래시는 3.12+ 문법이다(ruff가 잡는다).
6. **`supabase.ts`는 최상단에서 `next/headers`를 임포트한다.** 클라이언트
   컴포넌트에서 임포트하면 빌드가 깨진다 — 저장소가 자기 브라우저 클라이언트를 만든다.
7. **`ILIKE ANY(배열)`에 `ESCAPE` 절을 붙일 수 없다**(연산자 형식). 기본
   이스케이프가 이미 백슬래시다.

## 검사

```powershell
npm run check      # lint + typecheck + unit
npm run build      # ★ 반드시
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration"
npm run test:integration
worker\.venv\Scripts\python.exe -m pytest worker -m integration
```

**eval · 임베딩 백필 · 전체 삭제 API를 실행하지 마라**(실 비용/파괴). 사람이 한다.
Storage 자격증명이 필요한 파괴 삭제 통합 테스트 1건도 사람이 실행한다.

## 실행

```powershell
npm run dev                                                          # localhost:3000
worker\.venv\Scripts\python.exe -m silen_worker run-pending --watch   # 회고용
```

Vertex ADC env 3종: `GOOGLE_GENAI_USE_VERTEXAI=true` ·
`GOOGLE_CLOUD_PROJECT=project-58561b19-fb35-4c01-bb2` · `GOOGLE_CLOUD_LOCATION=global`

## 어기면 안 되는 것

- **커밋까지만. push·merge 금지.** 사람이 지시할 때만.
- 사용자 소유 미추적 파일을 건드리지 마라: `.claude/orchestration/`, `docs/overview/`
- **모드 플래그 금지** — 컴포넌트는 `demo?: boolean` 같은 사용처 분기를 갖지 않는다.
  동작을 주입받고, 데이터 출처는 경계(page)가 고른다(`app/report/page.tsx` 선례).
- **계층 예외 목록(`eslint.config.mjs`)을 늘리지 마라.** 6개에서 멈춰 있다.
  경계가 저장소를 알아야 하면 `*Server.ts`·`*Client.ts` 서비스 facade를 만든다.
- **보이는 글자 = 접근성 이름**(WCAG 2.5.3). 터치 타깃 44px.
- 서술·회고에 내부 용어(`일기`·`활성일`·`valence`) 금지 — 가드레일이 막는다.
- 진행률·스트릭·죄책감 유도 금지.
- **통합 테스트는 유료 API를 부르지 않는다.** 스텁을 주입해라(`StubEmbedder` 선례).
