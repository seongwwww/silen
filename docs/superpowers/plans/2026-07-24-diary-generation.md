# 일기 생성(diary generation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 그날 메모(raw_text)와 confirmed 차이를 담백한 하루 일기로 엮어 `diaries`+`diary_sections`+`diary_sources`에 하루 1건 멱등 저장한다.

**Architecture:** 워커 3계층. 순수 서비스(프롬프트 조립+가드레일)에 `DiaryWriter` 포트를 주입해 LLM 없이 테스트한다. 저장소는 3테이블 멱등 저장(force 시 sections/sources 교체). Gemini와 eval은 마지막에 배치·게이트. 스키마 변경 없음(기존 테이블 재사용).

**Tech Stack:** Python 3.12 · psycopg 3 · Google `google-genai` SDK(Vertex AI Gemini, ADC) · pytest

## Global Constraints

- 산출물은 **코드**다. `main` 직접 커밋 금지 — `feat/diary-generation` 브랜치(생성됨).
- 커밋 메시지 `<type>(<scope>): <한국어 요약>`. scope는 `worker`·`eval`·`docs`. `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` 트레일러. **커밋만, push 금지**(사람이).
- 워커는 특권 역할로 psycopg 직접 접속(RLS 우회). **모든 쿼리에 user_id 필터/귀속을 코드로 강제.**
- **LLM = Vertex AI Gemini + ADC.** env: `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT=project-58561b19-fb35-4c01-bb2`, `GOOGLE_CLOUD_LOCATION=global`. 모델 `gemini-3.5-flash`. ADC·google-genai 이미 구성됨.
- **일기는 메모 본문(raw_text)을 Vertex로 전송한다**(하루 서술이라 불가피, 추출 기능과 동일 수용 흐름). 단 본문·일기 텍스트를 **로그·APM·예외에 남기지 않는다**.
- **하루 1건 멱등·자동 재생성 금지**(backend.md): 기존 diary 있으면 force=False는 no-op. force=True는 `status='draft'`만 덮어쓴다(edited/confirmed 보존). 빈 날(메모 0)은 미생성.
- **가드레일 통과분만 저장**: used_ids ⊆ 입력, 조언·인과 블록리스트, 빈 출력 거부.
- 하루 경계는 사용자 로컬 자정(`time.local_date_for`). 잠금·삭제 메모 제외.
- Python venv `worker\.venv`. 명령은 `worker\.venv\Scripts\python.exe` 직접 호출.
- 인증·삭제·본문 외부전송 변경이므로 병합 전 `/security-review`(privacy.md).
- **스키마 변경 없음** — `diaries`(unique user_id,date)·`diary_sources`(diary_id,memory_id PK)·`diary_sections`(section_type in 오늘의한문장|본문|다른점|성취, difference_id FK set null, content NOT NULL)를 재사용. RLS·grant 이미 존재.

## 결정 고정 (Locked Decisions — 냉정한 에이전트용 무-추측 규약)

1. **엔티티/차이 재료 출처** — confirmed 차이의 라벨은 `difference_narrations.headline`, 없으면 `differences.description`로 폴백(LEFT JOIN + COALESCE). 빈 문자열 가능.
2. **메모 순서·필드** — 메모는 `captured_at` 오름차순(시간순). `DiaryMemory`는 `(memory_id, text)`만(명시적 시각 없음 — 순서로 흐름 전달). `raw_text`가 null이거나 공백인 메모는 제외.
3. **빈 날** — 그날(로컬) 텍스트 있는 메모가 0개면 `generate_diary`는 **None 반환, diary 미생성**. 메모가 있으면 confirmed 차이가 0개여도 일기 생성.
4. **멱등/보호 순서** — `generate_diary`는 (a) 기존 diary 조회 → 있으면 `force=False`거나 `status≠'draft'`면 **기존 diary_id 반환(no-op)**. (b) force=True + draft면 진행. (c) 메모 0 → None. force+draft인데 메모 0이면 **None 반환, 기존 draft 그대로 둔다**(삭제 안 함).
5. **길이 단위** — `len(str)`(유니코드 코드포인트). `ONE_LINE_MAX=60`, `BODY_MAX=2000`. 초과 시 폐기.
6. **근거 정합(가드레일 핵심)** — `set(used_memory_ids) ⊆ 입력 메모 id집합` AND `set(used_difference_ids) ⊆ 입력 confirmed 차이 id집합`. 위반 시 폐기. used_* 는 문자열로 정규화 후 비교.
7. **비어있지 않음** — 입력 메모가 있고 body가 비어있지 않으면 `used_memory_ids`도 비어있지 않아야 한다(아니면 폐기).
8. **블록리스트 재사용** — `from silen_worker.narration.constants import FORBIDDEN_PHRASES`. 조언·응원·인과 금지. `one_line + " " + body`에서 부분문자열 검사(used_* 배열은 검사 대상 아님).
9. **저장 매핑** — `diaries.generated_text=body`, `status='draft'`, `style_profile='{"preset":"담백"}'::jsonb`. `diary_sections`=[오늘의한문장:one_line, 본문:body] + used 차이마다 다른점(difference_id, content=그 차이 headline). `diary_sources`=used_memory_ids.
10. **force 재저장** — force 재생성 시 `diary_sections`·`diary_sources`를 **전부 지우고 다시 쓴다**(delete-then-insert). diaries 행은 upsert(generated_text·status='draft' 갱신).
11. **LLM 오류 전파** — `writer.write()` 예외는 삼키지 않고 전파. `None`은 (빈 날 / 보호된 기존 diary는 diary_id 반환이지 None 아님 / 가드레일 탈락) 경우.
12. **모델 문자열** — style_profile엔 톤만. 모델명은 저장 안 함(diaries에 model 컬럼 없음). `writer.model`은 향후용, 이 기능은 미저장.
13. **감정·시각 미포함** — EMOTIONS 미적재라 감정 입력 없음. 명시적 clock time도 프롬프트에 안 넣음(순서만).
14. **커밋/푸시** — 커밋만, 사람이 push/merge. Co-Authored-By 트레일러.
15. **원자성** — 워커는 autocommit(detector/narration과 동일). `upsert_diary`→`replace_diary_sections`→`replace_diary_sources`는 각각 커밋되어 원자적이지 않다. 중간 실패 시 부분 일기가 남을 수 있으나 기존 diary는 `status='draft'`라 **force=True 재생성으로 복구**된다. MVP는 이 창을 수용한다(명시적 트랜잭션 미도입).
16. **가드레일 탈락 시 기존 draft 보존** — `upsert_diary`는 가드레일 통과 뒤에 호출된다. force+draft인데 새 생성이 가드레일 탈락(또는 메모 0)이면 upsert 전에 `None`을 반환하므로 **기존 draft를 건드리지 않는다**.
17. **편집 보호는 DB 레벨에서 원자적** (보안 리뷰 Important) — `generate_diary`의 이른 status 확인과 `upsert_diary` 사이에 유저가 편집하면 경쟁 조건이 생긴다. 이를 막기 위해 `upsert_diary`의 conflict update에 `where diaries.status='draft'` 조건을 두어 **draft일 때만 원자적으로 덮어쓰고**, 편집된 행이면 미갱신·`None` 반환한다. `generate_diary`는 `None`이면 섹션/출처를 건드리지 않고 기존 diary_id를 반환한다. #15의 autocommit 비원자성 수용은 부분 일기(force 복구 가능)에 한하며, **사용자 편집 소실은 이 규칙으로 차단**한다.

