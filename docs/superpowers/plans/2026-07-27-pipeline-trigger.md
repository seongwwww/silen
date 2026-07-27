# 파이프라인 트리거(CLI 엔트리포인트) Implementation Plan

> **실행 주체:** 이 계획은 **Codex가 구현**한다. Superpowers 스킬 없이 수동으로 수행한다 — 태스크마다 ① 실패 테스트 → ② 실패 확인 → ③ 계획의 코드 그대로 구현 → ④ 통과 확인 → ⑤ lint → ⑥ 그 태스크 단위로 1커밋.

**Goal:** 워커 함수 4개(`process_pending`·`detect_day`·`narrate_difference`·`generate_diary`)를 CLI로 실제 구동 가능하게 만들고, 스케줄러 반복 실행에도 LLM 재과금이 없게 한다.

**Architecture:** `cli.py`는 얇은 오케스트레이션 계층이다 — 새 도메인 로직 없이 기존 `tasks/*` 함수를 부른다. 대상 선택은 순수 함수(`local_yesterday`·`build_targets`)로 분리해 DB 없이 단위 테스트한다. LLM은 포트 주입(스텁)으로 검증한다.

**Tech Stack:** Python 3.12 · argparse(표준 라이브러리) · psycopg 3 · pytest

## Global Constraints

- 산출물은 **코드**다. `main` 직접 커밋 금지 — **`feat/pipeline-trigger` 브랜치를 `main`에서 새로 만들어** 작업한다.
- 커밋 메시지 `<type>(<scope>): <한국어 요약>`. scope는 `worker`·`docs`. **`Co-Authored-By` 트레일러는 네 것으로** 바꾼다(네가 저자다, git.md).
- **태스크마다 커밋만. push·merge 금지**(사람이 한다).
- 파이썬 명령은 `worker\.venv\Scripts\python.exe`를 직접 호출한다.
- 통합 테스트는 **로컬 Supabase 스택이 떠 있어야** 한다. `npx supabase db reset` 후에는 반드시 `npx supabase stop; Start-Sleep -Seconds 3; npx supabase start`로 auth 502를 복구한다.
- 워커는 특권 역할로 psycopg 직접 접속(RLS 우회). **모든 쿼리에 user 스코프를 코드로 강제**한다.
- **로그에 사용자 기록 본문·일기 텍스트를 남기지 않는다** — `user_id`·카운트·id·예외 **타입명**만(backend.md·privacy.md).
- **새 도메인 로직·스키마 변경 없음.** 마이그레이션을 만들지 마라.
- 이미 병합된 기능(extraction·detector·narration·diary·UI)을 **이 계획이 지정한 파일 외엔 수정하지 마라.**
- 완료(DoD) = ruff + pytest(단위+통합). **eval은 이 기능 대상 아님**(프롬프트·모델 미변경).
- 못 고치는 실패나 모호한 점이 있으면 **멈추고 보고**하라. 추측하거나 테스트를 약화시키지 마라.

## 결정 고정 (Locked Decisions — 무-추측 규약)

1. **`process_pending`은 `conn`을 받지 않는다**(자체 `connect()`). 나머지 셋은 `conn`을 받는다. 이 불일치는 **그대로 둔다** — 통일하지 마라(병합된 코드 회귀 위험, 스펙 §7).
2. **`skip_if_exists` 기본값은 `True`.** 기존 narration이 있으면 LLM을 부르지 않고 그 id를 반환한다. 기존 호출자(테스트 포함)의 동작이 바뀌는 건 의도된 것이다.
3. **로그는 JSON 한 줄을 stdout에 `print`** 한다. 로깅 프레임워크를 도입하지 마라. 예외는 `type(exc).__name__`만 기록한다 — **예외 메시지에 프롬프트/본문이 섞여 나올 수 있어** 메시지를 로그에 넣지 않는다.
4. **날짜 기본값은 "사용자 로컬 어제"**. `local_date_for(now_utc, tz)`로 오늘을 구한 뒤 하루를 뺀다. `--date`가 있으면 모든 대상에 그 값을 그대로 쓴다.
5. **`--user`가 존재하지 않는 사용자면** stderr에 메시지를 찍고 **exit 1**(조용한 무동작 방지).
6. **종료 코드**: 실패 0건 → `0`, 1건 이상 → `1`. 인자 오류는 argparse 기본(`2`).
7. **`run-diary`는 `force=False`가 기본.** `--force` 플래그를 줄 때만 `True`.
8. **`run-pending`은 drain**: 한 배치가 `limit`보다 적게 처리하면 종료, 아니면 반복. `--max-batches` 기본 50(무한 루프 방지).
9. **`run_pending`은 실패를 세지 않는다** — `process_pending`이 내부에서 예외를 잡아 큐 재시도/데드레터로 처리하므로 CLI로 전파되지 않는다. 반환값은 처리한 memory_id 총 개수다.
10. **사용자 단위 실패 격리**: `run_daily`·`run_diary`는 사용자 하나가 예외를 던져도 잡아서 집계하고 다음 사용자로 넘어간다.
11. **순수 함수 분리**: `local_yesterday(tz, now)`·`build_targets(users, user, date_iso, now)`는 DB를 모른다(단위 테스트 대상). `resolve_targets(conn, ...)`가 이 둘과 `fetch_active_users`를 잇는다.
12. **`fetch_active_users`는 `public.users` 전체**를 `(user_id, timezone)`로 반환한다. "최근 활동" 필터를 넣지 마라(YAGNI, MVP는 사용자 수가 적다).
13. **console script(`silen-worker`)는 부가**다. 문서·스케줄러가 쓰는 **정식 형태는 `python -m silen_worker`** — venv 파이썬을 직접 지목해 PATH 문제를 피한다.
14. **스케줄러 실제 등록은 사람이** 한다. 문서만 작성하고 `schtasks`·`crontab` 명령을 실행하지 마라.

