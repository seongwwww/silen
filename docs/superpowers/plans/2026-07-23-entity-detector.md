# 엔티티 통계 차이 검출(detector) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 쌓인 `memory_entities`에서 **결정적 통계 규칙**(first_occurrence·freq_shift)만으로 "평소와 다른 점"을 찾아 `differences(status=candidate)`를 멱등 저장한다. LLM 없음.

**Architecture:** 워커 3계층. 순수 규칙(`detection/service.py`)은 DB·LLM·프레임워크를 모르고 합성 시계열로 단위 테스트한다. 저장소(`db.py`)가 user 스코프·잠금/삭제 제외를 강제하고, 경계(`tasks/detect.py`의 `detect_day`)가 재료를 읽어 사용자 로컬 날짜로 버킷팅한 뒤 규칙을 적용하고 결과를 쓴다. 스케줄 트리거는 범위 밖(호출 가능한 함수로만).

**Tech Stack:** Python 3.12 · psycopg · zoneinfo(기존 `worker/src/silen_worker/time.py`) · pytest

## Global Constraints

- 산출물은 **코드**다. `main` 직접 커밋 금지 — 현재 브랜치 `feat/entity-detector`에서 작업.
- 커밋 메시지 `<type>(<scope>): <한국어 요약>` + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` 트레일러. scope는 `db`·`worker`.
- **마이그레이션 up/down 같은 커밋.** down은 `supabase/migrations/down/<ts>_<name>.down.sql`. 타임스탬프는 `npx supabase migration new`가 생성 — `<ts1>`을 그 값으로 대체.
- 로컬 Supabase만(`postgresql://postgres:postgres@127.0.0.1:54322/postgres`). production 금지. `db reset` 후 auth 502는 `npx supabase stop; npx supabase start`로 복구.
- 워커는 특권 postgres 역할로 접속해 **RLS를 우회한다 → 모든 쿼리에 user_id 필터를 코드로 강제**(교차 사용자 격리의 유일한 방어선).
- **탐지=통계.** 이 기능 어디에도 LLM 호출 없음.
- **하루 경계 = 사용자 로컬 자정.** `memories.captured_at`(timestamptz, 항상 존재) + `users.timezone`을 기존 `time.local_date_for`로 변환. 전날 늦은 메모가 오늘 차이에 새면 안 된다.
- **멱등.** 재실행이 같은 (user, date, entity, method) 차이를 중복 생성하지 않는다.
- **빈 날·산발적 → 0건.** 억지 생성 금지(testing.md 필수 시나리오).
- Python venv `worker\.venv`. 명령은 `worker\.venv\Scripts\python.exe` 직접 호출. lint 게이트: `ruff check worker` clean.
- DoD = lint + typecheck + unit + integration 통과. **eval 없음**(순수 통계, spec §6.3).

## 확정된 스키마 사실 (구현자가 의존)

- `public.differences(id uuid pk, user_id, date, dimension text not null, description text, detection_method text not null check in (zscore|first_occurrence|freq_shift|pattern), confidence real, status default 'candidate', category text not null check in (오늘의다른점|성취|감정전환|패턴), evidence_state default 'intact', staled_at)`. **`entity_id` 컬럼 없음 → Task 1에서 추가.** PK는 `id`뿐 → 부분 unique 인덱스는 순수 추가.
- `public.difference_evidence(difference_id, memory_id, primary key(difference_id, memory_id))`. 둘 다 CASCADE.
- `public.memory_entities(memory_id, entity_id, relation_type, ..., pk(memory_id, entity_id, relation_type))`. `entities(id, user_id, entity_type check in person|place|activity|thing, name, normalized_name)`.
- `public.memories(... user_id, captured_at timestamptz not null, is_locked bool, deleted_at)`. `public.users(... timezone text not null default 'Asia/Seoul')`.
- 기존 `worker/src/silen_worker/time.py` → `local_date_for(instant: datetime, time_zone: str) -> str`("YYYY-MM-DD" 반환). **이 함수가 하루 경계의 단일 출처.**
- 기존 `worker/tests/conftest.py` → `seed_user(conn)`, `seed_memory(conn, user_id, text="메모")`, `delete_user(conn, user_id)`. `db.py` → `connect()`, `dsn()`.

---

## File Structure

| 경로 | 책임 |
|------|------|
| `supabase/migrations/<ts1>_difference_detector.sql` | `differences.entity_id`(ON DELETE SET NULL) + 부분 unique 인덱스 |
| `supabase/migrations/down/<ts1>_difference_detector.down.sql` | 인덱스·컬럼 제거 |
| `worker/src/silen_worker/detection/__init__.py` | |
| `worker/src/silen_worker/detection/constants.py` | 튜닝 상수(창·임계·confidence 계수) 한곳 |
| `worker/src/silen_worker/detection/service.py` | 순수 규칙 + 데이터클래스(DB·LLM 없음) |
| `worker/src/silen_worker/db.py`(수정) | fetch_window_occurrences·fetch_earliest_occurrence·upsert_difference·link_difference_evidence |
| `worker/src/silen_worker/tasks/detect.py` | `detect_day` 경계(재료→버킷팅→규칙→저장) |
| `worker/tests/conftest.py`(수정) | `seed_memory_at` 헬퍼(captured_at 지정) |
| `worker/tests/test_detection.py` | 순수 규칙 단위(합성 시계열, DB 없음) |
| `worker/tests/test_detection_repo_integration.py` | 저장소 스코핑·멱등·근거 링크(실 DB) |
| `worker/tests/test_detect_day_integration.py` | detect_day 종단(멱등·빈날·제외·tz경계·유저격리) |