## File Structure

| 경로 | 책임 |
|------|------|
| `worker/src/silen_worker/diary/__init__.py` | 패키지 |
| `worker/src/silen_worker/diary/constants.py` | 길이 상한(블록리스트는 narration에서 재사용) |
| `worker/src/silen_worker/diary/service.py` | DiaryInput·Diary·DiaryWriter 포트·build_prompt·guardrail(순수) |
| `worker/src/silen_worker/diary/gemini.py` | Vertex Gemini `DiaryWriter` 구현(ADC) |
| `worker/src/silen_worker/db.py`(수정) | fetch_diary_memories·fetch_confirmed_differences·fetch_existing_diary·upsert_diary·replace_diary_sections·replace_diary_sources |
| `worker/src/silen_worker/tasks/write_diary.py` | generate_diary 경계 |
| `worker/tests/test_diary.py` | 가드레일·프롬프트 단위(LLM 없음) |
| `worker/tests/test_diary_repo_integration.py` | 저장소 함수 통합(저장·교체·조회) |
| `worker/tests/test_diary_integration.py` | generate_diary 통합(멱등·force·보호·빈날·스코프·cascade) |
| `evals/diary/fixtures.json`, `evals/diary/run.py` | 골든셋 + 러너(키 필요) |

---

## Task 1: 일기 서비스 — 프롬프트 조립·가드레일 (LLM 없음)

**Files:**
- Create: `worker/src/silen_worker/diary/__init__.py`, `constants.py`, `service.py`
- Create: `worker/tests/test_diary.py`

**Interfaces:**
- Consumes: `silen_worker.narration.constants.FORBIDDEN_PHRASES`
- Produces:
  ```python
  @dataclass(frozen=True)
  class DiaryMemory: memory_id: str; text: str
  @dataclass(frozen=True)
  class DiaryDifference: difference_id: str; headline: str
  @dataclass(frozen=True)
  class DiaryInput: date_iso: str; user_id: str; memories: list[DiaryMemory]; differences: list[DiaryDifference]
  @dataclass(frozen=True)
  class Diary: one_line: str; body: str; used_memory_ids: list[str]; used_difference_ids: list[str]
  class DiaryWriter(Protocol):
      model: str
      def write(self, facts: DiaryInput) -> dict: ...
  def build_prompt(facts: DiaryInput) -> str
  def guardrail(raw: dict, facts: DiaryInput) -> Diary | None
  ```

- [ ] **Step 1: 실패 테스트 작성**

`worker/tests/test_diary.py`:

```python
from silen_worker.diary.service import (
    DiaryDifference, DiaryInput, DiaryMemory, build_prompt, guardrail,
)


def _facts(memories=None, differences=None):
    if memories is None:
        memories = [DiaryMemory("m1", "점심 김밥"), DiaryMemory("m2", "오늘 좀 일찍 나옴")]
    if differences is None:
        differences = [DiaryDifference("d1", "평소보다 일찍 퇴근")]
    return DiaryInput("2026-07-24", "u1", memories, differences)


def _raw(one_line="비슷한 하루, 그래도 조금 일찍.",
         body="특별할 것 없는 하루였다. 점심은 김밥. 오늘은 조금 일찍 나왔다.",
         used_memory_ids=None, used_difference_ids=None):
    return {
        "one_line": one_line, "body": body,
        "used_memory_ids": ["m1", "m2"] if used_memory_ids is None else used_memory_ids,
        "used_difference_ids": ["d1"] if used_difference_ids is None else used_difference_ids,
    }


def test_정상_출력은_통과한다():
    out = guardrail(_raw(), _facts())
    assert out is not None
    assert out.one_line.startswith("비슷한")
    assert out.used_memory_ids == ["m1", "m2"]


def test_입력_밖_메모id는_폐기한다():
    out = guardrail(_raw(used_memory_ids=["m1", "m99"]), _facts())
    assert out is None


def test_입력_밖_차이id는_폐기한다():
    out = guardrail(_raw(used_difference_ids=["dX"]), _facts())
    assert out is None


def test_body있는데_근거메모_없으면_폐기():
    out = guardrail(_raw(used_memory_ids=[]), _facts())
    assert out is None


def test_조언_표현은_폐기한다():
    out = guardrail(_raw(body="오늘은 김밥을 먹었다. 내일은 다른 걸 해보세요."), _facts())
    assert out is None


def test_인과_창작은_폐기한다():
    out = guardrail(_raw(body="일찍 나온 건 바빴기 때문에 그런 거다."), _facts())
    assert out is None


def test_빈_출력은_폐기한다():
    out = guardrail(_raw(body="  "), _facts())
    assert out is None


def test_비문자열_출력도_크래시없이_폐기():
    out = guardrail({"one_line": 5, "body": "x", "used_memory_ids": [], "used_difference_ids": []}, _facts())
    assert out is None


def test_차이없는_평범한날도_통과():
    out = guardrail(_raw(used_difference_ids=[]), _facts(differences=[]))
    assert out is not None
    assert out.used_difference_ids == []


def test_프롬프트에_메모본문과_차이가_들어간다():
    p = build_prompt(_facts())
    assert "점심 김밥" in p
    assert "평소보다 일찍 퇴근" in p
    assert "2026-07-24" in p
```

