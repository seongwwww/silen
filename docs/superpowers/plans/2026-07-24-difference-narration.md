# 차이 서술(difference narration) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** detector가 만든 `differences(candidate)`를 구조화 사실만으로 담백한 카드 텍스트(headline/body/근거)로 서술해 `difference_narrations`에 멱등 저장한다.

**Architecture:** 워커 3계층. 순수 서비스(프롬프트 조립+가드레일)에 `Narrator` 포트를 주입해 LLM 없이 테스트한다. 실 Gemini 클라이언트와 eval은 마지막에 배치하고 명시적으로 게이트한다. 탐지=통계 경계 유지 — 서술은 검증된 차이의 번역일 뿐.

**Tech Stack:** Python 3.12 · psycopg 3 · Google `google-genai` SDK(Vertex AI Gemini, ADC) · pytest

## Global Constraints

- 산출물은 **코드**다. `main` 직접 커밋 금지 — `feat/difference-narration` 브랜치(생성됨).
- 커밋 메시지 `<type>(<scope>): <한국어 요약>`. scope는 `db`·`worker`·`eval`·`docs`. `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` 트레일러.
- **마이그레이션은 up/down을 같은 커밋에.** down은 `supabase/migrations/down/<타임스탬프>_<이름>.down.sql`.
- 타임스탬프는 `npx supabase migration new <name>` 생성값. 아래 `<ts1>`을 그 값으로 대체.
- 로컬 Supabase 스택 필요. **`db reset` 후 auth 502는 `supabase stop && start`로 복구.**
- 워커는 특권 역할로 psycopg 직접 접속. **모든 쿼리에 user_id 필터/귀속을 코드로 강제.**
- **LLM = Vertex AI Gemini + ADC**(조직 정책이 API 키 금지). env: `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION=global`. 모델 `gemini-3.5-flash`.
- **서술 입력은 구조화 사실만.** 메모 `raw_text`(본문)를 프롬프트·로그·예외에 넣지 않는다.
- **가드레일 통과분만 저장.** 없는 사실·감정·인과·조언 0(ai-evals.md).
- **서술은 사용자에게 읽기 전용.** 쓰기는 워커(service_role/postgres)만. 사용자 위조 금지(deletions 패턴).
- Python venv `worker\.venv`. 명령은 `worker\.venv\Scripts\python.exe` 직접 호출.
- 인증·삭제·본문 외부전송 변경이므로 병합 전 `/security-review`(privacy.md).

## 결정 고정 (Locked Decisions — 냉정한 에이전트용 무-추측 규약)

아래는 구현 중 판단이 갈릴 수 있는 지점을 **전부 못박은** 것이다. 그대로 따른다. 여기서 벗어나면 리뷰에서 반려한다.

1. **마이그레이션 타임스탬프(`<ts1>`)** — `npx supabase migration new difference_narration`이 만든 파일명의 14자리 숫자(예: `20260724NNNNNN`). up 파일은 그 값 그대로, down 파일은 `supabase/migrations/down/<그-값>_difference_narration.down.sql`로 **동일 타임스탬프**를 쓴다. 임의 숫자를 지어내지 않는다.
2. **엔티티 이름 출처** — 서술에 쓰는 이름은 `entities.name`(원문 형태)이다. `normalized_name`(병합 키)이 **아니다**. 가드레일 엔티티명 정합도 `entities.name` 기준.
3. **`differences.description` 형태** — detector가 넣는 값 그대로다. first_occurrence는 `이 <entity_type> 첫 등장`(entity_type은 영문 enum: person/place/activity/thing), freq_shift는 `최근 N일 연속 등장` 또는 `G일 만에 재등장(최근 28일 내)`. eval 픽스처의 description은 이 실제 형식과 일치시킨다. LLM은 그래도 한국어로 서술한다.
4. **길이 상한 단위** — `len(str)`(파이썬 유니코드 코드포인트 수). 한글 1자 = 1. `HEADLINE_MAX=40`·`BODY_MAX=200`·`EVIDENCE_MAX=120`. 초과 시 폐기.
5. **가드레일 매칭 방식** — 엔티티명 정합·블록리스트 모두 **부분 문자열(substring) 검사**다(정규식·토큰화 아님). 한국어라 대소문자 이슈 없음. 엔티티명은 `headline + " " + body`에서 찾는다(evidence_text 제외). 블록리스트는 세 필드 전체(`headline body evidence`)에서 찾는다.
6. **`confidence`는 서술에서 쓰지 않는다** — detector의 confidence는 서술 입력·출력 어디에도 넣지 않는다(의미필터가 생길 때 쓸 값). 프롬프트에 포함하지 않는다.
7. **재서술 시 `created_at`** — `on conflict do update`는 `created_at`을 건드리지 않으므로 **최초 서술 시각으로 유지**된다(마지막 아님). 의도된 동작. `updated_at` 컬럼은 두지 않는다(YAGNI).
8. **LLM 오류 전파** — `narrate_difference`는 `narrator.narrate()`의 예외를 **삼키지 않고 그대로 올린다**(추출 gemini와 동일). 재시도/스킵은 미래 트리거의 몫. `None` 반환은 오직 (a) 대상 difference 없음 (b) 가드레일 탈락 두 경우뿐.
9. **서술 대상 선별** — `fetch_difference_for_narration`은 `entity_id is not null AND evidence_state='intact'`만 반환한다. 그 외(zscore/pattern처럼 entity_id 없는 미래 차이, stale 차이)는 `None` → 서술 안 함. user_id 파라미터는 없다(difference_id는 전역 유일 UUID, 반환된 user_id로 저장을 귀속).
10. **모델 문자열 저장** — `difference_narrations.model`에는 `narrator.model` 값을 그대로 넣는다(프로덕션은 `gemini-3.5-flash` 또는 `GEMINI_MODEL` env, 스텁은 `"stub"`).
11. **톤** — 담백 고정. 프롬프트에 톤 파라미터·프리셋을 넣지 않는다.
12. **eval 측정 기준** — 조언/인과/응원·엔티티명 정합·빈필드는 **모델 raw 출력**에서 검사한다(guardrail 이전). guardrail 통과 여부는 정상 케이스 저장 가능성 확인용으로만 부가 검사.
13. **테스트 마커** — 실 DB가 필요한 테스트에는 `@pytest.mark.integration`을 붙인다. 단위(가드레일·프롬프트)는 마커 없음. `-m "not integration"`으로 DB·키 없이 돈다.
14. **커밋 트레일러** — 모든 커밋에 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. 커밋·푸시·병합은 **사람이 요청할 때만**(AI 임의 금지, CLAUDE.md 안전 가드).