---

## Task 1: 스키마 — differences.entity_id + 멱등 자연키

**Files:**
- Create: `supabase/migrations/<ts1>_difference_detector.sql`, `supabase/migrations/down/<ts1>_difference_detector.down.sql`
- Create: `worker/tests/test_difference_schema_integration.py`

**Interfaces:**
- Produces: `differences.entity_id`(nullable FK, ON DELETE SET NULL), 부분 unique 인덱스 `differences_entity_natural_key`

- [ ] **Step 1: 마이그레이션 생성**

```powershell
npx supabase migration new difference_detector
```

- [ ] **Step 2: up 작성** — `supabase/migrations/<ts1>_difference_detector.sql`:

```sql
-- 엔티티 기반 차이(first_occurrence·freq_shift)를 근거 엔티티에 연결한다.
-- ON DELETE SET NULL: 엔티티가 삭제돼도 difference를 하드 삭제하지 않는다.
-- 사용자의 status(confirmed/dismissed) 판단을 보존하고, 근거 소실 시 무효화는
-- stale 메커니즘(삭제 원장 기능)의 몫이다(ADR-0002).
alter table public.differences
  add column entity_id uuid references public.entities(id) on delete set null;

-- 멱등 자연키: 같은 (사용자, 날짜, 엔티티, 방법) 차이를 재실행이 중복 생성하지 않는다.
-- entity_id 없는 미래 method(zscore/pattern)는 제약 대상 아님(부분 인덱스).
create unique index differences_entity_natural_key
  on public.differences (user_id, date, entity_id, detection_method)
  where entity_id is not null;
```

- [ ] **Step 3: down 작성** — `supabase/migrations/down/<ts1>_difference_detector.down.sql`:

```sql
drop index if exists public.differences_entity_natural_key;
alter table public.differences drop column if exists entity_id;
```

- [ ] **Step 4: 통합 테스트** — `worker/tests/test_difference_schema_integration.py`:

```python
import pytest

from tests.conftest import seed_user, seed_memory, delete_user


def _entity(conn, user_id, name="민수", etype="person"):
    return conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, %s, %s, %s) returning id::text",
        (user_id, etype, name, name),
    ).fetchone()[0]


def _insert_diff(conn, user_id, entity_id, method="first_occurrence"):
    return conn.execute(
        "insert into public.differences "
        "  (user_id, date, entity_id, dimension, description, detection_method, category) "
        "values (%s, '2026-07-23', %s, 'person', '테스트', %s, '오늘의다른점') "
        "returning id::text",
        (user_id, entity_id, method),
    ).fetchone()[0]


@pytest.mark.integration
def test_같은_자연키_차이는_중복_생성되지_않는다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user)
        _insert_diff(conn, user, ent)
        with pytest.raises(Exception):  # unique 위반
            _insert_diff(conn, user, ent)
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_엔티티_삭제시_entity_id는_null이_되고_difference는_남는다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user)
        did = _insert_diff(conn, user, ent)
        conn.execute("delete from public.entities where id = %s", (ent,))
        row = conn.execute(
            "select entity_id from public.differences where id = %s", (did,)
        ).fetchone()
        assert row is not None      # difference 보존
        assert row[0] is None       # entity_id만 null
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_entity_id_null인_행은_자연키_제약을_받지_않는다(conn):
    user = seed_user(conn)
    try:
        # 미래 method(zscore 등) 시뮬레이션 — entity_id null 두 건이 충돌하지 않는다.
        for _ in range(2):
            conn.execute(
                "insert into public.differences "
                "  (user_id, date, dimension, description, detection_method, category) "
                "values (%s, '2026-07-23', 'x', 'y', 'zscore', '오늘의다른점')",
                (user,),
            )
        n = conn.execute(
            "select count(*)::int from public.differences where user_id = %s", (user,)
        ).fetchone()[0]
        assert n == 2
    finally:
        delete_user(conn, user)
```

- [ ] **Step 5: 적용·실행**

```powershell
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_difference_schema_integration.py -m integration -v
```

Expected: 3건 PASS.

- [ ] **Step 6: 커밋**

```powershell
git add supabase/migrations worker/tests/test_difference_schema_integration.py
git commit -m "feat(db): differences.entity_id와 멱등 자연키

엔티티 기반 차이를 근거 엔티티에 연결(ON DELETE SET NULL — 엔티티가
삭제돼도 사용자 status 판단을 보존, 무효화는 stale의 몫, ADR-0002).
(user,date,entity,method) 부분 unique로 재실행 멱등."
```