- [ ] **Step 2: 실패 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_diary.py -v
```
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 구현 작성**

`worker/src/silen_worker/diary/__init__.py`:

```python
"""일기 생성 — 그날 메모+확정 차이를 담백한 하루 이야기로 엮는다(LLM=번역자). 탐지는 detector의 몫."""
```

`worker/src/silen_worker/diary/constants.py`:

```python
"""일기 가드레일 상수. 조언·인과 블록리스트는 narration.constants를 재사용한다(동일 제품 규칙)."""

ONE_LINE_MAX = 60
BODY_MAX = 2000
```

`worker/src/silen_worker/diary/service.py`:

```python
"""일기 오케스트레이션·프롬프트 조립·가드레일. LLM은 DiaryWriter 포트로 주입한다.
프레임워크·DB·Gemini를 모른다(순수 로직) — 여기 테스트를 집중한다.
입력은 그날 메모(raw_text)+확정 차이. 출력은 가드레일 통과분만(근거 정합 검증).
"""

from dataclasses import dataclass
from typing import Protocol

from silen_worker.diary.constants import BODY_MAX, ONE_LINE_MAX
from silen_worker.narration.constants import FORBIDDEN_PHRASES


@dataclass(frozen=True)
class DiaryMemory:
    memory_id: str
    text: str


@dataclass(frozen=True)
class DiaryDifference:
    difference_id: str
    headline: str


@dataclass(frozen=True)
class DiaryInput:
    date_iso: str
    user_id: str
    memories: list[DiaryMemory]
    differences: list[DiaryDifference]


@dataclass(frozen=True)
class Diary:
    one_line: str
    body: str
    used_memory_ids: list[str]
    used_difference_ids: list[str]


class DiaryWriter(Protocol):
    model: str

    def write(self, facts: DiaryInput) -> dict:
        """{"one_line","body","used_memory_ids","used_difference_ids"} 원시 출력. 가드레일 전."""
        ...


def build_prompt(facts: DiaryInput) -> str:
    """그날 메모(본문)+확정 차이로 프롬프트를 조립한다. 시간순 메모, 사실만."""
    mem_lines = "\n".join(f"- [{m.memory_id}] {m.text}" for m in facts.memories)
    diff_lines = (
        "\n".join(f"- [{d.difference_id}] {d.headline}" for d in facts.differences)
        or "- (없음)"
    )
    return (
        "너는 일기 앱 '실은'의 서술 담당이다. 아래는 오늘 남긴 메모와, 통계로 검증돼\n"
        "유저가 확인한 '다른 점'이다. 이것들만으로 오늘 하루를 1인칭 담백한 일기로 써라.\n"
        "규칙: 메모에 있는 사실만 쓴다. 없는 장면·대사·사람·감정·인과를 만들지 마라.\n"
        "조언·응원·교훈·자기계발 금지. 평범하면 평범하다고 써도 된다. 감정을 지어내지 마라.\n"
        "메모가 1~2개면 짧게(2~3문장), 3개 이상이면 흐름으로 엮어라.\n"
        "one_line은 60자 이내, body는 2000자 이내로 쓴다.\n\n"
        f"날짜: {facts.date_iso}\n"
        f"메모(시간순):\n{mem_lines}\n\n"
        f"확인된 다른 점:\n{diff_lines}\n\n"
        "출력(JSON): one_line(오늘의 한 문장, 제목처럼), body(일기 본문), "
        "used_memory_ids(실제 근거로 쓴 메모 id 배열), used_difference_ids(쓴 차이 id 배열)."
    )


def guardrail(raw: dict, facts: DiaryInput) -> Diary | None:
    """결정적 방어선. 통과 못 하면 None(저장 안 함).
    ① 두 텍스트 필드 비어있지 않음·길이 상한 ② 근거 정합(used ⊆ 입력)
    ③ body 있는데 근거메모 없음 폐기 ④ 조언·인과 블록리스트."""
    if not isinstance(raw, dict):
        return None
    one_line = str(raw.get("one_line") or "").strip()
    body = str(raw.get("body") or "").strip()
    if not one_line or not body:
        return None
    if len(one_line) > ONE_LINE_MAX or len(body) > BODY_MAX:
        return None

    used_mem = raw.get("used_memory_ids")
    used_diff = raw.get("used_difference_ids")
    if not isinstance(used_mem, list) or not isinstance(used_diff, list):
        return None
    used_mem = [str(x) for x in used_mem]
    used_diff = [str(x) for x in used_diff]

    input_mem_ids = {m.memory_id for m in facts.memories}
    input_diff_ids = {d.difference_id for d in facts.differences}
    if not set(used_mem) <= input_mem_ids:
        return None
    if not set(used_diff) <= input_diff_ids:
        return None
    if facts.memories and not used_mem:
        return None

    blob = f"{one_line} {body}"
    if any(p in blob for p in FORBIDDEN_PHRASES):
        return None

    return Diary(one_line=one_line, body=body, used_memory_ids=used_mem, used_difference_ids=used_diff)
```

- [ ] **Step 4: 통과 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_diary.py -v
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 10건 PASS, ruff 통과.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/diary worker/tests/test_diary.py
git commit -m "feat(worker): 일기 가드레일·프롬프트 조립 (LLM 없음)

그날 메모(본문)+확정 차이로 프롬프트를 만든다. 가드레일은 근거 정합
(used_memory/difference_ids ⊆ 입력)·조언/인과 블록리스트·길이·빈필드를
결정적으로 검사해 통과분만 남긴다. DiaryWriter 포트로 주입해 순수 로직을
Gemini 없이 테스트한다. 블록리스트는 narration.constants 재사용.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: 저장소 함수 (db.py 확장)

**Files:**
- Modify: `worker/src/silen_worker/db.py`
- Create: `worker/tests/test_diary_repo_integration.py`

**Interfaces:**
- Consumes: Task 1 없음(독립). 기존 `time.local_date_for`.
- Produces:
  ```python
  @dataclass
  class DiaryMemoryRow: memory_id: str; captured_at: datetime; timezone: str; raw_text: str
  def fetch_diary_memories(conn, user_id, target_date) -> list[DiaryMemoryRow]
  def fetch_confirmed_differences(conn, user_id, target_date) -> list[tuple[str, str]]  # (difference_id, headline)
  def fetch_existing_diary(conn, user_id, target_date) -> tuple[str, str] | None        # (diary_id, status)
  def upsert_diary(conn, user_id, target_date, generated_text) -> str | None            # diary_id, 편집된 행이면 None
  def replace_diary_sections(conn, diary_id, one_line, body, used_differences) -> None  # used_differences: list[(diff_id, headline)]
  def replace_diary_sources(conn, diary_id, memory_ids) -> None
  ```

- [ ] **Step 1: 저장소 함수 추가**

`worker/src/silen_worker/db.py` 끝에 추가:

```python
@dataclass
class DiaryMemoryRow:
    memory_id: str
    captured_at: datetime
    timezone: str
    raw_text: str