## File Structure

| 경로 | 책임 |
|------|------|
| `supabase/migrations/<ts1>_difference_narration.sql` | difference_narrations 테이블 + RLS + grant |
| `supabase/migrations/down/<ts1>_difference_narration.down.sql` | 테이블 드롭 |
| `worker/src/silen_worker/narration/__init__.py` | 패키지 |
| `worker/src/silen_worker/narration/constants.py` | 길이 상한·금지 표현 블록리스트 |
| `worker/src/silen_worker/narration/service.py` | NarrationInput·Narration·Narrator 포트·build_prompt·guardrail(순수) |
| `worker/src/silen_worker/narration/gemini.py` | Vertex Gemini `Narrator` 구현(ADC) |
| `worker/src/silen_worker/db.py`(수정) | fetch_difference_for_narration·upsert_narration |
| `worker/src/silen_worker/tasks/narrate.py` | narrate_difference 경계 |
| `worker/tests/test_narration.py` | 가드레일·프롬프트 단위(LLM 없음) |
| `worker/tests/test_narration_integration.py` | 스텁 Narrator로 저장·멱등·귀속·삭제연쇄 |
| `worker/tests/test_narration_schema_integration.py` | 테이블 제약·RLS·grant·cascade |
| `evals/narration/fixtures.json`, `evals/narration/run.py` | 골든셋 + 러너(키 필요) |

---

## Task 1: 스키마 — difference_narrations 테이블

**Files:**
- Create: `supabase/migrations/<ts1>_difference_narration.sql`, `supabase/migrations/down/<ts1>_difference_narration.down.sql`
- Create: `worker/tests/test_narration_schema_integration.py`

**Interfaces:**
- Consumes: 기존 `differences`·`users`
- Produces: `public.difference_narrations` (id, user_id, difference_id UNIQUE, headline, body, evidence_text, model, created_at)

- [ ] **Step 1: 마이그레이션 생성**

```powershell
npx supabase migration new difference_narration
```

- [ ] **Step 2: up 스크립트 작성**

`supabase/migrations/<ts1>_difference_narration.sql`:

```sql
-- 서술은 AI 생성물이다. 탐지(differences, 통계)와 행으로 분리해
-- detector 변경과 프롬프트 변경을 섞지 않는다(git.md). difference당 1건.
create table public.difference_narrations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  -- 하나의 차이당 서술 하나. 재서술은 명시적 upsert만.
  difference_id uuid not null unique references public.differences(id) on delete cascade,
  headline text not null,
  body text not null,
  evidence_text text not null,
  model text not null,
  created_at timestamptz not null default now()
);
create index difference_narrations_user_idx on public.difference_narrations (user_id);

alter table public.difference_narrations enable row level security;
create policy "본인 데이터만" on public.difference_narrations
  for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

-- 신규 테이블이라 과거 일괄 grant에 안 잡힌다. 여기서 명시한다.
-- 서술은 사용자에게 읽기 전용 — 쓰기는 워커(service_role/postgres)만.
-- 사용자가 서술 텍스트를 위조하면 'AI 생성물'의 진실성이 무너진다(deletions 패턴).
revoke all on public.difference_narrations from anon;
grant select on public.difference_narrations to authenticated;
grant all on public.difference_narrations to service_role;
```

Step 1이 만든 실제 타임스탬프로 파일명을 확인한다.

- [ ] **Step 3: down 스크립트 작성**

`supabase/migrations/down/<ts1>_difference_narration.down.sql`:

```sql
-- 테이블을 드롭하면 정책·인덱스·grant가 함께 사라진다.
drop table if exists public.difference_narrations;
```

- [ ] **Step 4: 통합 테스트 작성**

`worker/tests/test_narration_schema_integration.py`:

