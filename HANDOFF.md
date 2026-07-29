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
| **P4** | **사진 첨부 + 근거 썸네일** | 🟡 **`feat/photo`에 커밋됨, 미병합** |
| P5 | 기억 잠금 UI | ⬜ 미착수 |
| P6 | 공유 카드 | ⬜ 미착수 |

**임베딩 결정:** `docs/decisions/ADR-0004-embeddings.md`
모델 `gemini-embedding-001` · **768차원**(기본 3072은 HNSW 상한 2000 초과) · cosine · HNSW.

### `feat/photo` (커밋 2개, 검사 전부 통과)

- `fb56781` **사진 첨부** — 형식·8MB 검증은 **고를 때**, 업로드는 **저장할 때 1회**
  (중간에 그만두면 고아 파일이 남으므로). 실패해도 쓴 글·고른 사진을 지우지 않는다.
  경로에 원본 파일명을 쓰지 않는다.
- `5e96be5` **근거 썸네일** — 서명 URL 10분. **사진만 있는 기록도 근거에 포함**
  (`raw_text`가 비었다고 걸러내던 것을 고침).

**검사:** 프론트 195 · lint · typecheck · 프로덕션 빌드 통과.
**브라우저 확인:** 업로드 → `storage.objects` + `assets` 행, 경로 `{user_id}/{uuid}.{ext}`.

**아직 안 된 것:** `/recall` 근거 카드에는 썸네일이 없다(일기 근거만). `main` 병합 미실행.

---

## 다음 작업자에게

**할 일:** ①P4 더블체크 → ②P5 → ③P6.
**지시서:** `docs/superpowers/plans/2026-07-29-codex-p4-p6.md`

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