## File Structure

| 경로 | 책임 |
|------|------|
| `worker/src/silen_worker/db.py`(수정) | `fetch_active_users`·`fetch_narration_id` 추가 |
| `worker/src/silen_worker/tasks/narrate.py`(수정) | `skip_if_exists` 파라미터(재실행 안전) |
| `worker/src/silen_worker/cli.py` | 순수 대상 계산 + 세 명령 오케스트레이션 + argparse |
| `worker/src/silen_worker/__main__.py` | `python -m silen_worker` 진입점 |
| `worker/pyproject.toml`(수정) | `[project.scripts]` |
| `worker/tests/test_cli_targets.py` | 대상 계산·인자 파싱 단위(DB 없음) |
| `worker/tests/test_cli_integration.py` | 세 명령 통합(체인·재실행 1회·실패 격리·스코프) |
| `worker/tests/test_narrate_skip_integration.py` | skip_if_exists 재실행 안전 통합 |
| `README.md`(수정) | 실행·스케줄 등록 안내 |

---

## Task 1: db 함수 — 사용자 열거·서술 존재 조회

**Files:**
- Modify: `worker/src/silen_worker/db.py` (파일 끝에 추가)
- Create: `worker/tests/test_cli_db_integration.py`

**Interfaces:**
- Consumes: 기존 `connect()`·psycopg 패턴
- Produces:
  ```python
  def fetch_active_users(conn) -> list[tuple[str, str]]   # [(user_id, timezone), ...]
  def fetch_narration_id(conn, difference_id: str) -> str | None
  ```

- [ ] **Step 1: 실패 테스트 작성**

`worker/tests/test_cli_db_integration.py`:

```python
import pytest

from silen_worker.db import fetch_active_users, fetch_narration_id
from tests.conftest import seed_user, seed_memory, delete_user


def _difference_with_narration(conn, user_id, headline="3일째 김밥"):
    """차이 하나 + 그 서술을 만들고 (difference_id, narration_id)를 돌려준다."""
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', '김밥', '김밥') returning id::text",
        (user_id,),
    ).fetchone()[0]
    from datetime import date

    diff = conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description, detection_method,
           confidence, category, status, evidence_state)
        values (%s, %s, %s, 'thing', '최근 3일 연속 등장', 'freq_shift',
                0.5, '오늘의다른점', 'candidate', 'intact')
        returning id::text
        """,
        (user_id, date.today(), ent),
    ).fetchone()[0]
    nid = conn.execute(
        "insert into public.difference_narrations "
        "(user_id, difference_id, headline, body, evidence_text, model) "
        "values (%s, %s, %s, 'b', 'e', 'm') returning id::text",
        (user_id, diff, headline),
    ).fetchone()[0]
    return diff, nid


@pytest.mark.integration
def test_사용자를_타임존과_함께_열거한다(conn):
    user = seed_user(conn)
    try:
        rows = fetch_active_users(conn)
        found = [(u, tz) for (u, tz) in rows if u == user]
        assert len(found) == 1
        assert found[0][1] == "Asia/Seoul"  # users.timezone 기본값
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_서술이_있으면_id를_돌려준다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "김밥 먹음")
        diff, nid = _difference_with_narration(conn, user)
        assert fetch_narration_id(conn, diff) == nid
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_서술이_없으면_None(conn):
    user = seed_user(conn)
    try:
        ent = conn.execute(
            "insert into public.entities (user_id, entity_type, name, normalized_name) "
            "values (%s, 'thing', '김밥', '김밥') returning id::text",
            (user,),
        ).fetchone()[0]
        from datetime import date

        diff = conn.execute(
            """
            insert into public.differences
              (user_id, date, entity_id, dimension, description, detection_method,
               confidence, category, status, evidence_state)
            values (%s, %s, %s, 'thing', 'x', 'freq_shift', 0.5, '오늘의다른점',
                    'candidate', 'intact')
            returning id::text
            """,
            (user, date.today(), ent),
        ).fetchone()[0]
        assert fetch_narration_id(conn, diff) is None
    finally:
        delete_user(conn, user)
```