```python
import pytest

from tests.conftest import seed_user, seed_memory, delete_user


def _mk_difference(conn, user_id, memory_id):
    """엔티티 차이 하나를 만들어 그 id를 돌려준다. narration의 FK 대상."""
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', '김밥', '김밥') returning id::text",
        (user_id,),
    ).fetchone()[0]
    diff = conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description,
           detection_method, confidence, category, status, evidence_state)
        values (%s, current_date, %s, 'thing', '최근 3일 연속 등장',
                'freq_shift', 0.5, '오늘의다른점', 'candidate', 'intact')
        returning id::text
        """,
        (user_id, ent),
    ).fetchone()[0]
    return diff


@pytest.mark.integration
def test_서술을_저장하고_읽는다(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "김밥 먹음")
        diff = _mk_difference(conn, user, mem)
        conn.execute(
            "insert into public.difference_narrations "
            "(user_id, difference_id, headline, body, evidence_text, model) "
            "values (%s, %s, '3일째 김밥', '김밥을 최근 3일 연속으로 남기셨네요.', "
            "'요즘 자주 등장해서 찾았어요.', 'gemini-3.5-flash')",
            (user, diff),
        )
        row = conn.execute(
            "select headline from public.difference_narrations where difference_id = %s",
            (diff,),
        ).fetchone()
        assert row[0] == "3일째 김밥"
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_difference당_서술은_하나다(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "김밥 먹음")
        diff = _mk_difference(conn, user, mem)
        conn.execute(
            "insert into public.difference_narrations "
            "(user_id, difference_id, headline, body, evidence_text, model) "
            "values (%s, %s, 'a', 'b', 'c', 'm')",
            (user, diff),
        )
        with pytest.raises(psycopg_errors_UniqueViolation()):
            conn.execute(
                "insert into public.difference_narrations "
                "(user_id, difference_id, headline, body, evidence_text, model) "
                "values (%s, %s, 'a2', 'b2', 'c2', 'm')",
                (user, diff),
            )
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_difference_삭제시_서술도_사라진다(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "김밥 먹음")
        diff = _mk_difference(conn, user, mem)
        conn.execute(
            "insert into public.difference_narrations "
            "(user_id, difference_id, headline, body, evidence_text, model) "
            "values (%s, %s, 'a', 'b', 'c', 'm')",
            (user, diff),
        )
        conn.execute("delete from public.differences where id = %s", (diff,))
        left = conn.execute(
            "select 1 from public.difference_narrations where difference_id = %s", (diff,)
        ).fetchone()
        assert left is None
    finally:
        delete_user(conn, user)


def psycopg_errors_UniqueViolation():
    from psycopg import errors
    return errors.UniqueViolation
```

- [ ] **Step 5: 적용·실행**

```powershell
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_narration_schema_integration.py -m integration -v
```

Expected: 3건 PASS.

- [ ] **Step 6: 커밋**

```powershell
git add supabase/migrations worker/tests/test_narration_schema_integration.py
git commit -m "feat(db): difference_narrations 테이블 — 서술 저장

차이당 서술 1건(difference_id unique). 탐지↔서술을 행으로 분리한다.
difference 삭제 시 cascade. 사용자에겐 읽기 전용(쓰기는 워커),
RLS 본인 데이터만. up/down 동봉.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: 서술 서비스 — 프롬프트 조립·가드레일 (LLM 없음)

순수 로직을 먼저 만든다. LLM은 포트로 주입한다.

**Files:**
- Create: `worker/src/silen_worker/narration/__init__.py`, `constants.py`, `service.py`
- Create: `worker/tests/test_narration.py`

**Interfaces:**
- Consumes: 없음(순수)
- Produces:
  ```python
  @dataclass(frozen=True)
  class NarrationInput:
      difference_id: str; user_id: str; entity_name: str; entity_type: str
      detection_method: str; description: str; date_iso: str
  @dataclass(frozen=True)
  class Narration:
      headline: str; body: str; evidence_text: str
  class Narrator(Protocol):
      model: str
      def narrate(self, facts: NarrationInput) -> dict: ...   # {"headline","body","evidence_text"} 원시
  def build_prompt(facts: NarrationInput) -> str
  def guardrail(raw: dict, facts: NarrationInput) -> Narration | None
  ```

- [ ] **Step 1: 실패 테스트 작성**

`worker/tests/test_narration.py`:

```python
from silen_worker.narration.service import NarrationInput, build_prompt, guardrail


def _facts(**kw):
    base = dict(
        difference_id="d1", user_id="u1", entity_name="김밥", entity_type="thing",
        detection_method="freq_shift", description="최근 3일 연속 등장", date_iso="2026-07-24",
    )
    base.update(kw)
    return NarrationInput(**base)


def _raw(headline="3일째 김밥", body="김밥을 최근 3일 연속으로 남기셨네요.",
         evidence_text="요즘 자주 등장해서 찾았어요."):
    return {"headline": headline, "body": body, "evidence_text": evidence_text}


def test_정상_출력은_통과한다():
    out = guardrail(_raw(), _facts())
    assert out is not None
    assert out.headline == "3일째 김밥"


def test_엔티티명_없는_출력은_폐기한다():
    # headline+body 어디에도 '김밥'이 없으면 그 차이를 가리키지 않는다.
    out = guardrail(_raw(headline="오늘의 반복", body="비슷한 게 이어졌어요."), _facts())
    assert out is None


def test_조언_표현은_폐기한다():
    out = guardrail(_raw(body="김밥을 자주 드시네요. 내일은 다른 걸 해보세요."), _facts())
    assert out is None