def fetch_diary_memories(
    conn: psycopg.Connection, user_id: str, target_date: date
) -> list[DiaryMemoryRow]:
    """대상 로컬 날짜를 덮는 UTC 창의 활성 메모(본문 있음)를 반환한다. 로컬 날짜
    필터는 호출자가 time.local_date_for로 정밀하게 한다. user_id 강제, 잠금/삭제 제외."""
    lower = datetime.combine(target_date - timedelta(days=1), datetime.min.time(), timezone.utc)
    upper = datetime.combine(target_date + timedelta(days=2), datetime.min.time(), timezone.utc)
    rows = conn.execute(
        """
        select m.id::text, m.captured_at, u.timezone, m.raw_text
        from public.memories m
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and m.raw_text is not null
          and length(btrim(m.raw_text)) > 0
          and m.captured_at >= %s
          and m.captured_at < %s
        order by m.captured_at
        """,
        (user_id, lower, upper),
    ).fetchall()
    return [DiaryMemoryRow(r[0], r[1], r[2], r[3]) for r in rows]


def fetch_confirmed_differences(
    conn: psycopg.Connection, user_id: str, target_date: date
) -> list[tuple[str, str]]:
    """그날 confirmed(intact) 차이 + 서술 headline(없으면 description 폴백). user_id 강제."""
    rows = conn.execute(
        """
        select d.id::text, coalesce(n.headline, d.description, '')
        from public.differences d
        left join public.difference_narrations n on n.difference_id = d.id
        where d.user_id = %s
          and d.date = %s
          and d.status = 'confirmed'
          and d.evidence_state = 'intact'
        order by d.id
        """,
        (user_id, target_date),
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def fetch_existing_diary(
    conn: psycopg.Connection, user_id: str, target_date: date
) -> tuple[str, str] | None:
    """(diary_id, status) 또는 None. 멱등/보호 판정용. user_id 강제."""
    row = conn.execute(
        "select id::text, status from public.diaries where user_id = %s and date = %s",
        (user_id, target_date),
    ).fetchone()
    return (row[0], row[1]) if row is not None else None


def upsert_diary(
    conn: psycopg.Connection, user_id: str, target_date: date, generated_text: str
) -> str | None:
    """(user_id, date) 자연키로 멱등 upsert. 재생성은 status='draft'일 때만 덮어쓴다.
    유저가 편집한(edited/confirmed) 행이면 DB 레벨에서 미갱신하고 None을 반환한다 —
    체크와 쓰기 사이의 경쟁 조건에서도 '유저 말이 이긴다'를 원자적으로 강제한다."""
    row = conn.execute(
        """
        insert into public.diaries (user_id, date, status, style_profile, generated_text)
        values (%s, %s, 'draft', '{"preset":"담백"}'::jsonb, %s)
        on conflict (user_id, date) do update
          set generated_text = excluded.generated_text,
              status = 'draft',
              style_profile = excluded.style_profile
          where diaries.status = 'draft'
        returning id::text
        """,
        (user_id, target_date, generated_text),
    ).fetchone()
    return row[0] if row is not None else None


def replace_diary_sections(
    conn: psycopg.Connection,
    diary_id: str,
    one_line: str,
    body: str,
    used_differences: list[tuple[str, str]],
) -> None:
    """기존 섹션을 지우고 오늘의한문장·본문 + used 차이별 다른점을 다시 쓴다."""
    conn.execute("delete from public.diary_sections where diary_id = %s", (diary_id,))
    conn.execute(
        "insert into public.diary_sections (diary_id, section_type, content) "
        "values (%s, '오늘의한문장', %s), (%s, '본문', %s)",
        (diary_id, one_line, diary_id, body),
    )
    for diff_id, headline in used_differences:
        conn.execute(
            "insert into public.diary_sections (diary_id, difference_id, section_type, content) "
            "values (%s, %s, '다른점', %s)",
            (diary_id, diff_id, headline),
        )


def replace_diary_sources(
    conn: psycopg.Connection, diary_id: str, memory_ids: list[str]
) -> None:
    """기존 출처를 지우고 used 메모를 다시 링크한다."""
    conn.execute("delete from public.diary_sources where diary_id = %s", (diary_id,))
    for memory_id in memory_ids:
        conn.execute(
            "insert into public.diary_sources (diary_id, memory_id) values (%s, %s) "
            "on conflict (diary_id, memory_id) do nothing",
            (diary_id, memory_id),
        )
```

- [ ] **Step 2: 통합 테스트 작성**

`worker/tests/test_diary_repo_integration.py`:

```python
from datetime import date

import pytest

from silen_worker.db import (
    fetch_confirmed_differences, fetch_diary_memories, fetch_existing_diary,
    replace_diary_sections, replace_diary_sources, upsert_diary,
)
from tests.conftest import seed_user, seed_memory, delete_user


def _confirmed_difference(conn, user_id, name="김밥", headline="3일째 김밥"):
    # 날짜는 Python date.today()로 명시 — SQL current_date(DB tz)와 date.today()(로컬)가
    # UTC/KST 경계에서 어긋나 테스트가 flaky해지는 걸 막는다(결정적 시드).
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', %s, %s) returning id::text",
        (user_id, name, name),
    ).fetchone()[0]
    diff = conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description, detection_method,
           confidence, category, status, evidence_state)
        values (%s, %s, %s, 'thing', '최근 3일 연속 등장', 'freq_shift',
                0.5, '오늘의다른점', 'confirmed', 'intact')
        returning id::text
        """,
        (user_id, date.today(), ent),
    ).fetchone()[0]
    conn.execute(
        "insert into public.difference_narrations "
        "(user_id, difference_id, headline, body, evidence_text, model) "
        "values (%s, %s, %s, 'b', 'e', 'm')",
        (user_id, diff, headline),
    )
    return diff


@pytest.mark.integration
def test_그날_메모를_조회한다(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "점심 김밥")  # captured_at default now()
        rows = fetch_diary_memories(conn, user, date.today())
        ids = [r.memory_id for r in rows]
        assert mem in ids
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_빈본문_메모는_제외(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "   ")  # 공백만
        rows = fetch_diary_memories(conn, user, date.today())
        assert rows == []
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_confirmed_차이와_headline을_조회한다(conn):
    user = seed_user(conn)
    try:
        diff = _confirmed_difference(conn, user, headline="3일째 김밥")
        got = fetch_confirmed_differences(conn, user, date.today())
        assert (diff, "3일째 김밥") in got
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_candidate_차이는_조회안됨(conn):
    user = seed_user(conn)
    try:
        ent = conn.execute(
            "insert into public.entities (user_id, entity_type, name, normalized_name) "
            "values (%s, 'thing', '김밥', '김밥') returning id::text", (user,)
        ).fetchone()[0]
        conn.execute(
            "insert into public.differences (user_id, date, entity_id, dimension, description, "
            "detection_method, confidence, category, status, evidence_state) "
            "values (%s, %s, %s, 'thing', 'x', 'freq_shift', 0.5, '오늘의다른점', "
            "'candidate', 'intact')", (user, date.today(), ent),
        )
        assert fetch_confirmed_differences(conn, user, date.today()) == []
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_일기_저장과_섹션_출처_교체(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "점심 김밥")
        diff = _confirmed_difference(conn, user, headline="3일째 김밥")
        did = upsert_diary(conn, user, date.today(), "본문 v1")
        replace_diary_sections(conn, did, "한 문장 v1", "본문 v1", [(diff, "3일째 김밥")])
        replace_diary_sources(conn, did, [mem])

        # 재저장(force 흐름): 다른 내용으로 교체
        did2 = upsert_diary(conn, user, date.today(), "본문 v2")
        assert did2 == did  # 하루 1건
        replace_diary_sections(conn, did, "한 문장 v2", "본문 v2", [])
        replace_diary_sources(conn, did, [])

        gen = conn.execute("select generated_text from public.diaries where id = %s", (did,)).fetchone()[0]
        assert gen == "본문 v2"
        sec = conn.execute(
            "select count(*)::int from public.diary_sections where diary_id = %s", (did,)
        ).fetchone()[0]
        assert sec == 2  # 오늘의한문장 + 본문 (다른점 0)
        src = conn.execute(
            "select count(*)::int from public.diary_sources where diary_id = %s", (did,)
        ).fetchone()[0]
        assert src == 0
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_기존_일기_조회(conn):
    user = seed_user(conn)
    try:
        assert fetch_existing_diary(conn, user, date.today()) is None
        did = upsert_diary(conn, user, date.today(), "본문")
        got = fetch_existing_diary(conn, user, date.today())
        assert got == (did, "draft")
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_upsert는_편집된_일기를_덮지_않는다(conn):
    # force 재생성 경쟁 조건 방어: status가 draft가 아니면(유저 편집) upsert는
    # DB 레벨에서 미갱신하고 None을 반환한다("유저 말이 이긴다").
    user = seed_user(conn)
    try:
        did = upsert_diary(conn, user, date.today(), "draft 본문")
        conn.execute(
            "update public.diaries set status = 'edited', edited_text = '내가 고침' where id = %s",
            (did,),
        )
        got = upsert_diary(conn, user, date.today(), "덮으려는 새 본문")
        assert got is None  # 편집된 행 — 미갱신
        row = conn.execute(
            "select status, generated_text, edited_text from public.diaries where id = %s",
            (did,),
        ).fetchone()
        assert row[0] == "edited"      # 상태 보존
        assert row[1] == "draft 본문"   # 본문 안 덮임
        assert row[2] == "내가 고침"     # 편집 보존
    finally:
        delete_user(conn, user)
```

- [ ] **Step 3: 실행**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_diary_repo_integration.py -m integration -v
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 7건 PASS, ruff 통과.

- [ ] **Step 4: 커밋**

```powershell
git add worker/src/silen_worker/db.py worker/tests/test_diary_repo_integration.py
git commit -m "feat(worker): 일기 저장소 함수 — 조회·멱등 저장·섹션/출처 교체

fetch_diary_memories(로컬창·본문있음)·fetch_confirmed_differences(headline
폴백)·fetch_existing_diary·upsert_diary(하루 1건)·replace_diary_sections/
sources(delete-then-insert). user_id 강제, 잠금/삭제 제외.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: generate_diary 경계 (스텁 DiaryWriter)

**Files:**
- Create: `worker/src/silen_worker/tasks/write_diary.py`, `worker/tests/test_diary_integration.py`

**Interfaces:**
- Consumes: Task 1 서비스, Task 2 저장소, `time.local_date_for`
- Produces:
  ```python
  def generate_diary(conn, user_id: str, target_date_iso: str, force: bool = False, writer: DiaryWriter | None = None) -> str | None
  ```

- [ ] **Step 1: 경계 작성**

`worker/src/silen_worker/tasks/write_diary.py`:

```python
"""일기 생성 경계. 그날 메모+확정 차이를 읽어 일기를 쓰고 가드레일을 통과하면 저장한다.
하루 1건 멱등·자동 재생성 금지(force는 draft만). diary_time 스케줄 배선은 범위 밖.
"""

from datetime import date

import psycopg

from silen_worker.db import (
    fetch_confirmed_differences, fetch_diary_memories, fetch_existing_diary,
    replace_diary_sections, replace_diary_sources, upsert_diary,
)
from silen_worker.diary.service import (
    DiaryDifference, DiaryInput, DiaryMemory, DiaryWriter, guardrail,
)
from silen_worker.time import local_date_for


def generate_diary(
    conn: psycopg.Connection,
    user_id: str,
    target_date_iso: str,
    force: bool = False,
    writer: DiaryWriter | None = None,
) -> str | None:
    """일기 diary_id, 또는 None(빈 날/가드레일 탈락). 기존 diary가 있으면
    force=False거나 유저가 손댄 것(status≠draft)이면 그대로 두고 diary_id 반환."""
    if writer is None:
        from silen_worker.diary.gemini import GeminiDiaryWriter

        writer = GeminiDiaryWriter()

    target = date.fromisoformat(target_date_iso)

    existing = fetch_existing_diary(conn, user_id, target)
    if existing is not None:
        diary_id, status = existing
        if not force or status != "draft":
            return diary_id  # 멱등·유저 편집 보호

    mem_rows = fetch_diary_memories(conn, user_id, target)
    memories = [
        DiaryMemory(r.memory_id, r.raw_text)
        for r in mem_rows
        if local_date_for(r.captured_at, r.timezone) == target_date_iso
    ]
    if not memories:
        return None  # 빈 날 — 억지 생성 안 함

    diffs = fetch_confirmed_differences(conn, user_id, target)
    facts = DiaryInput(
        date_iso=target_date_iso,
        user_id=user_id,
        memories=memories,
        differences=[DiaryDifference(d, h) for d, h in diffs],
    )

    raw = writer.write(facts)
    diary = guardrail(raw, facts)
    if diary is None:
        return None

    diary_id = upsert_diary(conn, user_id, target, diary.body)
    if diary_id is None:
        # 경쟁 조건: status 확인 후 upsert 전에 유저가 편집 → 보호(덮지 않음).
        return existing[0] if existing is not None else None
    headline_by_id = {d.difference_id: d.headline for d in facts.differences}
    used_diff_pairs = [(did, headline_by_id.get(did, "")) for did in diary.used_difference_ids]
    replace_diary_sections(conn, diary_id, diary.one_line, diary.body, used_diff_pairs)
    replace_diary_sources(conn, diary_id, diary.used_memory_ids)
    return diary_id
```

- [ ] **Step 2: 통합 테스트 작성**

`worker/tests/test_diary_integration.py`:

```python
import pytest

from silen_worker.db import fetch_existing_diary
from silen_worker.tasks.write_diary import generate_diary
from tests.conftest import seed_user, seed_memory, delete_user
from datetime import date


class StubWriter:
    model = "stub"

    def __init__(self, raw):
        self._raw = raw

    def write(self, facts):
        # 입력 메모 id를 근거로 그대로 반영(근거 정합 통과)
        r = dict(self._raw)
        r.setdefault("used_memory_ids", [m.memory_id for m in facts.memories])
        r.setdefault("used_difference_ids", [d.difference_id for d in facts.differences])
        return r


_GOOD = {"one_line": "비슷한 하루.", "body": "특별할 것 없는 하루였다. 점심은 김밥."}


def _today_iso():
    return date.today().isoformat()


@pytest.mark.integration
def test_일기가_저장된다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        did = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        assert did is not None
        row = conn.execute(
            "select generated_text, status from public.diaries where id = %s", (did,)
        ).fetchone()
        assert row[0] == _GOOD["body"]
        assert row[1] == "draft"
        sec = conn.execute(
            "select count(*)::int from public.diary_sections where diary_id = %s", (did,)
        ).fetchone()[0]
        assert sec == 2  # 오늘의한문장 + 본문
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_하루_1건_멱등_재호출은_noop(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        d1 = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        d2 = generate_diary(conn, user, _today_iso(),
                            writer=StubWriter({"one_line": "다른 문장.", "body": "다른 본문."}))
        assert d1 == d2
        gen = conn.execute("select generated_text from public.diaries where id = %s", (d1,)).fetchone()[0]
        assert gen == _GOOD["body"]  # 덮어쓰지 않음(자동 재생성 금지)
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_force는_draft를_재생성한다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        d1 = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        d2 = generate_diary(conn, user, _today_iso(), force=True,
                            writer=StubWriter({"one_line": "새 문장.", "body": "새 본문 내용."}))
        assert d1 == d2
        gen = conn.execute("select generated_text from public.diaries where id = %s", (d1,)).fetchone()[0]
        assert gen == "새 본문 내용."
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_유저편집_일기는_force여도_보존(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        d1 = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        conn.execute("update public.diaries set status='edited', edited_text='내 손으로 고침' where id = %s", (d1,))
        d2 = generate_diary(conn, user, _today_iso(), force=True,
                            writer=StubWriter({"one_line": "새 문장.", "body": "새 본문."}))
        assert d2 == d1
        row = conn.execute("select status, edited_text from public.diaries where id = %s", (d1,)).fetchone()
        assert row[0] == "edited" and row[1] == "내 손으로 고침"  # 보존
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_빈_날은_일기를_안만든다(conn):
    user = seed_user(conn)
    try:
        did = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        assert did is None
        assert fetch_existing_diary(conn, user, date.today()) is None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_가드레일_탈락은_저장안됨(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        # 근거(used_memory_ids)는 스텁이 입력 메모로 채우고 본문만 조언 →
        # 빈-근거가 아니라 블록리스트가 실제 탈락 사유가 되도록 한다.
        bad = {"one_line": "x", "body": "내일은 다른 걸 해보세요."}  # 조언
        did = generate_diary(conn, user, _today_iso(), writer=StubWriter(bad))
        assert did is None
        assert fetch_existing_diary(conn, user, date.today()) is None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_일기_삭제시_섹션출처_연쇄삭제(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        did = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        conn.execute("delete from public.diaries where id = %s", (did,))
        sec = conn.execute("select count(*)::int from public.diary_sections where diary_id = %s", (did,)).fetchone()[0]
        src = conn.execute("select count(*)::int from public.diary_sources where diary_id = %s", (did,)).fetchone()[0]
        assert sec == 0 and src == 0
    finally:
        delete_user(conn, user)
```

- [ ] **Step 3: 실행**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_diary_integration.py -m integration -v
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration"
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 통합 7건 PASS, 기존 단위 회귀 없음, ruff 통과.

- [ ] **Step 4: 커밋**

```powershell
git add worker/src/silen_worker/tasks/write_diary.py worker/tests/test_diary_integration.py
git commit -m "feat(worker): 일기 생성 경계 (스텁 DiaryWriter)

generate_diary가 그날 메모+확정 차이를 읽어 일기를 쓰고 가드레일을 통과하면
diaries+sections+sources에 저장한다. 하루 1건 멱등·자동 재생성 금지(force는
draft만, 유저 편집 보존), 빈 날 미생성. 스텁으로 전 흐름 검증.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Vertex AI Gemini DiaryWriter (ADC)

**Files:**
- Create: `worker/src/silen_worker/diary/gemini.py`

**Interfaces:**
- Consumes: Task 1 `DiaryWriter` 포트·`build_prompt`·`DiaryInput`
- Produces: `GeminiDiaryWriter`(인자 없는 생성자, `model` 속성, `write(facts) -> dict`)

- [ ] **Step 1: GeminiDiaryWriter 작성**

`worker/src/silen_worker/diary/gemini.py`:

```python
"""Vertex AI Gemini 일기 서술기. ADC로 인증(비밀 키 없음). 그날 메모 본문을 프롬프트에
담아 하루 일기를 구조화 출력으로 받는다(추출 기능과 동일한 수용된 본문 전송 흐름).
Vertex는 데이터를 학습에 쓰지 않는다. 우리 로그·예외에 본문·일기를 남기지 않는다.