---

## Task 2: 순수 검출 규칙 (DB·LLM 없음)

**Files:**
- Create: `worker/src/silen_worker/detection/__init__.py`, `worker/src/silen_worker/detection/constants.py`, `worker/src/silen_worker/detection/service.py`, `worker/tests/test_detection.py`

**Interfaces:**
- Produces:
  ```python
  # constants.py
  WINDOW_DAYS=28; STREAK_MIN=2; REEMERGENCE_GAP_MIN=7
  # service.py
  @dataclass(frozen=True) class EntityWindow: entity_id:str; entity_type:str; dates:frozenset; occurred_before:bool
  @dataclass(frozen=True) class DetectedDifference: entity_id:str; entity_type:str; method:str; description:str; confidence:float
  def detect_differences(target_date: date, windows: list[EntityWindow]) -> list[DetectedDifference]
  ```

- [ ] **Step 1: 실패 테스트** — `worker/tests/test_detection.py`:

```python
from datetime import date, timedelta

from silen_worker.detection.service import (
    EntityWindow,
    detect_differences,
)

TARGET = date(2026, 7, 23)


def _win(dates, occurred_before, etype="thing", eid="e1"):
    return EntityWindow(eid, etype, frozenset(dates), occurred_before)


def _by_id(diffs):
    return {d.entity_id: d for d in diffs}


def test_이력_없는_엔티티는_first_occurrence():
    out = detect_differences(TARGET, [_win({TARGET}, occurred_before=False)])
    assert len(out) == 1
    assert out[0].method == "first_occurrence"
    assert out[0].description == "이 thing 첫 등장"
    assert out[0].confidence == 1.0


def test_오늘만_등장하고_이력_있으면_차이없음():
    # 아주 오래전(창 밖) 등장 이력만 있고 최근 창엔 오늘뿐 → 산발, 차이 없음.
    out = detect_differences(TARGET, [_win({TARGET}, occurred_before=True)])
    assert out == []


def test_이틀_연속은_streak():
    dates = {TARGET, TARGET - timedelta(days=1)}
    out = detect_differences(TARGET, [_win(dates, occurred_before=True)])
    assert len(out) == 1
    assert out[0].method == "freq_shift"
    assert out[0].description == "최근 2일 연속 등장"


def test_사흘_연속_streak_길이가_반영된다():
    dates = {TARGET, TARGET - timedelta(days=1), TARGET - timedelta(days=2)}
    out = detect_differences(TARGET, [_win(dates, occurred_before=True)])
    assert out[0].description == "최근 3일 연속 등장"


def test_7일_이상_공백_후_재등장():
    dates = {TARGET, TARGET - timedelta(days=9)}  # 9일 공백
    out = detect_differences(TARGET, [_win(dates, occurred_before=True)])
    assert len(out) == 1
    assert out[0].method == "freq_shift"
    assert out[0].description == "9일 만에 재등장(최근 28일 내)"


def test_6일_공백은_재등장_아님_산발():
    dates = {TARGET, TARGET - timedelta(days=6)}  # 6일 공백, 연속 아님
    out = detect_differences(TARGET, [_win(dates, occurred_before=True)])
    assert out == []


def test_빈_입력은_0건():
    assert detect_differences(TARGET, []) == []


def test_오늘_등장하지_않는_엔티티는_분류하지_않는다():
    dates = {TARGET - timedelta(days=1)}  # 어제만
    out = detect_differences(TARGET, [_win(dates, occurred_before=True)])
    assert out == []


def test_first와_freq는_상호배타():
    # occurred_before=False면 창에 오늘만 있어도 freq_shift로 뜨지 않는다.
    out = detect_differences(TARGET, [_win({TARGET}, occurred_before=False)])
    assert [d.method for d in out] == ["first_occurrence"]


def test_streak가_재등장보다_우선():
    # 연속이면서 공백도 있는 경우 streak로 분류(연속 우선).
    dates = {TARGET, TARGET - timedelta(days=1), TARGET - timedelta(days=10)}
    out = detect_differences(TARGET, [_win(dates, occurred_before=True)])
    assert out[0].description == "최근 2일 연속 등장"
```

- [ ] **Step 2: 실패 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_detection.py -v
```

Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 상수 작성** — `worker/src/silen_worker/detection/constants.py`:

```python
"""탐지 튜닝 상수 한곳. 골든 단위 테스트로 검증·튜닝한다(spec §3.3)."""

WINDOW_DAYS = 28          # freq_shift 관찰 창
STREAK_MIN = 2            # 연속 등장 최소 일수
REEMERGENCE_GAP_MIN = 7   # 재등장으로 볼 최소 공백(일)