def test_인과_창작은_폐기한다():
    out = guardrail(_raw(body="김밥을 3일 연속 먹은 건 바빴기 때문에 그런 거예요."), _facts())
    assert out is None


def test_빈_필드는_폐기한다():
    out = guardrail(_raw(evidence_text="  "), _facts())
    assert out is None


def test_길이_초과는_폐기한다():
    out = guardrail(_raw(headline="김밥" * 30), _facts())
    assert out is None


def test_프롬프트에_본문은_없고_사실은_있다():
    p = build_prompt(_facts())
    assert "김밥" in p
    assert "최근 3일 연속 등장" in p
    assert "2026-07-24" in p
```

- [ ] **Step 2: 실패 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_narration.py -v
```

Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 구현 작성**

`worker/src/silen_worker/narration/__init__.py`:

```python
"""차이 서술 — 검증된 차이를 담백한 카드로 옮긴다(LLM=번역자). 탐지는 detector의 몫."""
```

`worker/src/silen_worker/narration/constants.py`:

```python
"""서술 가드레일 상수 한곳. 골든 eval로 검증·튜닝한다(ai-evals.md)."""

HEADLINE_MAX = 40
BODY_MAX = 200
EVIDENCE_MAX = 120

# 조언·응원·인과 표현. 통계에 없는 해석·자기계발·응원·인과를 차단한다.
# 관찰체("~네요/~인 듯해요")는 걸리지 않는다. eval로 오탐/누락을 조정한다.
FORBIDDEN_PHRASES = (
    "때문에", "덕분에", "해보세요", "해보는 건", "어때요", "어떨까요",
    "화이팅", "파이팅", "응원", "추천", "하세요", "해야",
)
```

`worker/src/silen_worker/narration/service.py`:

```python
"""서술 오케스트레이션·프롬프트 조립·가드레일. LLM은 Narrator 포트로 주입한다.
프레임워크·DB·Gemini를 모른다(순수 로직) — 여기 테스트를 집중한다.
입력은 구조화 사실만(메모 본문 없음). 출력은 가드레일 통과분만.
"""

from dataclasses import dataclass
from typing import Protocol

from silen_worker.narration.constants import (
    BODY_MAX,
    EVIDENCE_MAX,
    FORBIDDEN_PHRASES,
    HEADLINE_MAX,
)


@dataclass(frozen=True)
class NarrationInput:
    difference_id: str
    user_id: str
    entity_name: str
    entity_type: str
    detection_method: str
    description: str
    date_iso: str


@dataclass(frozen=True)
class Narration:
    headline: str
    body: str
    evidence_text: str


class Narrator(Protocol):
    model: str

    def narrate(self, facts: NarrationInput) -> dict:
        """{"headline","body","evidence_text"} 원시 출력. 가드레일 전."""
        ...


_METHOD_LABEL = {
    "first_occurrence": "처음 등장",
    "freq_shift": "반복/빈도 변화",
}


def build_prompt(facts: NarrationInput) -> str:
    """구조화 사실만으로 프롬프트를 조립한다. 메모 본문은 넣지 않는다."""
    return (
        "너는 일기 앱 '실은'의 서술 담당이다. 통계 엔진이 이미 검증한 '다른 점' 하나를\n"
        "사람이 읽을 담백한 한국어 카드로 옮겨라. 너는 번역자이지 발견자가 아니다.\n"
        "규칙: 아래 사실에 없는 사건·인물·감정·인과를 만들지 마라. 조언·응원·교훈 금지.\n"
        "단정하지 말고 관찰체로. 없는 감정을 지어내지 마라. 반드시 엔티티 이름을 넣어라.\n\n"
        f"엔티티: {facts.entity_name} ({facts.entity_type})\n"
        f"차이 유형: {_METHOD_LABEL.get(facts.detection_method, facts.detection_method)}\n"
        f"통계 근거: {facts.description}\n"
        f"날짜: {facts.date_iso}\n\n"
        "출력(JSON): headline(12자 내외), body(1~2문장, 사실만), "
        "evidence_text(왜 찾았는지 한 줄, 통계 용어 순화)."
    )


def guardrail(raw: dict, facts: NarrationInput) -> Narration | None:
    """결정적 방어선. 통과 못 하면 None(저장 안 함).
    ① 세 필드 비어있지 않음 ② 길이 상한 ③ 엔티티명 정합(headline+body에 실재)
    ④ 조언·응원·인과 블록리스트 미포함."""
    if not isinstance(raw, dict):
        return None
    headline = (raw.get("headline") or "").strip()
    body = (raw.get("body") or "").strip()
    evidence = (raw.get("evidence_text") or "").strip()
    if not headline or not body or not evidence:
        return None
    if len(headline) > HEADLINE_MAX or len(body) > BODY_MAX or len(evidence) > EVIDENCE_MAX:
        return None
    if facts.entity_name not in f"{headline} {body}":
        return None
    blob = f"{headline} {body} {evidence}"
    if any(p in blob for p in FORBIDDEN_PHRASES):
        return None
    return Narration(headline=headline, body=body, evidence_text=evidence)
```