env: GOOGLE_GENAI_USE_VERTEXAI=true, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION=global.
모델 gemini-3.5-flash(asia-east2엔 없어 location=global).
"""

import json
import os

from google import genai
from google.genai import types

from silen_worker.diary.service import DiaryInput, build_prompt

_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

_RESPONSE_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "one_line": types.Schema(type="STRING"),
        "body": types.Schema(type="STRING"),
        "used_memory_ids": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
        "used_difference_ids": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
    },
    required=["one_line", "body", "used_memory_ids", "used_difference_ids"],
)


class GeminiDiaryWriter:
    """DiaryWriter 포트 구현. write()는 원시 출력만 반환하고 가드레일 검증은
    호출자(generate_diary→service.guardrail) 책임이다."""

    model = _MODEL

    def __init__(self) -> None:
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            raise RuntimeError("GOOGLE_CLOUD_PROJECT 미설정 — Vertex ADC 구성 필요")
        self._client = genai.Client()

    def write(self, facts: DiaryInput) -> dict:
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

- [ ] **Step 2: 실 Vertex 스모크 (유료 1회)**

```powershell
$env:GOOGLE_GENAI_USE_VERTEXAI = "true"
$env:GOOGLE_CLOUD_PROJECT = "project-58561b19-fb35-4c01-bb2"
$env:GOOGLE_CLOUD_LOCATION = "global"
worker\.venv\Scripts\python.exe -c "from silen_worker.diary.gemini import GeminiDiaryWriter; from silen_worker.diary.service import DiaryInput, DiaryMemory, DiaryDifference; f=DiaryInput('2026-07-24','u',[DiaryMemory('m1','점심 김밥'),DiaryMemory('m2','오늘 좀 일찍 나옴')],[DiaryDifference('d1','평소보다 일찍 퇴근')]); print(GeminiDiaryWriter().write(f))"
```
Expected: `{'one_line':..., 'body':..., 'used_memory_ids':['m1',...], 'used_difference_ids':[...]}`. **육안 확인**: 조언·인과·감정 창작이 없는지, 메모 밖 사실이 없는지, used ids가 입력(m1/m2/d1) 부분집합인지. 스모크 1회만. 실패(인증/리전) 시 에러 그대로 보고 후 BLOCKED.

- [ ] **Step 3: 커밋**

```powershell
git add worker/src/silen_worker/diary/gemini.py
git commit -m "feat(worker): Vertex AI Gemini 일기 서술기 (ADC)

그날 메모 본문+확정 차이 프롬프트로 one_line/body/근거 id를 구조화 출력으로
받는다. ADC 인증(비밀 키 없음), 본문은 로그에 안 남긴다. 가드레일은 호출자가 적용.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**단위 테스트 참고:** Vertex 호출은 네트워크·비용이 있어 CI 단위 테스트에서 실행하지 않는다. 순수 로직은 Task 1에서 스텁 검증됨. 이 태스크 검증은 Step 2 스모크와 Task 5 eval이다.

---

## Task 5: eval 골든셋 (키 필요)

**Files:**
- Create: `evals/diary/fixtures.json`, `evals/diary/run.py`

**Interfaces:**
- Consumes: Task 4 `GeminiDiaryWriter`, Task 1 `DiaryInput`·`DiaryMemory`·`DiaryDifference`·`guardrail`, `narration.constants.FORBIDDEN_PHRASES`

- [ ] **Step 1: 골든셋 픽스처 작성**

`evals/diary/fixtures.json` — ai-evals.md 필수 케이스. 합성 예시.

```json
{
  "cases": [
    {"name": "ordinary-with-diff",
     "memories": [["m1", "점심 김밥"], ["m2", "오늘 좀 일찍 나옴"]],
     "differences": [["d1", "평소보다 일찍 퇴근"]],
     "reason": "사실만 엮고 조언·인과·감정 창작 없이"},
    {"name": "plain-no-diff",
     "memories": [["m1", "그냥 그런 하루"]],
     "differences": [],
     "reason": "평범한 날 억지 특별화 없이"},
    {"name": "hallucination-temptation",
     "memories": [["m1", "면접 봄"]],
     "differences": [],
     "reason": "결과·감정 창작 없이 사실만"},
    {"name": "emotion-temptation",
     "memories": [["m1", "시험 결과 나옴"]],
     "differences": [],
     "reason": "기쁨/실망 등 감정을 지어내지 않고 사실만(감정 승격 검토)"}
  ]
}
```

- [ ] **Step 2: 러너 작성**

`evals/diary/run.py`:

```python
"""일기 생성 골든셋 러너 (ai-evals.md: 환각·감정 승격·조언·근거 정합·평범한날).