FIRST_OCCURRENCE_CONFIDENCE = 1.0
STREAK_CONFIDENCE_SPAN = 6.0        # (streak_len-1)/SPAN, 7일=1.0
REEMERGENCE_CONFIDENCE_SPAN = float(WINDOW_DAYS)  # gap/WINDOW, 28일=1.0
```

- [ ] **Step 4: __init__ + 서비스 작성**

`worker/src/silen_worker/detection/__init__.py`:

```python
"""엔티티 통계 차이 검출 — 순수 규칙. 탐지=통계, LLM 없음."""
```

`worker/src/silen_worker/detection/service.py`:

```python
"""결정적 차이 규칙. DB·LLM·프레임워크를 모른다 — 테스트를 여기 집중(spec §5.2).

입력: 오늘 포함 창 안의 엔티티별 등장 날짜 집합 + 전체 이력 존재 여부.
출력: DetectedDifference 목록. 오늘 등장한 엔티티만, 정확히 하나로 분류(상호 배타).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from silen_worker.detection.constants import (
    FIRST_OCCURRENCE_CONFIDENCE,
    REEMERGENCE_CONFIDENCE_SPAN,
    REEMERGENCE_GAP_MIN,
    STREAK_CONFIDENCE_SPAN,
    STREAK_MIN,
    WINDOW_DAYS,
)


@dataclass(frozen=True)
class EntityWindow:
    entity_id: str
    entity_type: str
    dates: frozenset          # 창[target-(WINDOW-1)..target] 안의 로컬 날짜, target 포함 가정
    occurred_before: bool     # target 이전 전체 이력에 등장한 적 있는가


@dataclass(frozen=True)
class DetectedDifference:
    entity_id: str
    entity_type: str
    method: str               # 'first_occurrence' | 'freq_shift'
    description: str          # 통계 근거(사람에게 직접 노출 안 함)
    confidence: float


def _streak_len(dates: frozenset, target: date) -> int:
    """target에서 끝나는 연속 등장 일수."""
    n = 0
    d = target
    while d in dates:
        n += 1
        d -= timedelta(days=1)
    return n


def detect_differences(target_date: date, windows: list[EntityWindow]) -> list[DetectedDifference]:
    out: list[DetectedDifference] = []
    for w in windows:
        if target_date not in w.dates:
            continue  # 오늘 등장한 엔티티만 분류

        if not w.occurred_before:
            out.append(
                DetectedDifference(
                    w.entity_id, w.entity_type, "first_occurrence",
                    f"이 {w.entity_type} 첫 등장", FIRST_OCCURRENCE_CONFIDENCE,
                )
            )
            continue

        # freq_shift: 이력 있음. 창 안 반복 신호가 있을 때만.
        streak = _streak_len(w.dates, target_date)
        if streak >= STREAK_MIN:
            conf = min(1.0, (streak - 1) / STREAK_CONFIDENCE_SPAN)
            out.append(
                DetectedDifference(
                    w.entity_id, w.entity_type, "freq_shift",
                    f"최근 {streak}일 연속 등장", conf,
                )
            )
            continue

        prior = [d for d in w.dates if d < target_date]
        if prior:
            gap = (target_date - max(prior)).days
            if gap >= REEMERGENCE_GAP_MIN:
                conf = min(1.0, gap / REEMERGENCE_CONFIDENCE_SPAN)
                out.append(
                    DetectedDifference(
                        w.entity_id, w.entity_type, "freq_shift",
                        f"{gap}일 만에 재등장(최근 {WINDOW_DAYS}일 내)", conf,
                    )
                )
        # 그 외(산발적) → 차이 없음(오탐 억제)
    return out
```

- [ ] **Step 5: 통과 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_detection.py -v
worker\.venv\Scripts\python.exe -m ruff check worker
```

Expected: 10건 PASS, ruff clean.

- [ ] **Step 6: 커밋**

```powershell
git add worker/src/silen_worker/detection worker/tests/test_detection.py
git commit -m "feat(worker): 차이 검출 순수 규칙 (first_occurrence·freq_shift)

이력 없으면 first_occurrence, 있으면 창 안 연속(streak)·재등장을 freq_shift로.
산발적 등장은 차이 없음(오탐 억제), 상호 배타. 튜닝 상수는 한곳에 모아
골든 단위 테스트로 검증. DB·LLM 없는 결정적 규칙."
```

---

## Task 3: 저장소 — 재료 조회·멱등 upsert·근거 링크

**Files:**
- Modify: `worker/src/silen_worker/db.py`, `worker/tests/conftest.py`
- Create: `worker/tests/test_detection_repo_integration.py`

**Interfaces:**
- Consumes: Task 1 스키마, 기존 `connect`
- Produces:
  ```python
  @dataclass class OccurrenceRow: entity_id:str; entity_type:str; memory_id:str; captured_at:datetime; timezone:str
  def fetch_window_occurrences(conn, user_id, target_date: date, window_days: int) -> list[OccurrenceRow]
  def fetch_earliest_occurrence(conn, user_id, entity_ids: list[str]) -> dict[str, tuple[datetime, str]]
  def upsert_difference(conn, user_id, target_date: date, entity_id, detection_method, dimension, description, confidence) -> str
  def link_difference_evidence(conn, difference_id, memory_id) -> None
  # conftest.py
  def seed_memory_at(conn, user_id, captured_at_iso: str, text="메모") -> str
  ```

- [ ] **Step 1: conftest에 captured_at 지정 시드 추가**

`worker/tests/conftest.py`에 추가(기존 함수는 건드리지 않음):

```python
def seed_memory_at(
    conn: psycopg.Connection, user_id: str, captured_at_iso: str, text: str | None = "메모"
) -> str:
    """captured_at을 명시해 메모를 시드한다(타임존 경계 테스트용)."""
    row = conn.execute(
        "insert into public.memories (user_id, raw_text, source_type, memory_type, captured_at) "
        "values (%s, %s, 'manual', 'moment', %s) returning id::text",
        (user_id, text, captured_at_iso),
    ).fetchone()
    return row[0]
```

- [ ] **Step 2: db.py에 저장소 함수 추가**

`worker/src/silen_worker/db.py`에 추가(상단 import에 `from datetime import date, datetime, timedelta, timezone` 추가):

```python
@dataclass
class OccurrenceRow:
    entity_id: str
    entity_type: str
    memory_id: str
    captured_at: datetime
    timezone: str


def fetch_window_occurrences(
    conn: psycopg.Connection, user_id: str, target_date: date, window_days: int
) -> list[OccurrenceRow]:
    """창을 넉넉히 덮는 UTC 범위의 활성 엔티티 언급을 반환한다. 로컬 날짜 버킷팅은
    호출자가 time.local_date_for로 정밀하게 한다(하루 경계 단일 출처). user_id 강제,
    잠금/삭제 메모 제외."""
    lower = datetime.combine(
        target_date - timedelta(days=window_days + 2), datetime.min.time(), timezone.utc
    )
    upper = datetime.combine(
        target_date + timedelta(days=2), datetime.min.time(), timezone.utc
    )
    rows = conn.execute(
        """
        select me.entity_id::text, e.entity_type, m.id::text, m.captured_at, u.timezone
        from public.memory_entities me
        join public.memories m on m.id = me.memory_id
        join public.entities e on e.id = me.entity_id
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and m.captured_at >= %s
          and m.captured_at < %s
        """,
        (user_id, lower, upper),
    ).fetchall()
    return [OccurrenceRow(r[0], r[1], r[2], r[3], r[4]) for r in rows]


def fetch_earliest_occurrence(
    conn: psycopg.Connection, user_id: str, entity_ids: list[str]
) -> dict[str, tuple[datetime, str]]:
    """주어진 엔티티들의 가장 이른 활성 언급 시각+타임존. first_occurrence 판정용
    (전체 이력 존재 여부). user_id 강제."""
    if not entity_ids:
        return {}
    rows = conn.execute(
        """
        select distinct on (me.entity_id)
               me.entity_id::text, m.captured_at, u.timezone
        from public.memory_entities me
        join public.memories m on m.id = me.memory_id
        join public.users u on u.id = m.user_id
        where m.user_id = %s
          and m.deleted_at is null
          and m.is_locked = false
          and me.entity_id = any(%s::uuid[])
        order by me.entity_id, m.captured_at asc
        """,
        (user_id, entity_ids),
    ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def upsert_difference(
    conn: psycopg.Connection,
    user_id: str,
    target_date: date,
    entity_id: str,
    detection_method: str,
    dimension: str,
    description: str,
    confidence: float,
) -> str:
    """(user_id, date, entity_id, detection_method) 부분 자연키로 멱등 upsert.
    재실행 시 근거를 되살린다(evidence_state=intact)."""
    row = conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description,
           detection_method, confidence, category, status, evidence_state)
        values (%s, %s, %s, %s, %s, %s, %s, '오늘의다른점', 'candidate', 'intact')
        on conflict (user_id, date, entity_id, detection_method) where entity_id is not null
        do update set description = excluded.description,
                      confidence = excluded.confidence,
                      dimension = excluded.dimension,
                      evidence_state = 'intact',
                      staled_at = null
        returning id::text
        """,
        (user_id, target_date, entity_id, dimension, description, detection_method, confidence),
    ).fetchone()
    return row[0]