- [ ] **Step 4: 통과 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_narration.py -v
worker\.venv\Scripts\python.exe -m ruff check worker
```

Expected: 7건 PASS, ruff 통과.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/narration worker/tests/test_narration.py
git commit -m "feat(worker): 서술 가드레일·프롬프트 조립 (LLM 없음)

구조화 사실만으로 프롬프트를 만든다(본문 미포함). 가드레일은 엔티티명
정합·조언/인과 블록리스트·길이·빈필드를 결정적으로 검사해 통과분만 남긴다.
Narrator 포트로 주입해 순수 로직을 Gemini 없이 테스트한다.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: 저장소·파이프라인 배선 (스텁 Narrator)

**Files:**
- Modify: `worker/src/silen_worker/db.py`
- Create: `worker/src/silen_worker/tasks/narrate.py`, `worker/tests/test_narration_integration.py`

**Interfaces:**
- Consumes: Task 1 스키마, Task 2 서비스
- Produces:
  ```python
  # db.py
  @dataclass
  class DifferenceFacts:
      difference_id: str; user_id: str; entity_id: str; entity_name: str
      entity_type: str; detection_method: str; description: str; date_iso: str
  def fetch_difference_for_narration(conn, difference_id: str) -> DifferenceFacts | None
  def upsert_narration(conn, user_id, difference_id, headline, body, evidence_text, model) -> str
  # tasks/narrate.py
  def narrate_difference(conn, difference_id: str, narrator: Narrator | None = None) -> str | None
  ```

- [ ] **Step 1: 저장소 함수 추가**

`worker/src/silen_worker/db.py` 끝에 추가:

```python
@dataclass
class DifferenceFacts:
    difference_id: str
    user_id: str
    entity_id: str
    entity_name: str
    entity_type: str
    detection_method: str
    description: str
    date_iso: str


def fetch_difference_for_narration(
    conn: psycopg.Connection, difference_id: str
) -> DifferenceFacts | None:
    """서술 재료를 엔티티 조인으로 읽는다. 엔티티 차이(entity_id 있음)이고
    근거가 살아있는(intact) 것만 대상. 저장은 여기서 읽은 user_id로 귀속한다."""
    row = conn.execute(
        """
        select d.id::text, d.user_id::text, d.entity_id::text,
               e.name, e.entity_type, d.detection_method,
               coalesce(d.description, ''), d.date::text
        from public.differences d
        join public.entities e on e.id = d.entity_id
        where d.id = %s
          and d.entity_id is not null
          and d.evidence_state = 'intact'
        """,
        (difference_id,),
    ).fetchone()
    if row is None:
        return None
    return DifferenceFacts(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])


def upsert_narration(
    conn: psycopg.Connection,
    user_id: str,
    difference_id: str,
    headline: str,
    body: str,
    evidence_text: str,
    model: str,
) -> str:
    """difference_id 자연키로 멱등 upsert. 재서술은 덮어쓴다."""
    row = conn.execute(
        """
        insert into public.difference_narrations
          (user_id, difference_id, headline, body, evidence_text, model)
        values (%s, %s, %s, %s, %s, %s)
        on conflict (difference_id) do update
          set headline = excluded.headline,
              body = excluded.body,
              evidence_text = excluded.evidence_text,
              model = excluded.model
        returning id::text
        """,
        (user_id, difference_id, headline, body, evidence_text, model),
    ).fetchone()
    return row[0]
```

- [ ] **Step 2: narrate_difference 경계 작성**

`worker/src/silen_worker/tasks/narrate.py`:

```python
"""차이 서술 경계. 차이 하나를 읽어 서술하고 가드레일을 통과하면 저장한다.
스케줄/lazy 트리거 배선은 범위 밖 — 호출 가능한 함수. 탐지=통계, 서술=번역.
"""

import psycopg

from silen_worker.db import fetch_difference_for_narration, upsert_narration
from silen_worker.narration.service import Narrator, NarrationInput, guardrail


def narrate_difference(
    conn: psycopg.Connection, difference_id: str, narrator: Narrator | None = None
) -> str | None:
    """서술 성공 시 narration id, 대상 없음/가드레일 탈락 시 None."""
    if narrator is None:
        from silen_worker.narration.gemini import GeminiNarrator

        narrator = GeminiNarrator()

    facts_row = fetch_difference_for_narration(conn, difference_id)
    if facts_row is None:
        return None

    facts = NarrationInput(
        difference_id=facts_row.difference_id,
        user_id=facts_row.user_id,
        entity_name=facts_row.entity_name,
        entity_type=facts_row.entity_type,
        detection_method=facts_row.detection_method,
        description=facts_row.description,
        date_iso=facts_row.date_iso,
    )
    raw = narrator.narrate(facts)
    narration = guardrail(raw, facts)
    if narration is None:
        return None
    return upsert_narration(
        conn,
        facts.user_id,
        facts.difference_id,
        narration.headline,
        narration.body,
        narration.evidence_text,
        narrator.model,
    )
```

- [ ] **Step 3: 스텁 통합 테스트 작성**

`worker/tests/test_narration_integration.py`:

```python
import pytest

from silen_worker.tasks.narrate import narrate_difference
from tests.conftest import seed_user, seed_memory, delete_user


class StubNarrator:
    """고정 출력을 내는 스텁. 실 Gemini 없이 파이프라인을 검증한다."""

    model = "stub"

    def __init__(self, raw):
        self._raw = raw

    def narrate(self, facts):
        return self._raw


