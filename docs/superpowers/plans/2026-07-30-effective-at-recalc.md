# Codex 지시서 — 과거 기록 유입 시 재계산 배선

설계: `docs/superpowers/specs/2026-07-29-effective-at-design.md` (**채택**, 이게 이긴다)
기반: `3fdfea2`에서 `effective_at` 생성 열과 미래 시각 차단까지 끝냈다.

**남은 것은 "과거 기록이 들어오면 무엇을 다시 계산하는가"다.**
이 배선이 없으면 `effective_at`은 절반만 맞는다 — 날짜는 제자리를 찾지만,
이미 만들어진 그날의 차이·일기·리포트는 옛 계산 그대로 남는다.

---

## 시작 전

1. **`AGENTS.md`의 "로컬 실행"** — env와 워커를 **같은 터미널**에서. 안 지키면
   추출이 조용히 실패하고 잡이 보관돼 복구되지 않는다.
2. `HANDOFF.md` — 환경 지뢰 목록
3. 위 설계 문서. **계획과 설계가 어긋나면 설계가 이긴다.**
4. `CLAUDE.md` + `.claude/rules/*.md`

## 브랜치

`main`에서 `feat/effective-at-recalc`. **커밋까지만. push·merge 금지.**

---

# T1 — 과거 기록 유입 감지

메모 잡을 처리한 뒤(`worker/src/silen_worker/tasks/process.py`) 그 메모의
**로컬 `effective` 날짜 `D`** 를 구한다.

| D | 할 일 |
|---|---|
| 오늘 | 아무것도 더 하지 않는다. sweep이 이미 다룬다 |
| **과거** | **T2 재계산**을 돌린다 |
| 미래 | 있을 수 없다(API가 막는다). 로그만 남기고 넘어간다 |

- `tasks/`가 `tasks/`를 부르는 것은 이미 있는 형태다(일기 분기가 `write_diary`를 쓴다)
- 재계산이 실패해도 **메모 잡 자체는 성공 처리**한다. 추출·임베딩은 이미 끝났고,
  여기서 큐로 되돌리면 같은 메모를 무한히 다시 추출한다

# T2 — 재계산 범위 (설계 §과거 기록이 들어오면)

`D` 하루와 그 주까지만이다. **그 뒤 날짜는 건드리지 않는다.**

1. **`detect_day(D, closing=True)`** — 그날은 이미 끝났으니 부재·감정 포함
2. 새로 생긴 차이를 **서술**한다
3. **일기** — `D`의 일기가 있으면 **본문을 바꾸지 않는다.**
   `regenerate_requested_at`을 세우고 아래 T3의 사유를 남긴다
4. **주간 리포트** — `D`가 속한 **완료된 블록**을 다시 계산한다.
   `generate_weekly_report`가 이미 있는 리포트를 건너뛰는지 확인하고,
   **덮어쓰는 경로가 없으면 만들어라**(하이라이트까지 결정적으로 재생성)

## 하지 마라

- **`D` 다음 날들을 재탐지하지 마라.** 감정 baseline이 달라지지만 다시 계산하지
  않는다 — 사용자가 이미 [맞아요]를 누른 카드가 말없이 사라지는 것이 더 나쁘다.
  이건 설계에서 명시적으로 정한 것이다
- 일기 본문을 자동으로 바꾸지 마라(원본↔생성물 분리, 자동 재생성 금지)

# T3 — "늦게 추가된 기록이 있어요"

지금은 재생성 요청이 왜 생겼는지 구분할 수 없다. 사용자가 누른 것과 과거 기록
유입은 **화면에서 다르게 보여야** 한다.

**마이그레이션 1건 허용**(up/down 같은 커밋):

```sql
alter table public.diaries
  add column regenerate_reason text
    check (regenerate_reason in ('user','late_record'));
```

- 사용자가 화면에서 요청 → `'user'`
- 과거 기록 유입 → `'late_record'`, 화면에 **"늦게 추가된 기록이 있어요"**
- 요청이 소비되면 함께 비운다

**그 밖의 스키마 변경이 필요해 보이면 멈추고 보고해라.**

# T4 — 경계 테스트

설계 §테스트를 그대로 구현한다. **세 계층 전부에 넣어라.**

**API (`app/api/memories/`)**
- `occurredAt`을 과거로 주면 그 **날짜에** 기록된다(오늘이 아니라)
- 미래는 **400**. **+5분 이내는 통과**

**워커 통합**
- 과거 기록 유입 → **그날만** 재탐지된다
- 그날 일기에 `regenerate_reason='late_record'`가 선다
- 그 주 리포트가 다시 계산된다
- **다음 날들의 차이는 그대로다**(사용자 판단 보존) ← 이걸 꼭 넣어라

**타임존·자정**
- 서울 자정 **직전/직후**가 서로 다른 날로 간다
- 타임존이 다른 두 사용자에게 같은 UTC 순간이 다른 날짜다
- `effective_at`이 `occurred_at`을 따르고, 없으면 `captured_at`을 따른다

**통합 테스트는 자기가 만든 사용자만 정리해라**(전역 삭제 금지, `testing.md`).
**유료 API를 부르지 마라** — 스텁을 주입해라(`StubEmbedder` 선례).

---

# 공통

## 절차

```
실패 테스트 → 최소 구현 → 리팩터 → 검사 → 커밋
```

**회귀 테스트는 수정을 되돌렸을 때 실패하는지까지 확인해라.** 이 저장소에서
SQL 문법 오류·폴링 중단·`occurred_at` 무시가 전부 **단위 테스트를 통과하면서**
숨어 있었다.

## 검사

```powershell
npm run check
npm run build      # ★ Supabase select 타입 오류는 이것만 잡는다
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration"
npm run test:integration
worker\.venv\Scripts\python.exe -m pytest worker -m integration
```

**단위만 돌리고 넘어가지 마라.** 타입을 바꾸면 통합 테스트가 따라오지 않는다.

## 실 데이터 확인

env를 **같은 터미널에** 두고:

```powershell
worker\.venv\Scripts\python.exe -m silen_worker run
```

과거 날짜 `occurredAt`으로 기록을 하나 넣고, **그날 차이가 생기고 그날 일기에
늦은 기록 표시가 뜨는지**, **다음 날 차이는 그대로인지** 눈으로 확인해라.

## 금지

- push·merge 금지. 사용자 소유 미추적 파일(`.claude/orchestration/`,
  `docs/overview/`)을 건드리지 마라
- eval · 임베딩 백필 · 전체 삭제 API 실행 금지
- **계층 예외 목록(`eslint.config.mjs`)을 늘리지 마라.** 6개에서 멈춰 있다 —
  경계가 저장소를 알아야 하면 `*Server.ts`·`*Client.ts` facade를 만들어라
- 모드 플래그 금지. 진행률·스트릭 금지

## 보고

1. **안 된 것과 의심스러운 것을 먼저**
2. 계획과 실제가 어디서 달랐는지
3. **실 데이터로 본 것** — 어떤 화면에서 무엇이 보였는지
4. 사람이 할 일(병합·마이그레이션 적용)

## 막히면

**추측하지 말고 멈추고 보고해라.** 특히 주간 리포트 재계산 경로가 없을 때,
스키마가 더 필요해 보일 때, 기존 테스트가 예상과 다르게 깨질 때.