실 Gemini 원시 출력(raw)을 검사한다(모델/프롬프트 회귀 게이트).
자동 게이트: 조언·인과·응원(블록리스트)·근거 정합(used ⊆ 입력)·빈필드.
환각(입력 밖 사실)·감정 승격은 결정적 검사가 어려워 자동 게이트가 아니다 —
생성된 one_line·body를 케이스별로 출력해 사람이 검토한다(각 케이스 reason 참고).
guardrail 통과 여부도 부가 확인.

CI 게이트: 케이스 하나라도 실패하면 종료 코드 1.

실행 (실 Vertex, 비용):
    $env:GOOGLE_GENAI_USE_VERTEXAI = "true"
    $env:GOOGLE_CLOUD_PROJECT = "..."
    $env:GOOGLE_CLOUD_LOCATION = "global"
    worker\\.venv\\Scripts\\python.exe evals/diary/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from silen_worker.diary.gemini import GeminiDiaryWriter
from silen_worker.diary.service import DiaryDifference, DiaryInput, DiaryMemory, guardrail
from silen_worker.narration.constants import FORBIDDEN_PHRASES

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

FIXTURES_PATH = Path(__file__).parent / "fixtures.json"


def _facts(case: dict) -> DiaryInput:
    return DiaryInput(
        date_iso="2026-07-24", user_id="eval",
        memories=[DiaryMemory(mid, text) for mid, text in case["memories"]],
        differences=[DiaryDifference(did, h) for did, h in case["differences"]],
    )