def _seed_difference(conn, user_id, name="김밥"):
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', %s, %s) returning id::text",
        (user_id, name, name),
    ).fetchone()[0]
    diff = conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description,
           detection_method, confidence, category, status, evidence_state)
        values (%s, current_date, %s, 'thing', '최근 3일 연속 등장',
                'freq_shift', 0.5, '오늘의다른점', 'candidate', 'intact')
        returning id::text
        """,
        (user_id, ent),
    ).fetchone()[0]
    return diff


_GOOD = {
    "headline": "3일째 김밥",
    "body": "김밥을 최근 3일 연속으로 남기셨네요.",
    "evidence_text": "요즘 자주 등장해서 찾았어요.",
}


def _narration_row(conn, diff):
    return conn.execute(
        "select user_id::text, headline from public.difference_narrations "
        "where difference_id = %s",
        (diff,),
    ).fetchone()


@pytest.mark.integration
def test_서술이_저장되고_소유자에_귀속된다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "김밥 먹음")
        diff = _seed_difference(conn, user)
        nid = narrate_difference(conn, diff, narrator=StubNarrator(_GOOD))
        assert nid is not None
        row = _narration_row(conn, diff)
        assert row[0] == user           # user 스코프 귀속
        assert row[1] == "3일째 김밥"
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_재서술은_중복을_만들지_않는다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "김밥 먹음")
        diff = _seed_difference(conn, user)
        narrate_difference(conn, diff, narrator=StubNarrator(_GOOD))
        narrate_difference(conn, diff, narrator=StubNarrator(_GOOD))
        count = conn.execute(
            "select count(*)::int from public.difference_narrations where difference_id = %s",
            (diff,),
        ).fetchone()[0]
        assert count == 1
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_가드레일_탈락은_저장되지_않는다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "김밥 먹음")
        diff = _seed_difference(conn, user)
        bad = {"headline": "오늘의 반복", "body": "내일은 다른 걸 해보세요.",
               "evidence_text": "자주 나와서요."}  # 엔티티명 없음 + 조언
        nid = narrate_difference(conn, diff, narrator=StubNarrator(bad))
        assert nid is None
        assert _narration_row(conn, diff) is None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_없는_difference는_None(conn):
    import uuid

    user = seed_user(conn)
    try:
        nid = narrate_difference(conn, str(uuid.uuid4()), narrator=StubNarrator(_GOOD))
        assert nid is None
    finally:
        delete_user(conn, user)
```

- [ ] **Step 4: 실행**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -m integration -v
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration"
worker\.venv\Scripts\python.exe -m ruff check worker
```

Expected: 통합(스키마 3 + 서술 4 + 기존 detector/추출)·단위 전부 PASS, ruff 통과.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/db.py worker/src/silen_worker/tasks/narrate.py worker/tests/test_narration_integration.py
git commit -m "feat(worker): 서술 파이프라인 배선 (스텁 Narrator)

fetch_difference_for_narration(엔티티 조인·intact만)·upsert_narration(멱등).
narrate_difference가 차이를 읽어 서술·가드레일·저장한다. 스텁으로 저장·귀속·
멱등·가드레일 탈락 미저장을 검증. 실 Gemini는 주입만 바꾸면 된다.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Vertex AI Gemini Narrator (ADC)

**⚠️ 전제:** ADC 발급·Vertex 활성(추출 기능에서 구성 완료). env 3종은 실행 시 셋업.

**Files:**
- Create: `worker/src/silen_worker/narration/gemini.py`

**Interfaces:**
- Consumes: Task 2 `Narrator` 포트·`build_prompt`·`NarrationInput`
- Produces: `GeminiNarrator`(인자 없는 생성자, `model` 속성, `narrate(facts) -> dict`)

- [ ] **Step 1: GeminiNarrator 작성**

`worker/src/silen_worker/narration/gemini.py`:

```python
"""Vertex AI Gemini 서술기. ADC로 인증(비밀 키 없음, 조직 정책이 API 키 금지).
입력은 구조화 사실만(build_prompt) — 메모 본문을 전송하지 않는다. Vertex는
데이터를 학습에 쓰지 않는다(추출 기능 Task 4에서 확인).