def link_difference_evidence(
    conn: psycopg.Connection, difference_id: str, memory_id: str
) -> None:
    """(difference_id, memory_id) PK로 멱등 링크."""
    conn.execute(
        "insert into public.difference_evidence (difference_id, memory_id) "
        "values (%s, %s) on conflict (difference_id, memory_id) do nothing",
        (difference_id, memory_id),
    )
```

- [ ] **Step 3: 통합 테스트** — `worker/tests/test_detection_repo_integration.py`:

```python
from datetime import date

import pytest

from silen_worker.db import (
    fetch_earliest_occurrence,
    fetch_window_occurrences,
    link_difference_evidence,
    upsert_difference,
)
from tests.conftest import seed_user, seed_memory_at, delete_user


def _entity(conn, user_id, name, etype="thing"):
    return conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, %s, %s, %s) returning id::text",
        (user_id, etype, name, name),
    ).fetchone()[0]


def _link(conn, memory_id, entity_id):
    conn.execute(
        "insert into public.memory_entities (memory_id, entity_id, relation_type) "
        "values (%s, %s, 'mentioned')",
        (memory_id, entity_id),
    )


@pytest.mark.integration
def test_window_조회는_user_스코프와_잠금삭제를_제외한다(conn):
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        ea = _entity(conn, alice, "김밥")
        m_ok = seed_memory_at(conn, alice, "2026-07-23T01:00:00+00")
        _link(conn, m_ok, ea)
        # 잠긴 메모
        m_lock = seed_memory_at(conn, alice, "2026-07-23T02:00:00+00")
        conn.execute("update public.memories set is_locked = true where id = %s", (m_lock,))
        _link(conn, m_lock, ea)
        # 삭제된 메모
        m_del = seed_memory_at(conn, alice, "2026-07-23T03:00:00+00")
        conn.execute("update public.memories set deleted_at = now() where id = %s", (m_del,))
        _link(conn, m_del, ea)
        # 밥의 메모(타 사용자)
        eb = _entity(conn, bob, "김밥")
        m_bob = seed_memory_at(conn, bob, "2026-07-23T01:00:00+00")
        _link(conn, m_bob, eb)

        rows = fetch_window_occurrences(conn, alice, date(2026, 7, 23), 28)
        mem_ids = {r.memory_id for r in rows}
        assert m_ok in mem_ids
        assert m_lock not in mem_ids   # 잠금 제외
        assert m_del not in mem_ids    # 삭제 제외
        assert m_bob not in mem_ids    # 타 사용자 제외
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)