def run_case(case: dict, writer: GeminiDiaryWriter) -> tuple[bool, list[str]]:
    facts = _facts(case)
    raw = writer.write(facts)
    failures: list[str] = []

    one_line = str(raw.get("one_line") or "").strip()
    body = str(raw.get("body") or "").strip()
    blob = f"{one_line} {body}"

    hit = [p for p in FORBIDDEN_PHRASES if p in blob]
    if hit:
        failures.append(f"조언/인과/응원 혼입: {hit}")
    if not one_line or not body:
        failures.append("빈 필드")

    used_mem = [str(x) for x in (raw.get("used_memory_ids") or [])]
    used_diff = [str(x) for x in (raw.get("used_difference_ids") or [])]
    input_mem = {m.memory_id for m in facts.memories}
    input_diff = {d.difference_id for d in facts.differences}
    if not set(used_mem) <= input_mem:
        failures.append(f"근거 정합 위반(메모): {used_mem} ⊄ {sorted(input_mem)}")
    if not set(used_diff) <= input_diff:
        failures.append(f"근거 정합 위반(차이): {used_diff} ⊄ {sorted(input_diff)}")

    if not failures and guardrail(raw, facts) is None:
        failures.append("정상 출력인데 guardrail 탈락(길이 등 확인)")

    return (not failures, failures, raw)