env: GOOGLE_GENAI_USE_VERTEXAI=true, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION=global.
모델 gemini-3.5-flash(asia-east2엔 없어 location=global).
"""

import json
import os

from google import genai
from google.genai import types

from silen_worker.narration.service import NarrationInput, build_prompt

_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

_RESPONSE_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "headline": types.Schema(type="STRING"),
        "body": types.Schema(type="STRING"),
        "evidence_text": types.Schema(type="STRING"),
    },
    required=["headline", "body", "evidence_text"],
)


class GeminiNarrator:
    """Narrator 포트 구현. narrate()는 원시 출력만 반환하고 가드레일 검증은
    호출자(narrate_difference→service.guardrail) 책임이다."""

    model = _MODEL

    def __init__(self) -> None:
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            raise RuntimeError("GOOGLE_CLOUD_PROJECT 미설정 — Vertex ADC 구성 필요")
        self._client = genai.Client()

    def narrate(self, facts: NarrationInput) -> dict:
        # 구조화 출력 강제 + "번역자" 프롬프트. 실패 시 예외를 올려 호출자가
        # 재시도/스킵을 결정하게 한다. 본문은 애초에 프롬프트에 없다.
        resp = self._client.models.generate_content(
            model=_MODEL,
            contents=build_prompt(facts),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
            ),
        )
        return json.loads(resp.text)
```

- [ ] **Step 2: 실 Vertex 스모크**

```powershell
$env:GOOGLE_GENAI_USE_VERTEXAI = "true"
$env:GOOGLE_CLOUD_PROJECT = "project-58561b19-fb35-4c01-bb2"
$env:GOOGLE_CLOUD_LOCATION = "global"
worker\.venv\Scripts\python.exe -c "from silen_worker.narration.gemini import GeminiNarrator; from silen_worker.narration.service import NarrationInput; f=NarrationInput('d','u','김밥','thing','freq_shift','최근 3일 연속 등장','2026-07-24'); print(GeminiNarrator().narrate(f))"
```

Expected: `{'headline': ..., 'body': ...(김밥 포함), 'evidence_text': ...}` JSON. 육안으로 조언·인과·감정 창작이 없는지 확인.

- [ ] **Step 3: 커밋**

```powershell
git add worker/src/silen_worker/narration/gemini.py
git commit -m "feat(worker): Vertex AI Gemini 서술기 (ADC)

구조화 사실만 담은 프롬프트로 headline/body/근거를 구조화 출력으로 받는다.
ADC 인증(비밀 키 없음), 본문 미전송. 가드레일은 호출자가 적용.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**단위 테스트 참고:** Vertex 호출은 네트워크·비용이 있어 CI 단위 테스트에서 실행하지 않는다. 순수 로직(가드레일·프롬프트)은 Task 2에서 스텁으로 검증됨. 이 태스크 검증은 Step 2 스모크와 Task 5 eval이다.

---

## Task 5: eval 골든셋 (키 필요)

**⚠️ 전제:** Task 4와 동일. 실 Gemini 호출이 필요하다.

**Files:**
- Create: `evals/narration/fixtures.json`, `evals/narration/run.py`

**Interfaces:**
- Consumes: Task 4 `GeminiNarrator`, Task 2 `NarrationInput`·`build_prompt`·`guardrail`·`FORBIDDEN_PHRASES`
- Produces: eval 러너(CI 게이트)

- [ ] **Step 1: 골든셋 픽스처 작성**

`evals/narration/fixtures.json` — ai-evals.md 필수 케이스. 합성 사실(실사용자 데이터 아님).

```json
{
  "cases": [
    {"name": "freq-streak", "entity_name": "김밥", "entity_type": "thing",
     "detection_method": "freq_shift", "description": "최근 3일 연속 등장",
     "date_iso": "2026-07-24", "must_include_entity": true,
     "reason": "반복을 담백하게, 조언·인과 없이"},
    {"name": "first-place", "entity_name": "그 카페", "entity_type": "place",
     "detection_method": "first_occurrence", "description": "이 place 첫 등장",
     "date_iso": "2026-07-24", "must_include_entity": true,
     "reason": "처음을 사실로만"},
    {"name": "reemergence", "entity_name": "지은", "entity_type": "person",
     "detection_method": "freq_shift", "description": "9일 만에 재등장(최근 28일 내)",
     "date_iso": "2026-07-24", "must_include_entity": true,
     "reason": "재등장을 감정 승격 없이"}
  ]
}
```

- [ ] **Step 2: 러너 작성**

`evals/narration/run.py`:

```python
"""차이 서술 골든셋 러너 (ai-evals.md: 환각·감정 승격·조언 혼입·근거 정합·단정 금지).

실 Gemini 원시 출력(raw)과 guardrail 통과분(kept)을 모두 검사한다. eval의 목적은
모델/프롬프트 회귀를 잡는 것 — guardrail은 사후에 걸러주므로 kept만 보면 항상
통과라 모델을 못 잰다. 그래서 조언/인과·엔티티명 정합은 raw에서 검사한다.

CI 게이트: 케이스 하나라도 실패하면 종료 코드 1.

실행 (실 Vertex, 비용 발생):
    $env:GOOGLE_GENAI_USE_VERTEXAI = "true"
    $env:GOOGLE_CLOUD_PROJECT = "..."
    $env:GOOGLE_CLOUD_LOCATION = "global"
    worker\\.venv\\Scripts\\python.exe evals/narration/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from silen_worker.narration.constants import FORBIDDEN_PHRASES
from silen_worker.narration.gemini import GeminiNarrator
from silen_worker.narration.service import NarrationInput, guardrail

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

FIXTURES_PATH = Path(__file__).parent / "fixtures.json"


def _facts(case: dict) -> NarrationInput:
    return NarrationInput(
        difference_id="eval", user_id="eval",
        entity_name=case["entity_name"], entity_type=case["entity_type"],
        detection_method=case["detection_method"], description=case["description"],
        date_iso=case["date_iso"],
    )