@pytest.mark.integration
def test_earliest는_가장_이른_언급을_준다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user, "요가", "activity")
        seed_and_link_early = seed_memory_at(conn, user, "2026-07-01T00:00:00+00")
        _link(conn, seed_and_link_early, ent)
        late = seed_memory_at(conn, user, "2026-07-23T00:00:00+00")
        _link(conn, late, ent)
        got = fetch_earliest_occurrence(conn, user, [ent])
        assert ent in got
        assert got[ent][0].isoformat().startswith("2026-07-01")
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_difference_upsert는_멱등이고_근거를_링크한다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user, "김밥")
        mem = seed_memory_at(conn, user, "2026-07-23T01:00:00+00")
        _link(conn, mem, ent)
        d = date(2026, 7, 23)

        did1 = upsert_difference(conn, user, d, ent, "first_occurrence", "thing", "이 thing 첫 등장", 1.0)
        link_difference_evidence(conn, did1, mem)
        # 재실행 — 같은 자연키 → 같은 행
        did2 = upsert_difference(conn, user, d, ent, "first_occurrence", "thing", "이 thing 첫 등장", 1.0)
        link_difference_evidence(conn, did2, mem)

        assert did1 == did2
        n = conn.execute(
            "select count(*)::int from public.differences where user_id = %s", (user,)
        ).fetchone()[0]
        assert n == 1
        ev = conn.execute(
            "select count(*)::int from public.difference_evidence where difference_id = %s", (did1,)
        ).fetchone()[0]
        assert ev == 1
    finally:
        delete_user(conn, user)
```

- [ ] **Step 4: 실행**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_detection_repo_integration.py -m integration -v
worker\.venv\Scripts\python.exe -m ruff check worker
```

Expected: 3건 PASS, ruff clean.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/db.py worker/tests/conftest.py worker/tests/test_detection_repo_integration.py
git commit -m "feat(worker): 차이 검출 저장소 — 조회·멱등 upsert·근거 링크

fetch_window_occurrences(창 UTC 범위, user 스코프·잠금/삭제 제외),
fetch_earliest_occurrence(first_occurrence 판정용 전체 이력 최솟값),
upsert_difference(부분 자연키 멱등), link_difference_evidence.
로컬 날짜 버킷팅은 경계에서 time 유틸로 정밀 처리."
```

---

## Task 4: 경계 — detect_day 종단

**Files:**
- Create: `worker/src/silen_worker/tasks/detect.py`, `worker/tests/test_detect_day_integration.py`

**Interfaces:**
- Consumes: Task 2 서비스, Task 3 저장소, 기존 `time.local_date_for`, `connect`
- Produces: `def detect_day(conn, user_id: str, target_date_iso: str) -> list[str]`  # 기록된 difference id들

- [ ] **Step 1: 경계 작성** — `worker/src/silen_worker/tasks/detect.py`:

```python
"""엔티티 통계 차이 검출 경계. 재료를 읽어 사용자 로컬 날짜로 버킷팅하고,
순수 규칙을 적용해 differences를 멱등 저장한다. 스케줄 트리거는 범위 밖 —
호출 가능한 함수. 탐지=통계, LLM 없음.
"""

from datetime import date

import psycopg

from silen_worker.db import (
    fetch_earliest_occurrence,
    fetch_window_occurrences,
    link_difference_evidence,
    upsert_difference,
)
from silen_worker.detection.constants import WINDOW_DAYS
from silen_worker.detection.service import EntityWindow, detect_differences
from silen_worker.time import local_date_for