- [ ] **Step 2: 실패 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_cli_db_integration.py -m integration -v
```
Expected: FAIL — `ImportError: cannot import name 'fetch_active_users'`.

- [ ] **Step 3: 구현 작성**

`worker/src/silen_worker/db.py` **파일 끝에** 추가:

```python
def fetch_active_users(conn: psycopg.Connection) -> list[tuple[str, str]]:
    """모든 사용자를 (user_id, timezone)으로 반환한다. 배치 대상 열거용.
    사용자별 '하루' 경계 계산에 timezone이 필요하다(time.local_date_for)."""
    rows = conn.execute(
        "select id::text, timezone from public.users order by id"
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def fetch_narration_id(conn: psycopg.Connection, difference_id: str) -> str | None:
    """이 차이에 이미 서술이 있으면 그 id, 없으면 None.
    재실행 시 LLM 재호출(반복 과금)을 막는 판정에 쓴다."""
    row = conn.execute(
        "select id::text from public.difference_narrations where difference_id = %s",
        (difference_id,),
    ).fetchone()
    return row[0] if row is not None else None
```

- [ ] **Step 4: 통과 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_cli_db_integration.py -m integration -v
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 3건 PASS, ruff 통과.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/db.py worker/tests/test_cli_db_integration.py
git commit -m "feat(worker): 배치 대상 열거·서술 존재 조회 함수

fetch_active_users는 (user_id, timezone)을 반환해 사용자별 하루 경계
계산을 가능하게 한다. fetch_narration_id는 재실행 시 LLM 재호출을 막는
판정에 쓴다."
```

---

## Task 2: 재실행 안전 — `narrate_difference(skip_if_exists=True)`

**⚠️ 이 태스크가 이 기능의 핵심이다.** 스케줄러가 반복 호출해도 이미 서술된 차이에는 LLM을 부르지 않아야 한다.

**Files:**
- Modify: `worker/src/silen_worker/tasks/narrate.py`
- Create: `worker/tests/test_narrate_skip_integration.py`

**Interfaces:**
- Consumes: Task 1의 `fetch_narration_id`
- Produces:
  ```python
  def narrate_difference(conn, difference_id: str, narrator: Narrator | None = None,
                         skip_if_exists: bool = True) -> str | None
  ```

- [ ] **Step 1: 실패 테스트 작성**

`worker/tests/test_narrate_skip_integration.py`:

```python
from datetime import date

import pytest

from silen_worker.tasks.narrate import narrate_difference
from tests.conftest import seed_user, seed_memory, delete_user


class CountingNarrator:
    """LLM 호출 횟수를 센다. 재실행 과금 방지의 증거."""

    model = "stub"

    def __init__(self):
        self.calls = 0

    def narrate(self, facts):
        self.calls += 1
        return {
            "headline": f"{facts.entity_name} 반복",
            "body": f"{facts.entity_name}을 최근 3일 연속으로 남기셨네요.",
            "evidence_text": "요즘 자주 등장해서 찾았어요.",
        }


def _candidate_difference(conn, user_id):
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', '김밥', '김밥') returning id::text",
        (user_id,),
    ).fetchone()[0]
    return conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description, detection_method,
           confidence, category, status, evidence_state)
        values (%s, %s, %s, 'thing', '최근 3일 연속 등장', 'freq_shift',
                0.5, '오늘의다른점', 'candidate', 'intact')
        returning id::text
        """,
        (user_id, date.today(), ent),
    ).fetchone()[0]


@pytest.mark.integration
def test_이미_서술된_차이는_LLM을_다시_부르지_않는다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "김밥 먹음")
        diff = _candidate_difference(conn, user)
        narrator = CountingNarrator()

        first = narrate_difference(conn, diff, narrator=narrator)
        second = narrate_difference(conn, diff, narrator=narrator)

        assert first is not None
        assert second == first        # 같은 narration id 반환
        assert narrator.calls == 1    # 핵심: 두 번째는 LLM 미호출
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_skip_if_exists_False면_다시_서술한다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "김밥 먹음")
        diff = _candidate_difference(conn, user)
        narrator = CountingNarrator()

        narrate_difference(conn, diff, narrator=narrator)
        narrate_difference(conn, diff, narrator=narrator, skip_if_exists=False)

        assert narrator.calls == 2  # 명시적 다시 만들기
    finally:
        delete_user(conn, user)
```

- [ ] **Step 2: 실패 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_narrate_skip_integration.py -m integration -v
```
Expected: 첫 테스트가 `assert narrator.calls == 1`에서 FAIL(현재는 2회 호출됨). 두 번째 테스트는 `TypeError: unexpected keyword argument 'skip_if_exists'`로 FAIL.

- [ ] **Step 3: 구현 수정**

`worker/src/silen_worker/tasks/narrate.py`에서 **import 줄에 `fetch_narration_id`를 추가**하고 함수 시그니처·본문 앞부분을 아래로 교체한다:

```python
from silen_worker.db import (
    fetch_difference_for_narration,
    fetch_narration_id,
    upsert_narration,
)
from silen_worker.narration.service import Narrator, NarrationInput, guardrail


def narrate_difference(
    conn: psycopg.Connection,
    difference_id: str,
    narrator: Narrator | None = None,
    skip_if_exists: bool = True,
) -> str | None:
    """서술 성공 시 narration id, 대상 없음/가드레일 탈락 시 None.

    skip_if_exists=True(기본)면 이미 서술이 있는 차이에는 LLM을 부르지 않고
    기존 id를 돌려준다 — 스케줄러가 반복 호출해도 재과금이 없다.
    명시적 '다시 만들기'는 skip_if_exists=False로 호출한다.
    """
    if skip_if_exists:
        existing = fetch_narration_id(conn, difference_id)
        if existing is not None:
            return existing

    if narrator is None:
        from silen_worker.narration.gemini import GeminiNarrator

        narrator = GeminiNarrator()

    facts_row = fetch_difference_for_narration(conn, difference_id)
    if facts_row is None:
        return None
```

**나머지 본문(`facts = NarrationInput(...)` 이하)은 그대로 둔다.**

> 주의: 기존 `narrator=None` 지연 import 블록을 **`skip_if_exists` 확인보다 뒤로** 옮겨야 한다. 그래야 이미 서술된 차이를 처리할 때 `GeminiNarrator()`(ADC 필요)를 생성조차 하지 않는다.

- [ ] **Step 4: 통과 확인 + 기존 회귀**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_narrate_skip_integration.py -m integration -v
worker\.venv\Scripts\python.exe -m pytest worker -m integration
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 새 2건 PASS. **기존 통합 테스트도 전부 통과해야 한다** — 특히 `test_narration_integration.py`의 재서술 테스트는 같은 difference를 두 번 서술하므로 `skip_if_exists` 기본값 때문에 깨질 수 있다. 깨지면 **테스트를 약화시키지 말고**, 그 테스트가 "명시적 재서술"을 검증하는 것이므로 해당 호출에 `skip_if_exists=False`를 넘기도록 고친다(의도를 명확히 하는 수정). 판단이 서지 않으면 멈추고 보고하라.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/tasks/narrate.py worker/tests/test_narrate_skip_integration.py
git commit -m "feat(worker): 서술 재실행 안전 — skip_if_exists

narrate_difference가 기존 서술 존재를 확인하지 않고 매번 LLM을 불러
스케줄러 반복 실행 시 전체 재서술로 반복 과금이 됐다. 기본값 True로
이미 서술된 차이는 LLM 없이 기존 id를 반환한다. 명시적 다시 만들기는
skip_if_exists=False."
```

---

## Task 3: 대상 계산 — 순수 함수 + 인자 파서

**Files:**
- Create: `worker/src/silen_worker/cli.py` (이 태스크는 순수 부분·파서만)
- Create: `worker/tests/test_cli_targets.py`

**Interfaces:**
- Consumes: `silen_worker.time.local_date_for`
- Produces:
  ```python
  def local_yesterday(tz: str, now: datetime) -> str            # 'YYYY-MM-DD'
  def build_targets(users: list[tuple[str, str]], user: str | None,
                    date_iso: str | None, now: datetime) -> list[tuple[str, str]]
  def build_parser() -> argparse.ArgumentParser
  ```

- [ ] **Step 1: 실패 테스트 작성**

`worker/tests/test_cli_targets.py`:

```python
from datetime import datetime, timezone

from silen_worker.cli import build_parser, build_targets, local_yesterday

_USERS = [("u1", "Asia/Seoul"), ("u2", "America/New_York")]


def test_서울_자정_전이면_어제는_전날():
    # UTC 14:30 = 서울 23:30 (7/27) → 어제 = 7/26
    now = datetime(2026, 7, 27, 14, 30, tzinfo=timezone.utc)
    assert local_yesterday("Asia/Seoul", now) == "2026-07-26"


def test_서울_자정_후면_어제가_하루_넘어간다():
    # UTC 16:00 = 서울 01:00 (7/28) → 어제 = 7/27
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    assert local_yesterday("Asia/Seoul", now) == "2026-07-27"


def test_타임존마다_어제가_다르다():
    # UTC 16:00 = 서울 7/28 01:00, 뉴욕 7/27 12:00
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    assert local_yesterday("Asia/Seoul", now) == "2026-07-27"
    assert local_yesterday("America/New_York", now) == "2026-07-26"


def test_인자_없으면_전체_사용자의_각자_어제():
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    targets = build_targets(_USERS, user=None, date_iso=None, now=now)
    assert targets == [("u1", "2026-07-27"), ("u2", "2026-07-26")]


def test_date를_주면_모든_대상에_그대로_쓴다():
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    targets = build_targets(_USERS, user=None, date_iso="2026-01-01", now=now)
    assert targets == [("u1", "2026-01-01"), ("u2", "2026-01-01")]


def test_user를_주면_그_사용자만():
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    targets = build_targets(_USERS, user="u2", date_iso=None, now=now)
    assert targets == [("u2", "2026-07-26")]


def test_없는_user면_빈_목록():
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    assert build_targets(_USERS, user="없음", date_iso=None, now=now) == []


def test_파서가_세_명령을_안다():
    parser = build_parser()
    assert parser.parse_args(["run-pending"]).command == "run-pending"
    assert parser.parse_args(["run-daily"]).command == "run-daily"
    assert parser.parse_args(["run-diary"]).command == "run-diary"


def test_파서_기본값과_옵션():
    parser = build_parser()
    args = parser.parse_args(["run-daily"])
    assert args.user is None and args.date is None

    args = parser.parse_args(["run-daily", "--user", "u1", "--date", "2026-07-01"])
    assert args.user == "u1" and args.date == "2026-07-01"

    assert parser.parse_args(["run-diary"]).force is False
    assert parser.parse_args(["run-diary", "--force"]).force is True

    args = parser.parse_args(["run-pending"])
    assert args.limit == 10 and args.max_batches == 50
```

- [ ] **Step 2: 실패 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_cli_targets.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'silen_worker.cli'`.

- [ ] **Step 3: 구현 작성**

`worker/src/silen_worker/cli.py` (이 태스크에서는 아래 내용만. 명령 실행부는 Task 4에서 추가):

```python
"""워커 CLI — 파이프라인 진입점. 주기 실행은 외부 스케줄러에 위임한다.

새 도메인 로직 없음: 기존 tasks/* 함수를 부르는 얇은 오케스트레이션 계층이다.
대상 계산(local_yesterday·build_targets)은 DB를 모르는 순수 함수라 단위 테스트한다.

로그는 JSON 한 줄을 stdout에 찍는다. **사용자 기록 본문·일기 텍스트는 절대
남기지 않는다** — user_id·카운트·id·예외 타입명만(backend.md·privacy.md).
"""

import argparse
from datetime import date, datetime, timedelta

from silen_worker.time import local_date_for


def local_yesterday(tz: str, now: datetime) -> str:
    """사용자 로컬 기준 '어제'(YYYY-MM-DD). 자정이 지나야 그 하루가 완결된다."""
    today_local = date.fromisoformat(local_date_for(now, tz))
    return (today_local - timedelta(days=1)).isoformat()


def build_targets(
    users: list[tuple[str, str]],
    user: str | None,
    date_iso: str | None,
    now: datetime,
) -> list[tuple[str, str]]:
    """처리할 (user_id, date_iso) 목록. user를 주면 그 사용자만, date_iso를 주면
    모든 대상에 그 날짜를 쓴다. 없으면 각자 로컬 어제."""
    selected = [(uid, tz) for uid, tz in users if user is None or uid == user]
    return [
        (uid, date_iso if date_iso is not None else local_yesterday(tz, now))
        for uid, tz in selected
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="silen-worker", description="실은 워커 파이프라인 실행"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_pending = sub.add_parser("run-pending", help="큐 소비 → 엔티티 추출")
    p_pending.add_argument("--limit", type=int, default=10, help="한 배치 크기")
    p_pending.add_argument(
        "--max-batches", dest="max_batches", type=int, default=50,
        help="무한 루프 방지 상한",
    )

    for name, help_text in (
        ("run-daily", "차이 검출 → 서술"),
        ("run-diary", "일기 생성(확정 차이 반영)"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--user", default=None, help="이 사용자만 처리(기본: 전체)")
        p.add_argument("--date", default=None, help="YYYY-MM-DD(기본: 각자 로컬 어제)")
        if name == "run-diary":
            p.add_argument(
                "--force", action="store_true",
                help="이미 있는 draft 일기를 다시 생성(유저 편집본은 보존)",
            )

    return parser
```

- [ ] **Step 4: 통과 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_cli_targets.py -v
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 9건 PASS, ruff 통과.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/cli.py worker/tests/test_cli_targets.py
git commit -m "feat(worker): CLI 대상 계산·인자 파서

인자 없으면 전체 사용자 × 각자 로컬 어제를 처리한다. 하루 경계는
time.local_date_for 단일 출처를 쓴다. 대상 계산은 DB를 모르는 순수
함수라 타임존별로 단위 테스트한다."
```

---

## Task 4: 세 명령 구현 + 집계·종료 코드

**Files:**
- Modify: `worker/src/silen_worker/cli.py` (Task 3 내용 뒤에 추가)
- Create: `worker/tests/test_cli_integration.py`

**Interfaces:**
- Consumes: Task 1 `fetch_active_users`, Task 2 `narrate_difference(skip_if_exists)`, Task 3 순수 함수, 기존 `process_pending`·`detect_day`·`generate_diary`
- Produces:
  ```python
  def run_pending(extractor=None, limit: int = 10, max_batches: int = 50) -> int
  def run_daily(conn, targets: list[tuple[str, str]], narrator=None) -> tuple[int, int]
  def run_diary(conn, targets: list[tuple[str, str]], writer=None, force: bool = False) -> tuple[int, int]
  def resolve_targets(conn, user, date_iso, now=None) -> list[tuple[str, str]]
  def main(argv=None) -> int
  ```

- [ ] **Step 1: 실패 테스트 작성**

`worker/tests/test_cli_integration.py`:

```python
from datetime import date

import pytest

from silen_worker.cli import run_daily, run_diary
from silen_worker.db import fetch_existing_diary, fetch_narration_id
from tests.conftest import seed_user, seed_memory, delete_user


class CountingNarrator:
    model = "stub"

    def __init__(self):
        self.calls = 0

    def narrate(self, facts):
        self.calls += 1
        return {
            "headline": f"{facts.entity_name} 반복",
            "body": f"{facts.entity_name}을 최근 3일 연속으로 남기셨네요.",
            "evidence_text": "요즘 자주 등장해서 찾았어요.",
        }


class BoomNarrator:
    """특정 사용자에서만 터지는 서술기. 실패 격리 검증용."""

    model = "stub"

    def __init__(self, boom_user):
        self.boom_user = boom_user
        self.calls = 0

    def narrate(self, facts):
        self.calls += 1
        if facts.user_id == self.boom_user:
            raise RuntimeError("boom")
        return {
            "headline": f"{facts.entity_name} 반복",
            "body": f"{facts.entity_name}을 최근 3일 연속으로 남기셨네요.",
            "evidence_text": "요즘 자주 등장해서 찾았어요.",
        }


class StubWriter:
    model = "stub"

    def write(self, facts):
        return {
            "one_line": "비슷한 하루.",
            "body": "특별할 것 없는 하루였다. 점심은 김밥.",
            "used_memory_ids": [m.memory_id for m in facts.memories],
            "used_difference_ids": [d.difference_id for d in facts.differences],
        }


def _entity_mention(conn, user_id, text="김밥 먹음", name="김밥"):
    """메모 + 그 메모가 언급한 엔티티를 만든다(detect_day가 볼 재료)."""
    mem = seed_memory(conn, user_id, text)
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', %s, %s) "
        "on conflict (user_id, entity_type, normalized_name) do update set name = excluded.name "
        "returning id::text",
        (user_id, name, name),
    ).fetchone()[0]
    conn.execute(
        "insert into public.memory_entities (memory_id, entity_id, relation_type) "
        "values (%s, %s, 'mentioned') on conflict do nothing",
        (mem, ent),
    )
    return mem, ent


def _today():
    return date.today().isoformat()


@pytest.mark.integration
def test_run_daily가_차이를_검출하고_서술한다(conn):
    user = seed_user(conn)
    try:
        _entity_mention(conn, user)
        narrator = CountingNarrator()
        ok, fail = run_daily(conn, [(user, _today())], narrator=narrator)

        assert (ok, fail) == (1, 0)
        diffs = conn.execute(
            "select id::text from public.differences where user_id = %s", (user,)
        ).fetchall()
        assert len(diffs) >= 1
        assert fetch_narration_id(conn, diffs[0][0]) is not None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_run_daily를_두번_돌려도_LLM은_한번만(conn):
    """핵심 회귀: 스케줄러 반복 실행이 재과금을 만들지 않는다."""
    user = seed_user(conn)
    try:
        _entity_mention(conn, user)
        narrator = CountingNarrator()

        run_daily(conn, [(user, _today())], narrator=narrator)
        first_calls = narrator.calls
        run_daily(conn, [(user, _today())], narrator=narrator)

        assert first_calls >= 1
        assert narrator.calls == first_calls  # 두 번째 실행은 LLM 미호출
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_한_사용자_실패가_다른_사용자를_막지_않는다(conn):
    user_a = seed_user(conn)
    user_b = seed_user(conn)
    try:
        _entity_mention(conn, user_a)
        _entity_mention(conn, user_b)
        narrator = BoomNarrator(boom_user=user_a)

        ok, fail = run_daily(
            conn, [(user_a, _today()), (user_b, _today())], narrator=narrator
        )

        assert (ok, fail) == (1, 1)
        b_diffs = conn.execute(
            "select id::text from public.differences where user_id = %s", (user_b,)
        ).fetchall()
        assert fetch_narration_id(conn, b_diffs[0][0]) is not None  # B는 처리됨
    finally:
        delete_user(conn, user_a)
        delete_user(conn, user_b)


@pytest.mark.integration
def test_run_diary가_일기를_만든다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        ok, fail = run_diary(conn, [(user, _today())], writer=StubWriter())

        assert (ok, fail) == (1, 0)
        assert fetch_existing_diary(conn, user, date.today()) is not None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_빈_날은_일기를_안만들지만_실패도_아니다(conn):
    user = seed_user(conn)
    try:
        ok, fail = run_diary(conn, [(user, _today())], writer=StubWriter())
        assert (ok, fail) == (1, 0)  # 처리는 성공, 생성은 안 함
        assert fetch_existing_diary(conn, user, date.today()) is None
    finally:
        delete_user(conn, user)
```

- [ ] **Step 2: 실패 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_cli_integration.py -m integration -v
```
Expected: FAIL — `ImportError: cannot import name 'run_daily' from 'silen_worker.cli'`.

- [ ] **Step 3: 구현 추가**

`worker/src/silen_worker/cli.py`의 **import 블록을 아래로 교체**하고(기존 argparse·datetime·local_date_for 유지 + 추가), 파일 **끝에** 명령 구현을 붙인다:

```python
import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone

from silen_worker.db import connect, fetch_active_users
from silen_worker.tasks.detect import detect_day
from silen_worker.tasks.narrate import narrate_difference
from silen_worker.tasks.process import process_pending
from silen_worker.tasks.write_diary import generate_diary
from silen_worker.time import local_date_for
```

파일 끝에 추가:

```python
def _emit(event: dict) -> None:
    """구조화 로그 한 줄. 본문·일기 텍스트를 절대 싣지 않는다."""
    print(json.dumps(event, ensure_ascii=False))


def resolve_targets(
    conn, user: str | None, date_iso: str | None, now: datetime | None = None
) -> list[tuple[str, str]]:
    """DB에서 사용자를 읽어 처리 대상 (user_id, date_iso) 목록을 만든다."""
    return build_targets(
        fetch_active_users(conn),
        user,
        date_iso,
        now or datetime.now(timezone.utc),
    )


def run_pending(extractor=None, limit: int = 10, max_batches: int = 50) -> int:
    """큐가 빌 때까지(또는 상한까지) 소비하고 처리한 memory 개수를 반환한다.
    process_pending은 conn을 받지 않고 자체 접속한다(기존 인터페이스 유지)."""
    total = 0
    for _ in range(max_batches):
        processed = process_pending(limit=limit, extractor=extractor)
        total += len(processed)
        if len(processed) < limit:
            break
    _emit({"event": "run_pending.done", "processed": total})
    return total


def run_daily(conn, targets: list[tuple[str, str]], narrator=None) -> tuple[int, int]:
    """사용자별로 차이를 검출하고 서술한다. (성공 수, 실패 수) 반환.
    한 사용자의 실패가 나머지를 막지 않는다."""
    ok = fail = 0
    for user_id, date_iso in targets:
        try:
            difference_ids = detect_day(conn, user_id, date_iso)
            narrated = 0
            for difference_id in difference_ids:
                if narrate_difference(conn, difference_id, narrator=narrator) is not None:
                    narrated += 1
            _emit({
                "event": "run_daily.user", "user_id": user_id, "date": date_iso,
                "differences": len(difference_ids), "narrated": narrated,
            })
            ok += 1
        except Exception as exc:  # 사용자 단위 격리
            fail += 1
            _emit({
                "event": "run_daily.error", "user_id": user_id, "date": date_iso,
                "error": type(exc).__name__,  # 메시지는 본문이 섞일 수 있어 제외
            })
    return ok, fail


def run_diary(
    conn, targets: list[tuple[str, str]], writer=None, force: bool = False
) -> tuple[int, int]:
    """사용자별로 일기를 생성한다. (성공 수, 실패 수) 반환.
    빈 날은 생성하지 않지만 실패가 아니다."""
    ok = fail = 0
    for user_id, date_iso in targets:
        try:
            diary_id = generate_diary(
                conn, user_id, date_iso, force=force, writer=writer
            )
            _emit({
                "event": "run_diary.user", "user_id": user_id, "date": date_iso,
                "created": diary_id is not None,
            })
            ok += 1
        except Exception as exc:  # 사용자 단위 격리
            fail += 1
            _emit({
                "event": "run_diary.error", "user_id": user_id, "date": date_iso,
                "error": type(exc).__name__,
            })
    return ok, fail


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "run-pending":
        run_pending(limit=args.limit, max_batches=args.max_batches)
        return 0

    with connect() as conn:
        targets = resolve_targets(conn, args.user, args.date)
        if args.user is not None and not targets:
            print(f"사용자를 찾을 수 없습니다: {args.user}", file=sys.stderr)
            return 1

        if args.command == "run-daily":
            ok, fail = run_daily(conn, targets)
        else:
            ok, fail = run_diary(conn, targets, force=args.force)

    _emit({"event": f"{args.command}.done", "ok": ok, "failed": fail})
    return 1 if fail else 0
```

- [ ] **Step 4: 통과 확인 + 전체 회귀**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_cli_integration.py -m integration -v
worker\.venv\Scripts\python.exe -m pytest worker
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 새 5건 PASS, 전체 pytest 통과, ruff 통과.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/cli.py worker/tests/test_cli_integration.py
git commit -m "feat(worker): CLI 세 명령 — run-pending·run-daily·run-diary

run-daily는 detect→narrate 체인을, run-diary는 확정 차이를 반영한 일기를
돌린다. 사용자 단위로 실패를 격리하고 집계해 실패가 있으면 exit 1.
로그는 JSON 한 줄이며 본문·일기 텍스트를 싣지 않는다(예외는 타입명만)."
```

---

## Task 5: 엔트리포인트 — `python -m silen_worker`

**Files:**
- Create: `worker/src/silen_worker/__main__.py`
- Modify: `worker/pyproject.toml`

**Interfaces:**
- Consumes: Task 4 `main`

- [ ] **Step 1: `__main__.py` 작성**

`worker/src/silen_worker/__main__.py`:

```python
"""`python -m silen_worker <command>` 진입점."""

import sys

from silen_worker.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: pyproject에 console script 추가**

`worker/pyproject.toml`의 `[project.optional-dependencies]` 블록 **바로 앞**에 추가:

```toml
[project.scripts]
silen-worker = "silen_worker.cli:main"
```

- [ ] **Step 3: 재설치 후 스모크**

console script는 재설치해야 생긴다. `python -m` 형태는 재설치 없이 즉시 동작한다.

```powershell
worker\.venv\Scripts\python.exe -m pip install -e "worker[dev]"
worker\.venv\Scripts\python.exe -m silen_worker --help
worker\.venv\Scripts\python.exe -m silen_worker run-daily --help
```
Expected: 도움말이 출력되고 세 하위 명령(`run-pending`·`run-daily`·`run-diary`)이 보인다.

**LLM을 부르는 실행(`run-daily`를 인자 없이)은 이 단계에서 하지 마라** — 실 Vertex 비용이 발생한다. 스모크는 `--help`까지만.

- [ ] **Step 4: 전체 검사**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 전부 통과.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/__main__.py worker/pyproject.toml
git commit -m "feat(worker): python -m silen_worker 진입점

스케줄러가 부를 수 있는 실행 경로를 연다. console script(silen-worker)도
등록하지만 정식 형태는 venv 파이썬을 직접 지목하는 python -m 이다."
```

---

## Task 6: 문서 — 실행·스케줄 등록 안내

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README에 파이프라인 실행 절 추가**

`README.md`의 "### 3. 검사" 절 **뒤에**(`> shadcn/ui는 첫 화면 작업 시 도입.` 줄 앞) 아래를 추가한다:

```markdown
### 4. 파이프라인 실행

워커 함수는 CLI로 구동한다. **주기 실행은 OS 스케줄러에 위임**한다(상주 데몬 없음).

```powershell
# 큐 소비 → 엔티티 추출 (실 Vertex 호출·비용)
worker\.venv\Scripts\python.exe -m silen_worker run-pending

# 차이 검출 → 서술 (실 Vertex 호출·비용). 기본 대상: 전체 사용자 × 각자 로컬 어제
worker\.venv\Scripts\python.exe -m silen_worker run-daily

# 일기 생성 (확정 차이 반영). 사람이 확인 UI에서 맞아요/아니에요를 누른 뒤 실행
worker\.venv\Scripts\python.exe -m silen_worker run-diary

# 특정 사용자·날짜만 (디버깅·재실행)
worker\.venv\Scripts\python.exe -m silen_worker run-daily --user <uuid> --date 2026-07-26
```

전제: Vertex ADC env 3종(`GOOGLE_GENAI_USE_VERTEXAI`·`GOOGLE_CLOUD_PROJECT`·`GOOGLE_CLOUD_LOCATION`).

**순서가 중요하다.** `run-daily`는 차이 카드를 준비만 하고, 일기는 사람이 확정한 차이만 녹인다:

```
run-daily (자정 이후)  →  사람이 확인 UI에서 확정  →  run-diary (그날 밤)
```

**재실행 안전:** 이미 서술된 차이는 LLM을 다시 부르지 않는다. 스케줄러가 자주 돌아도 새 차이에만 비용이 든다.

**종료 코드:** 전부 성공 `0`, 사용자 처리 실패가 하나라도 있으면 `1`.

#### 스케줄 등록 (사람이 실행)

Windows 작업 스케줄러 예시 — **아래는 안내이며 등록은 사람이 직접 한다.**

```powershell
# 5분마다 큐 소비
schtasks /create /tn "silen-run-pending" /sc minute /mo 5 ^
  /tr "C:\workspace\silen\worker\.venv\Scripts\python.exe -m silen_worker run-pending"

# 매일 00:30 차이 검출·서술
schtasks /create /tn "silen-run-daily" /sc daily /st 00:30 ^
  /tr "C:\workspace\silen\worker\.venv\Scripts\python.exe -m silen_worker run-daily"

# 매일 22:00 일기 생성
schtasks /create /tn "silen-run-diary" /sc daily /st 22:00 ^
  /tr "C:\workspace\silen\worker\.venv\Scripts\python.exe -m silen_worker run-diary"
```

작업 스케줄러는 작업의 "시작 위치"를 저장소 루트로 두고, ADC env가 필요한 작업은 사용자 계정 컨텍스트로 실행해야 한다.
```

- [ ] **Step 2: 저장소 구조 절에 CLI 한 줄 추가**

`README.md`의 저장소 구조 블록에서 `worker/src/silen_worker/db.py` 줄 **앞에** 추가:

```
worker/src/silen_worker/cli.py        # 파이프라인 CLI(run-pending·run-daily·run-diary)
```

- [ ] **Step 3: 전체 검사**

```powershell
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker
npx vitest run
```
Expected: 전부 통과(프론트는 이 기능과 무관하나 회귀 확인).

- [ ] **Step 4: 커밋**

```powershell
git add README.md
git commit -m "docs: 파이프라인 CLI 실행·스케줄 등록 안내

run-daily → 사람 확정 → run-diary 순서와 재실행 안전을 명시한다.
스케줄 등록 예시는 안내이며 실제 등록은 사람이 한다."
```

- [ ] **Step 5: 최종 보고**

작업을 마치면 `HANDOFF.md`의 "상태" 절을 갱신하고 커밋한다(무엇을 했는지·커밋 SHA·검증 결과·막힌 점). **push·merge는 하지 마라** — 사람이 한다.

---

## 완료 기준

- `python -m silen_worker --help`가 세 명령을 보여준다.
- `run-daily`가 detect→narrate 체인을 돌리고, **두 번 돌려도 LLM 호출이 늘지 않는다**(핵심 회귀 테스트 통과).
- 한 사용자의 실패가 다른 사용자 처리를 막지 않고, 실패가 있으면 exit 1.
- 대상 계산이 타임존별로 정확하다(단위 테스트).
- 로그에 본문·일기 텍스트가 없다.
- ruff + pytest(단위+통합) 전부 통과. 스키마 변경 없음.

## 이번 범위 밖

- 상주 데몬·`--watch` 폴링 · 사용자별 `diary_time` 정밀 스케줄 · 실패 알림/모니터링.
- `process_pending`의 `conn` 인터페이스 통일 · 새 도메인 로직 · 마이그레이션.
- 스케줄러 실제 등록(사람이 실행).