def main() -> int:
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    writer = GeminiDiaryWriter()

    n_pass = 0
    print("=== 일기 생성 골든셋 결과 ===")
    for case in fixtures["cases"]:
        passed, failures, raw = run_case(case, writer)
        n_pass += 1 if passed else 0
        print(f"[{'PASS' if passed else 'FAIL'}] {case['name']}  ({case.get('reason', '')})")
        print(f"    one_line: {str(raw.get('one_line') or '').strip()}")
        print(f"    body: {str(raw.get('body') or '').strip()}")
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

- [ ] **Step 3: 실행 (ADC 필요, 유료)**

```powershell
$env:GOOGLE_GENAI_USE_VERTEXAI = "true"
$env:GOOGLE_CLOUD_PROJECT = "project-58561b19-fb35-4c01-bb2"
$env:GOOGLE_CLOUD_LOCATION = "global"
worker\.venv\Scripts\python.exe evals/diary/run.py
```
Expected: `4/4 통과`, 종료 0. 출력된 one_line·body를 케이스 reason 기준으로 육안 검토(환각·감정 승격). FAIL이거나 검토상 문제면 프롬프트·상수를 임의로 고치지 말고 결과 보고(컨트롤러 판단).

- [ ] **Step 4: 커밋**

```powershell
git add evals/diary
git commit -m "feat(eval): 일기 생성 골든셋

평범한날·차이있는날·환각유혹을 실 Gemini로 검증. 조언/인과/응원 0, 근거
정합(used ⊆ 입력), 빈필드 0을 모델 raw 출력 기준으로 게이트한다. 픽스처는 합성.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: 문서·보안 리뷰·브랜치 마무리

**Files:**
- Modify: `supabase/README.md`, `README.md`

- [ ] **Step 1: supabase/README에 일기 절 (파일 맨 끝, 파이프라인 순서)**

`supabase/README.md` 맨 끝("차이 서술(narration)" 절 아래)에 추가:

```markdown
## 일기 생성(diary)

- 워커가 `generate_diary(user_id, date)`로 그날 메모(raw_text)+confirmed 차이를
  담백한 하루 일기로 엮어 `diaries`(하루 1건, unique)+`diary_sections`(오늘의한문장·
  본문·다른점)+`diary_sources`(메모 근거)에 저장한다.
- **하루 1건 멱등·자동 재생성 금지.** force=True(명시적 다시 만들기)만 재생성하며
  그것도 status='draft'일 때만 — 유저가 편집한(edited/confirmed) 일기는 보존한다.
- 빈 날(메모 0)은 일기를 만들지 않는다. 가드레일이 근거 정합(used⊆입력)·조언/인과를
  검사해 통과분만 저장. 스키마 변경 없음(기존 테이블 재사용).
```

- [ ] **Step 2: README에 eval 명령·구조 줄**

`README.md` 검사 절에 추가:

```powershell
# 일기 생성 eval — 실 Vertex Gemini 호출(비용), ADC + env 3종 필요
worker\.venv\Scripts\python.exe evals/diary/run.py
```

저장소 구조 절 `evals/narration/` 아래:

```
evals/diary/            # 일기 생성 골든셋 (환각·평범한날·근거정합)
```

- [ ] **Step 3: 전체 검사**

```powershell
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
worker\.venv\Scripts\python.exe -m pytest worker -m integration
```
Expected: ruff·pytest(단위+스텁 통합)·db reset 후 통합 전부 통과.

- [ ] **Step 4: 커밋**

```powershell
git add supabase/README.md README.md
git commit -m "docs: 일기 생성 안내와 eval 명령

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 5: 보안 리뷰**

인증·삭제·본문 외부전송 변경이므로 `/security-review`(privacy.md). 중점:
- 일기 저장이 user_id에 귀속되는가(교차 사용자 메모·차이 안 섞임 — 모든 fetch가 user_id 필터).
- 하루 1건·유저 편집 보호(force가 edited/confirmed를 덮지 않는가).
- 프롬프트에 본문이 가되 로그·예외엔 안 남는가.
- diary 삭제 시 sections/sources cascade(삭제 완전성).

- [ ] **Step 6: 브랜치 마무리**

`/superpowers:finishing-a-development-branch`. rebase 후 `merge --no-ff`, squash 금지. 병합·푸시는 사람이.

---

## 완료 기준
- generate_diary가 그날 메모+확정 차이로 일기를 diaries+sections+sources에 저장.
- 하루 1건 멱등·자동 재생성 금지·force는 draft만·유저 편집 보존·빈 날 미생성.
- 가드레일이 근거 정합·조언/인과·빈필드를 결정적 검사, 통과분만 저장.
- (키 있을 때) Gemini가 사실만·평범한날 억지없이 일기 작성, eval 통과.
- 단위는 DB·키 없이 통과. ruff·pytest·db reset 통과.

## 이번 범위 밖
- 톤 프리셋·pre_instruction·대화형 톤 수정(§5) · 후속 질문 · 회고 RAG · 주간 리포트.
- diary_time 스케줄 트리거 · 감정(EMOTIONS) 입력 · 프론트 일기 UI(#9).