def run_case(case: dict, narrator: GeminiNarrator) -> tuple[bool, list[str]]:
    facts = _facts(case)
    raw = narrator.narrate(facts)
    failures: list[str] = []

    headline = (raw.get("headline") or "").strip()
    body = (raw.get("body") or "").strip()
    evidence = (raw.get("evidence_text") or "").strip()
    blob = f"{headline} {body} {evidence}"

    # 조언·인과·응원(모델 원시 출력 기준 — guardrail 사후 제거와 무관하게 모델을 잰다).
    hit = [p for p in FORBIDDEN_PHRASES if p in blob]
    if hit:
        failures.append(f"조언/인과/응원 표현 혼입: {hit}")

    # 엔티티명 정합.
    if case.get("must_include_entity") and case["entity_name"] not in f"{headline} {body}":
        failures.append(f"엔티티명 누락: '{case['entity_name']}'")

    # 빈 필드.
    if not headline or not body or not evidence:
        failures.append("빈 필드")

    # guardrail이 실제로 통과시키는지(정상 케이스는 저장 가능해야 한다).
    if not failures and guardrail(raw, facts) is None:
        failures.append("정상 출력인데 guardrail 탈락(길이 등 확인)")

    return (not failures, failures)


def main() -> int:
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    narrator = GeminiNarrator()

    n_pass = 0
    print("=== 차이 서술 골든셋 결과 ===")
    for case in fixtures["cases"]:
        passed, failures = run_case(case, narrator)
        n_pass += 1 if passed else 0
        print(f"[{'PASS' if passed else 'FAIL'}] {case['name']}")
        for f in failures:
            print(f"    - {f}")

    total = len(fixtures["cases"])
    print(f"\n케이스: {n_pass}/{total} 통과")
    if n_pass < total:
        print("결과: FAIL — 게이트 실패, 종료 코드 1")
        return 1
    print("결과: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 실행 (ADC 필요)**

```powershell
$env:GOOGLE_GENAI_USE_VERTEXAI = "true"
$env:GOOGLE_CLOUD_PROJECT = "project-58561b19-fb35-4c01-bb2"
$env:GOOGLE_CLOUD_LOCATION = "global"
worker\.venv\Scripts\python.exe evals/narration/run.py
```

Expected: 3/3 통과. 조언·인과 혼입 시 프롬프트 보강 후 재실행(회귀 게이트).

- [ ] **Step 4: 커밋**

```powershell
git add evals/narration
git commit -m "feat(eval): 차이 서술 골든셋

반복·처음·재등장을 실 Gemini로 검증. 조언/인과/응원 혼입 0, 엔티티명 정합,
빈 필드 0을 모델 원시 출력 기준으로 게이트한다(ai-evals.md). 픽스처는 합성.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: 문서·보안 리뷰·브랜치 마무리

**Files:**
- Modify: `supabase/README.md`, `README.md`

- [ ] **Step 1: supabase/README에 서술 메모**

`supabase/README.md`의 "엔티티" 절 아래에 추가:

```markdown
## 차이 서술(narration)

- 워커가 `differences`(candidate)를 담백한 카드 텍스트로 서술해
  `difference_narrations`(difference당 1건, unique)에 저장한다.
- 입력은 구조화 사실만(엔티티명·통계 근거). **메모 본문은 전송하지 않는다.**
- 가드레일이 엔티티명 정합·조언/인과 블록리스트·길이를 검사해 통과분만 저장.
- 서술은 사용자에게 **읽기 전용**(쓰기는 워커). difference 삭제 시 cascade.
```

- [ ] **Step 2: README에 eval 명령 추가**

`README.md`의 검사 절에 추가:

```powershell
# 차이 서술 eval — 실 Vertex Gemini 호출(비용), ADC + env 3종 필요
worker\.venv\Scripts\python.exe evals/narration/run.py
```

그리고 저장소 구조 절 `evals/entities/` 아래에 한 줄:

```
evals/narration/        # 차이 서술 골든셋 (조언·인과·감정승격 방지)
```

- [ ] **Step 3: 전체 검사**

```powershell
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
```

Expected: ruff·pytest(키 없이 도는 단위+스텁 통합) 통과.

- [ ] **Step 4: 커밋**

```powershell
git add supabase/README.md README.md
git commit -m "docs: 차이 서술 안내와 eval 명령

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 5: 보안 리뷰**

인증·삭제·본문 외부전송 변경이므로 `/security-review`(privacy.md). 중점:
- 서술 저장이 difference 소유자에 귀속되는가(교차 사용자 오염 없음).
- 서술 테이블 RLS·grant(사용자 읽기 전용, 위조 불가).
- 프롬프트·로그·예외에 메모 본문이 새지 않는가(입력에 본문 없음 재확인).
- difference 삭제 시 narration cascade(삭제 완전성).

- [ ] **Step 6: 브랜치 마무리**

`/superpowers:finishing-a-development-branch`. rebase 후 `merge --no-ff`, squash 금지. 병합·푸시는 사람이.

---

## 완료 기준
- difference_narrations 테이블(difference당 unique) + RLS(읽기 전용) + cascade.
- 가드레일이 엔티티명·조언/인과·길이·빈필드를 결정적으로 검사, 통과분만 저장.
- 스텁 파이프라인: 저장·소유자 귀속·멱등·가드레일 탈락 미저장 통합 통과.
- (키 있을 때) Gemini가 조언·인과 없이 카드 서술, eval 골든셋 통과.
- 단위 테스트는 DB·키 없이 통과. `ruff`·`pytest`·`supabase db reset` 통과.

## 이번 범위 밖
- 의미 필터(수치 노이즈용 — z-score 생길 때).
- 일기 생성(#8b) · 톤 3층 · 서술 스케줄/lazy 트리거 배선 · 프론트 카드 UI(#9).