def detect_day(conn: psycopg.Connection, user_id: str, target_date_iso: str) -> list[str]:
    target = date.fromisoformat(target_date_iso)
    window_start = target.toordinal() - (WINDOW_DAYS - 1)

    rows = fetch_window_occurrences(conn, user_id, target, WINDOW_DAYS)

    # 로컬 날짜로 버킷팅(하루 경계 단일 출처: time.local_date_for).
    by_entity: dict[str, dict] = {}
    for r in rows:
        local = date.fromisoformat(local_date_for(r.captured_at, r.timezone))
        if local.toordinal() < window_start or local > target:
            continue  # 창 밖 정밀 제외
        b = by_entity.setdefault(
            r.entity_id, {"type": r.entity_type, "dates": set(), "today": []}
        )
        b["dates"].add(local)
        if local == target:
            b["today"].append(r.memory_id)

    today_entities = {eid: b for eid, b in by_entity.items() if target in b["dates"]}
    if not today_entities:
        return []

    earliest = fetch_earliest_occurrence(conn, user_id, list(today_entities))
    windows = []
    for eid, b in today_entities.items():
        occurred_before = False
        er = earliest.get(eid)
        if er is not None:
            occurred_before = date.fromisoformat(local_date_for(er[0], er[1])) < target
        windows.append(EntityWindow(eid, b["type"], frozenset(b["dates"]), occurred_before))

    written: list[str] = []
    for diff in detect_differences(target, windows):
        did = upsert_difference(
            conn, user_id, target, diff.entity_id, diff.method,
            diff.entity_type, diff.description, diff.confidence,
        )
        for mid in today_entities[diff.entity_id]["today"]:
            link_difference_evidence(conn, did, mid)
        written.append(did)
    return written
```

> `detect_day(conn, ...)`가 호출 인터페이스다. 실제 스케줄 구동·연결 관리·큐 배선은 spec §5.1대로 **다음 기능**의 몫이라 여기서 만들지 않는다.

- [ ] **Step 2: 종단 통합 테스트** — `worker/tests/test_detect_day_integration.py`:

```python
import pytest

from silen_worker.tasks.detect import detect_day
from tests.conftest import seed_user, seed_memory_at, delete_user


def _entity(conn, user_id, name, etype="thing"):
    return conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, %s, %s, %s) returning id::text",
        (user_id, etype, name, name),
    ).fetchone()[0]


def _mention(conn, user_id, entity_id, captured_at_iso):
    mem = seed_memory_at(conn, user_id, captured_at_iso)
    conn.execute(
        "insert into public.memory_entities (memory_id, entity_id, relation_type) "
        "values (%s, %s, 'mentioned')",
        (mem, entity_id),
    )
    return mem


def _diffs(conn, user_id):
    return conn.execute(
        "select detection_method, description from public.differences "
        "where user_id = %s order by detection_method, description",
        (user_id,),
    ).fetchall()


@pytest.mark.integration
def test_첫_등장이_first_occurrence로_기록되고_근거가_연결된다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user, "낯선카페", "place")
        mem = _mention(conn, user, ent, "2026-07-23T02:00:00+00")

        written = detect_day(conn, user, "2026-07-23")

        assert len(written) == 1
        rows = _diffs(conn, user)
        assert rows == [("first_occurrence", "이 place 첫 등장")]
        ev = conn.execute(
            "select memory_id::text from public.difference_evidence where difference_id = %s",
            (written[0],),
        ).fetchall()
        assert [e[0] for e in ev] == [mem]
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_이틀_연속이면_freq_shift_streak(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user, "김밥")
        _mention(conn, user, ent, "2026-07-22T02:00:00+00")
        _mention(conn, user, ent, "2026-07-23T02:00:00+00")
        detect_day(conn, user, "2026-07-23")
        assert _diffs(conn, user) == [("freq_shift", "최근 2일 연속 등장")]
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_재실행은_중복을_만들지_않는다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user, "요가", "activity")
        _mention(conn, user, ent, "2026-07-23T02:00:00+00")
        detect_day(conn, user, "2026-07-23")
        detect_day(conn, user, "2026-07-23")
        n = conn.execute(
            "select count(*)::int from public.differences where user_id = %s", (user,)
        ).fetchone()[0]
        assert n == 1
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_빈_날은_0건_억지생성_안함(conn):
    user = seed_user(conn)
    try:
        # 오늘 언급 없음(어제만).
        ent = _entity(conn, user, "산책", "activity")
        _mention(conn, user, ent, "2026-07-22T02:00:00+00")
        written = detect_day(conn, user, "2026-07-23")
        assert written == []
        assert _diffs(conn, user) == []
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_타임존_경계_전날_늦은_메모는_오늘에_새지_않는다(conn):
    user = seed_user(conn)
    try:
        conn.execute("update public.users set timezone = 'Asia/Seoul' where id = %s", (user,))
        ent = _entity(conn, user, "김밥")
        # 07-22T14:30Z = 07-22 23:30 KST → 로컬 07-22 (오늘 아님)
        _mention(conn, user, ent, "2026-07-22T14:30:00+00")
        # 07-22T15:30Z = 07-23 00:30 KST → 로컬 07-23 (오늘)
        m_today = _mention(conn, user, ent, "2026-07-22T15:30:00+00")

        written = detect_day(conn, user, "2026-07-23")

        # 오늘 로컬에 처음(전체 이력에 07-22 KST 존재하므로 occurred_before=True),
        # 07-22 KST와 07-23 KST는 연속 → streak 2일.
        assert _diffs(conn, user) == [("freq_shift", "최근 2일 연속 등장")]
        ev = conn.execute(
            "select memory_id::text from public.difference_evidence", ()
        ).fetchall()
        # 근거는 오늘(07-23 KST) 메모만.
        assert [e[0] for e in ev] == [m_today]
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_타_사용자_엔티티는_절대_섞이지_않는다(conn):
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        ea = _entity(conn, alice, "김밥")
        _mention(conn, alice, ea, "2026-07-23T02:00:00+00")
        eb = _entity(conn, bob, "김밥")
        _mention(conn, bob, eb, "2026-07-23T02:00:00+00")

        detect_day(conn, alice, "2026-07-23")

        # 앨리스 것만 기록, 밥은 0건.
        na = conn.execute(
            "select count(*)::int from public.differences where user_id = %s", (alice,)
        ).fetchone()[0]
        nb = conn.execute(
            "select count(*)::int from public.differences where user_id = %s", (bob,)
        ).fetchone()[0]
        assert na == 1
        assert nb == 0
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)
```

- [ ] **Step 3: 실행**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -m integration -v
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration"
worker\.venv\Scripts\python.exe -m ruff check worker
```

Expected: 통합(스키마 3 + 저장소 3 + 종단 6 + 기존 추출/워커 12 = 24) PASS, 단위(검출 10 + 추출 10 + time 7 = 27) PASS, ruff clean. (숫자는 대략치 — 전부 PASS면 된다.)

- [ ] **Step 4: 커밋**

```powershell
git add worker/src/silen_worker/tasks/detect.py worker/tests/test_detect_day_integration.py
git commit -m "feat(worker): detect_day 경계 — 재료→로컬버킷팅→규칙→저장

창 재료를 읽어 사용자 로컬 자정 경계로 버킷팅(time 유틸)하고, 순수 규칙을
적용해 differences를 멱등 저장 + 근거 연결. 빈날 0건, 잠금/삭제/타 사용자
제외, 타임존 경계로 전날 메모 누출 방지. 스케줄 배선은 범위 밖."
```

---

## Task 5: 문서·검증·마무리

**Files:**
- Modify: `supabase/README.md`

- [ ] **Step 1: supabase/README에 detector 메모** — 엔티티 절 아래에 추가:

```markdown
## 차이 검출(detector)

- 워커가 `detect_day(user_id, date)`로 그날 언급된 엔티티를 통계 규칙으로 분류해
  `differences(status=candidate)`를 채운다. **탐지=통계, LLM 없음.**
- 규칙 2종: first_occurrence(전체 이력 첫 등장), freq_shift(28일 창 연속 streak /
  7일+ 공백 후 재등장). 산발적 등장·빈 날은 0건(억지 생성 안 함).
- 하루 경계는 사용자 로컬 자정(users.timezone + time.local_date_for).
- (user,date,entity,method) 부분 unique로 멱등. 스케줄 배선은 다음 기능.
```

- [ ] **Step 2: 전체 검증**

```powershell
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
worker\.venv\Scripts\python.exe -m pytest worker -m integration
```

Expected: 전부 PASS.

- [ ] **Step 3: 커밋**

```powershell
git add supabase/README.md
git commit -m "docs: 차이 검출(detector) 워커 안내"
```

- [ ] **Step 4: 브랜치 마무리**

`/superpowers:finishing-a-development-branch`. 테스트 통과 확인 → main 위로 rebase → `merge --no-ff`(**squash 금지**, git.md). (병합·푸시는 사람이.)

> 참고: 이 기능은 Auth·삭제·RAG 변경이 아니므로 `/security-review` 필수는 아니다. 다만 user 스코프 격리가 핵심이라, 종단 테스트의 "타 사용자 안 섞임"·"잠금/삭제 제외"가 그 방어선을 고정한다.

---

## 완료 기준

- `differences.entity_id`(ON DELETE SET NULL) + 부분 unique 인덱스, 스키마 통합 통과
- 순수 규칙: first_occurrence·streak·재등장·산발제외·빈날0·상호배타 단위 통과
- 저장소: user 스코프·잠금/삭제 제외·멱등 upsert·근거 링크 통합 통과
- detect_day 종단: 첫등장·연속·멱등·빈날·**타임존 경계**·**타 사용자 격리** 통합 통과
- `ruff`·`pytest`·`supabase db reset` 통과. LLM·eval 없음.

## 이번 범위 밖 (spec §7)
- z-score(signals 비어 있음) · pattern-corr · 감정 전환(emotions)
- 의미필터 · 차이 서술 · 일기 생성(LLM)
- **스케줄 트리거**(일 배치 구동) · baselines 테이블 적재
- 근거 소실 시 difference staling(삭제 원장 기능 소관)
- 유저 확정(맞아요/아니에요) UI
