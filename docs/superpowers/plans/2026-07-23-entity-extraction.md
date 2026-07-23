# 엔티티 추출 (Gemini Flash · 가드레일 · 병합) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 메모 텍스트에서 4종 엔티티를 뽑아 `entities`·`memory_entities`를 채우되, 환각을 가드레일로 막고 삭제를 트리거로 완전하게 하며, 실 LLM 없이도 파이프라인 전체가 스텁으로 검증되게 한다.

**Architecture:** 워커의 사소한 잡을 추출로 교체한다. 추출 로직(가드레일·병합)은 `LLMExtractor` 포트를 주입받는 순수 로직이라 스텁으로 단위·통합 테스트한다. 실 Gemini 클라이언트와 eval은 API 키가 있어야 하므로 마지막에 배치하고 명시적으로 게이트한다. "탐지=통계" 경계를 지킨다 — 추출은 신호 보강일 뿐 차이 판정이 아니다.

**Tech Stack:** Python 3.12 · psycopg · pgmq · Google `google-genai` SDK(Gemini Flash) · pytest

## Global Constraints

- 산출물은 **코드**다. `main` 직접 커밋 금지 — `feat/entity-extraction` 브랜치(생성됨).
- 커밋 메시지 `<type>(<scope>): <한국어 요약>`. scope는 `worker`·`db`·`eval`. `Co-Authored-By` 트레일러.
- **마이그레이션은 up/down을 같은 커밋에.** down은 `supabase/migrations/down/<타임스탬프>_<이름>.down.sql`.
- 타임스탬프는 `npx supabase migration new <name>` 생성값. `<ts1>`을 그 값으로 대체.
- 로컬 Supabase 스택 필요. **`db reset` 후 auth 502는 `supabase stop && start`로 복구.**
- 워커는 특권 역할로 psycopg 직접 접속. **모든 쿼리에 user_id 필터를 코드로 강제.**
- **프라이버시 필수(privacy.md·기획서):** Gemini는 **무학습 구성(유료 API/Vertex)**만. 무료 티어 금지. API 키는 환경변수(`GEMINI_API_KEY`), 코드·로그·커밋·큐 메시지에 안 실림. 기록 본문을 로그·APM에 안 남김(memory_id·카운트만).
- **환각 0%(ai-evals.md):** 추출된 name이 원문에 실재하는지 후검증. 없으면 폐기.
- **relation_type은 `'mentioned'`.** met/visited/did로 단정하지 않는다(과잉해석 금지).
- Python venv `worker\.venv`. 명령은 `worker\.venv\Scripts\python.exe` 직접 호출.
- 인증·삭제·RAG 변경이므로 병합 전 `/security-review`(privacy.md). 타인 이름 저장·삭제·본문 전송을 중점 점검.

## 전제 조건 — Gemini API 키

**현재 환경에 Gemini 키가 없다.** Task 1–3·6은 스텁으로 키 없이 완성·검증된다. **Task 4(실 Gemini 클라이언트)·5(eval)는 `GEMINI_API_KEY`(무학습 구성)가 있어야** 실행된다. 키가 없으면 Task 3까지 진행해 스텁 파이프라인을 병합하고, 키 확보 후 Task 4–5를 잇는다.

---

## File Structure

| 경로 | 책임 |
|------|------|
| `supabase/migrations/<ts1>_entity_extraction.sql` | relation_type에 `mentioned` 추가 + 고아 entity 삭제 트리거 |
| `worker/src/silen_worker/extraction/__init__.py` | |
| `worker/src/silen_worker/extraction/service.py` | 가드레일·정규화·추출 오케스트레이션(포트 주입) |
| `worker/src/silen_worker/extraction/gemini.py` | 실 Gemini `LLMExtractor` 구현(키 필요) |
| `worker/src/silen_worker/db.py`(수정) | entity·memory_entity upsert(스코프) |
| `worker/src/silen_worker/tasks/process.py`(수정) | 사소한 잡 → 추출 잡 |
| `worker/tests/test_extraction.py` | 가드레일·정규화 단위(LLM 없음) |
| `worker/tests/test_extraction_integration.py` | 스텁 추출기로 파이프라인·멱등·고아삭제·스코핑 |
| `evals/entities/` | 골든셋 픽스처 + 러너(키 필요) |

---

## Task 1: 스키마 — relation_type·고아 삭제 트리거

**Files:**
- Create: `supabase/migrations/<ts1>_entity_extraction.sql`, `supabase/migrations/down/<ts1>_entity_extraction.down.sql`
- Create: `worker/tests/test_entity_schema_integration.py`

**Interfaces:**
- Consumes: 기존 `entities`·`memory_entities`·`relations`
- Produces: relation_type `mentioned` 허용, 고아 entity 자동 삭제

- [ ] **Step 1: relation_type CHECK 제약 이름 확인**

```powershell
node -e "const{Client}=require('pg');const c=new Client({connectionString:'postgresql://postgres:postgres@127.0.0.1:54322/postgres'});c.connect().then(()=>c.query(`select conname from pg_constraint where conrelid='public.memory_entities'::regclass and contype='c'`)).then(r=>{console.log(r.rows);return c.end()})"
```

Expected: `memory_entities_relation_type_check` 류의 이름. 이 이름을 Step 2 마이그레이션에 쓴다(다르면 맞춘다).

- [ ] **Step 2: 마이그레이션 생성**

```powershell
npx supabase migration new entity_extraction
```

- [ ] **Step 3: up 스크립트 작성**

`supabase/migrations/<ts1>_entity_extraction.sql`:

```sql
-- 추출 링크는 met/visited/did로 단정하지 않는다 — "메모가 이 엔티티를
-- 언급했다"가 정직하다(과잉해석 금지). mentioned를 허용값에 추가한다.
alter table public.memory_entities
  drop constraint memory_entities_relation_type_check;
alter table public.memory_entities
  add constraint memory_entities_relation_type_check
  check (relation_type in ('met', 'visited', 'did', 'mentioned'));

-- 고아 entity 즉시 삭제. 링크가 사라진 entity가 다른 memory_entities·
-- relations 어디서도 참조되지 않으면 지운다. 타인 이름이 "지웠는데 남는"
-- 창을 원천 차단한다(privacy.md 삭제 완전성). 메모 삭제·계정 삭제·미래
-- 경로 모두에 균일하게 걸린다.
create function public.delete_orphan_entity() returns trigger
  language plpgsql
  security definer
  set search_path = ''
as $$
begin
  if not exists (
        select 1 from public.memory_entities where entity_id = old.entity_id
      )
     and not exists (
        select 1 from public.relations
         where source_entity_id = old.entity_id or target_entity_id = old.entity_id
      )
  then
    delete from public.entities where id = old.entity_id;
  end if;
  return old;
end;
$$;

create trigger on_memory_entity_deleted
  after delete on public.memory_entities
  for each row execute function public.delete_orphan_entity();
```

Step 1에서 확인한 제약 이름이 `memory_entities_relation_type_check`가 아니면 위 `drop constraint` 이름을 그 값으로 바꾼다.

- [ ] **Step 4: down 스크립트 작성**

`supabase/migrations/down/<ts1>_entity_extraction.down.sql`:

```sql
drop trigger if exists on_memory_entity_deleted on public.memory_entities;
drop function if exists public.delete_orphan_entity();
-- mentioned를 되돌리면 기존 데이터가 위반일 수 있어 실패할 수 있다(의도).
alter table public.memory_entities
  drop constraint memory_entities_relation_type_check;
alter table public.memory_entities
  add constraint memory_entities_relation_type_check
  check (relation_type in ('met', 'visited', 'did'));
```

- [ ] **Step 5: 통합 테스트 작성**

`worker/tests/test_entity_schema_integration.py`:

```python
import uuid

import pytest

from tests.conftest import seed_user, seed_memory, delete_user


def _mk_entity(conn, user_id, name):
    row = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'person', %s, %s) returning id::text",
        (user_id, name, name),
    ).fetchone()
    return row[0]


@pytest.mark.integration
def test_mentioned_relation_type가_허용된다(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "민수 생각남")
        ent = _mk_entity(conn, user, "민수")
        conn.execute(
            "insert into public.memory_entities (memory_id, entity_id, relation_type) "
            "values (%s, %s, 'mentioned')",
            (mem, ent),
        )
        row = conn.execute(
            "select relation_type from public.memory_entities where memory_id = %s",
            (mem,),
        ).fetchone()
        assert row[0] == "mentioned"
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_마지막_링크가_사라지면_entity도_삭제된다(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "민수랑 점심")
        ent = _mk_entity(conn, user, "민수")
        conn.execute(
            "insert into public.memory_entities (memory_id, entity_id, relation_type) "
            "values (%s, %s, 'mentioned')",
            (mem, ent),
        )
        # 링크 삭제 → entity가 고아 → 트리거가 삭제
        conn.execute("delete from public.memory_entities where entity_id = %s", (ent,))
        left = conn.execute("select 1 from public.entities where id = %s", (ent,)).fetchone()
        assert left is None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_다른_메모가_참조하면_entity는_유지된다(conn):
    user = seed_user(conn)
    try:
        mem1 = seed_memory(conn, user, "민수랑 점심")
        mem2 = seed_memory(conn, user, "민수 또 생각남")
        ent = _mk_entity(conn, user, "민수")
        conn.execute(
            "insert into public.memory_entities (memory_id, entity_id, relation_type) "
            "values (%s, %s, 'mentioned'), (%s, %s, 'mentioned')",
            (mem1, ent, mem2, ent),
        )
        # mem1의 링크만 삭제 → entity는 mem2가 아직 참조 → 유지
        conn.execute(
            "delete from public.memory_entities where memory_id = %s and entity_id = %s",
            (mem1, ent),
        )
        left = conn.execute("select 1 from public.entities where id = %s", (ent,)).fetchone()
        assert left is not None
    finally:
        delete_user(conn, user)
```

- [ ] **Step 6: 적용·실행**

```powershell
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
worker\.venv\Scripts\python.exe -m pytest worker -m integration -v
```

Expected: 스키마 통합 3건 + 기존 워커 통합 5건 통과.

- [ ] **Step 7: 뮤테이션 점검 — 트리거가 실제 방어선인지**

트리거를 잠시 비활성화하고 "마지막 링크 삭제 시 entity 삭제" 테스트가 깨지는지 본다.

```powershell
node -e "const{Client}=require('pg');const c=new Client({connectionString:'postgresql://postgres:postgres@127.0.0.1:54322/postgres'});c.connect().then(()=>c.query('alter table public.memory_entities disable trigger on_memory_entity_deleted')).then(()=>{console.log('disabled');return c.end()})"
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_entity_schema_integration.py -m integration -v
```

Expected: FAIL — "마지막 링크가 사라지면 entity도 삭제된다"가 깨진다(트리거 없으면 고아가 남는다).

복구:

```powershell
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
worker\.venv\Scripts\python.exe -m pytest worker -m integration
```

Expected: PASS.

- [ ] **Step 8: 커밋**

```powershell
git add supabase/migrations worker/tests/test_entity_schema_integration.py
git commit -m "feat(db): 엔티티 추출 스키마 — mentioned 관계·고아 삭제 트리거

추출 링크는 relation_type='mentioned'. met/visited/did로 단정하면
과잉해석이라 '메모가 언급했다'만 기록한다.

고아 entity를 memory_entities AFTER DELETE 트리거로 즉시 삭제한다.
링크가 사라진 entity가 다른 곳에서 참조되지 않으면 지워 '지웠는데
타인 이름이 남는' 창을 원천 차단한다(privacy.md).
뮤테이션 점검으로 트리거가 방어선임을 확인."
```

---

## Task 2: 추출 서비스 — 가드레일·정규화 (LLM 없음)

순수 로직을 먼저 만든다. LLM은 포트로 주입한다.

**Files:**
- Create: `worker/src/silen_worker/extraction/__init__.py`, `worker/src/silen_worker/extraction/service.py`, `worker/tests/test_extraction.py`

**Interfaces:**
- Consumes: 없음(순수)
- Produces:
  ```python
  EntityType = Literal["person", "place", "activity", "thing"]
  @dataclass
  class ExtractedEntity:
      type: EntityType
      name: str
      normalized_name: str
  class LLMExtractor(Protocol):
      def extract(self, text: str) -> list[dict]: ...  # [{"type","name"}] 원시
  def normalize_name(name: str) -> str
  def guardrail(candidates: list[dict], text: str) -> list[ExtractedEntity]
  ```

- [ ] **Step 1: 실패 테스트 작성**

`worker/tests/test_extraction.py`:

```python
from silen_worker.extraction.service import normalize_name, guardrail


def test_원문에_있는_이름은_통과한다():
    out = guardrail([{"type": "person", "name": "민수"}], "민수랑 점심 먹음")
    assert len(out) == 1
    assert out[0].type == "person"
    assert out[0].name == "민수"


def test_원문에_없는_이름은_폐기한다():
    # LLM이 "스벅"을 "스타벅스"로 확장 → 원문에 없으니 폐기(추출자이지 해석자 아님).
    out = guardrail([{"type": "place", "name": "스타벅스"}], "스벅에서 커피")
    assert out == []


def test_스키마_밖_type은_폐기한다():
    out = guardrail([{"type": "emotion", "name": "행복"}], "행복했다")
    assert out == []


def test_빈_후보는_빈_결과():
    assert guardrail([], "아무 텍스트") == []


def test_normalize는_보수적이다():
    # 공백 제거·소문자화 정도만. 과병합 금지.
    assert normalize_name("스타 벅스") == normalize_name("스타벅스")
    assert normalize_name("Cafe") == normalize_name("cafe")
    # 다른 이름은 다른 키(김민수 ≠ 민수).
    assert normalize_name("김민수") != normalize_name("민수")


def test_정규화된_이름이_결과에_담긴다():
    out = guardrail([{"type": "thing", "name": "김밥"}], "김밥 또 먹음")
    assert out[0].normalized_name == normalize_name("김밥")
```

- [ ] **Step 2: 실패 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_extraction.py -v
```

Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 구현 작성**

`worker/src/silen_worker/extraction/__init__.py`:

```python
"""엔티티 추출 — 신호 보강(LLM). 차이 판정은 detector(통계)의 몫이다."""
```

`worker/src/silen_worker/extraction/service.py`:

```python
"""추출 오케스트레이션·가드레일·정규화. LLM은 LLMExtractor 포트로 주입한다.
프레임워크·DB·Gemini를 모른다(순수 로직) — 여기 테스트를 집중한다.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

EntityType = Literal["person", "place", "activity", "thing"]
_VALID_TYPES = {"person", "place", "activity", "thing"}


@dataclass
class ExtractedEntity:
    type: str
    name: str
    normalized_name: str


class LLMExtractor(Protocol):
    def extract(self, text: str) -> list[dict]:
        """[{"type","name"}] 원시 후보를 반환한다. 가드레일 전."""
        ...


def normalize_name(name: str) -> str:
    """보수적 병합 키. 공백 제거·소문자화만. 과병합 금지 — 이 이상 손대지 않는다."""
    return name.replace(" ", "").lower()


def guardrail(candidates: list[dict], text: str) -> list[ExtractedEntity]:
    """원문에 실재하지 않는 name·스키마 밖 type을 폐기한다(환각 0%).
    추출자이지 해석자가 아니다 — 확장·추론된 이름은 원문에 없어 자동 탈락한다."""
    out: list[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()
    for c in candidates:
        etype = c.get("type")
        name = (c.get("name") or "").strip()
        if etype not in _VALID_TYPES or not name:
            continue
        if name not in text:
            continue
        key = (etype, normalize_name(name))
        if key in seen:
            continue
        seen.add(key)
        out.append(ExtractedEntity(type=etype, name=name, normalized_name=normalize_name(name)))
    return out
```

- [ ] **Step 4: 통과 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_extraction.py -v
worker\.venv\Scripts\python.exe -m ruff check worker
```

Expected: 6건 PASS, ruff 통과.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/extraction worker/tests/test_extraction.py
git commit -m "feat(worker): 추출 가드레일·정규화 (LLM 없음)

원문에 실재하지 않는 name·스키마 밖 type을 폐기해 환각을 막는다.
추출자이지 해석자가 아니다 — 확장·추론된 이름은 원문에 없어 탈락.
normalize_name은 보수적(공백·소문자만), 과병합 금지.
LLMExtractor 포트로 주입해 순수 로직을 Gemini 없이 테스트한다."
```

---

## Task 3: 저장소·파이프라인 배선 (스텁 LLM)

추출 결과를 DB에 멱등 저장하고, `process_pending`을 추출 잡으로 바꾼다. 스텁 추출기로 파이프라인 전체를 검증한다.

**Files:**
- Modify: `worker/src/silen_worker/db.py`, `worker/src/silen_worker/tasks/process.py`, `worker/tests/test_process.py`
- Create: `worker/tests/test_extraction_integration.py`

**Interfaces:**
- Consumes: Task 1 스키마, Task 2 서비스, A의 큐 래퍼
- Produces:
  ```python
  # db.py
  def upsert_entity(conn, user_id, entity_type, name, normalized_name) -> str  # entity_id
  def link_memory_entity(conn, memory_id, entity_id) -> None
  # process.py
  def process_pending(limit=10, extractor: LLMExtractor | None = None) -> list[str]
  ```

- [ ] **Step 1: 저장소 함수 추가**

`worker/src/silen_worker/db.py` 끝에 추가:

```python
def upsert_entity(
    conn: psycopg.Connection, user_id: str, entity_type: str, name: str, normalized_name: str
) -> str:
    """(user_id, entity_type, normalized_name) 자연키로 upsert. 멱등."""
    row = conn.execute(
        """
        insert into public.entities (user_id, entity_type, name, normalized_name)
        values (%s, %s, %s, %s)
        on conflict (user_id, entity_type, normalized_name) do update
          set normalized_name = excluded.normalized_name
        returning id::text
        """,
        (user_id, entity_type, name, normalized_name),
    ).fetchone()
    return row[0]


def link_memory_entity(conn: psycopg.Connection, memory_id: str, entity_id: str) -> None:
    """(memory_id, entity_id, relation_type) PK로 upsert. 재처리해도 중복 없음."""
    conn.execute(
        """
        insert into public.memory_entities (memory_id, entity_id, relation_type)
        values (%s, %s, 'mentioned')
        on conflict (memory_id, entity_id, relation_type) do nothing
        """,
        (memory_id, entity_id),
    )
```

`entities`의 `(user_id, entity_type, normalized_name)`는 이미 유니크 제약이 있다(20260722073820 마이그레이션). 없다면 이 태스크에서 추가한다 — `db reset` 후 `\d public.entities`로 확인.

- [ ] **Step 2: process_pending을 추출 잡으로 교체**

`worker/src/silen_worker/tasks/process.py`를 교체:

```python
"""메모 잡 소비 — 엔티티 추출. pgmq에서 읽어 메모 텍스트를 추출하고 저장한다.

일회성. 프로덕션 주기 실행은 범위 밖. 실패 시 삭제하지 않아 visibility
timeout으로 재시도, 상한 초과 시 데드레터.
"""

from silen_worker.db import connect, fetch_memory, upsert_entity, link_memory_entity
from silen_worker.extraction.service import LLMExtractor, guardrail
from silen_worker.queue import QUEUE, archive_message, delete_message, read_messages

VISIBILITY_TIMEOUT = 60  # 초. LLM 호출이 있어 A보다 넉넉히.
MAX_READS = 5


def process_pending(limit: int = 10, extractor: LLMExtractor | None = None) -> list[str]:
    """큐에서 최대 limit개 처리하고 처리한 memory_id를 반환한다.
    extractor는 LLMExtractor 포트. 테스트는 스텁, 프로덕션은 Gemini를 주입한다."""
    if extractor is None:
        from silen_worker.extraction.gemini import GeminiExtractor

        extractor = GeminiExtractor()

    processed: list[str] = []
    with connect() as conn:
        for msg_id, read_ct, payload in read_messages(conn, QUEUE, VISIBILITY_TIMEOUT, limit):
            try:
                memory = fetch_memory(conn, payload["memory_id"], payload["user_id"])
                if memory is None:
                    delete_message(conn, QUEUE, msg_id)
                    continue
                if memory.raw_text:
                    candidates = extractor.extract(memory.raw_text)
                    for ent in guardrail(candidates, memory.raw_text):
                        entity_id = upsert_entity(
                            conn, memory.user_id, ent.type, ent.name, ent.normalized_name
                        )
                        link_memory_entity(conn, memory.id, entity_id)
                processed.append(memory.id)
                delete_message(conn, QUEUE, msg_id)
            except Exception:
                if read_ct >= MAX_READS:
                    archive_message(conn, QUEUE, msg_id)
    return processed
```

- [ ] **Step 3: 기존 배관 테스트에 빈 스텁 주입**

`process_pending`이 이제 추출기를 요구한다. 기존 `test_process.py`는 추출기 없이 호출하므로 그대로면 `GeminiExtractor` 생성 → 키 없음 RuntimeError로 깨진다. 큐 배관만 검증하는 이 테스트들엔 **빈 추출기**를 주입한다(엔티티는 관심 밖).

`worker/tests/test_process.py` 상단에 추가:

```python
class _NoEntities:
    def extract(self, text):
        return []
```

그리고 세 곳의 `process_pending(limit=10)` 호출을 `process_pending(limit=10, extractor=_NoEntities())`로 바꾼다(`test_메모_생성부터_처리까지_배관이_돈다`, `test_메모가_삭제됐어도_메시지는_치워진다`). `test_삭제하지_않은_메시지는...`은 `process_pending`을 호출하지 않으므로 그대로 둔다.

- [ ] **Step 4: 스텁 통합 테스트 작성**

`worker/tests/test_extraction_integration.py`:

```python
import pytest

from silen_worker.queue import QUEUE, read_messages
from silen_worker.tasks.process import process_pending
from tests.conftest import seed_user, seed_memory, delete_user


class StubExtractor:
    """고정 후보를 반환하는 스텁. 실 Gemini 없이 파이프라인을 검증한다."""

    def __init__(self, candidates):
        self._candidates = candidates

    def extract(self, text):
        return self._candidates


def _entities_of(conn, user):
    return conn.execute(
        "select entity_type, name from public.entities where user_id = %s order by name",
        (user,),
    ).fetchall()


@pytest.mark.integration
def test_추출_결과가_entities_memory_entities로_저장된다(conn):
    conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "민수랑 김밥 먹음")  # 트리거가 큐에 넣음
        stub = StubExtractor(
            [{"type": "person", "name": "민수"}, {"type": "thing", "name": "김밥"}]
        )
        processed = process_pending(limit=10, extractor=stub)

        assert mem in processed
        rows = _entities_of(conn, user)
        assert ("person", "민수") in rows
        assert ("thing", "김밥") in rows
        link_count = conn.execute(
            "select count(*)::int from public.memory_entities where memory_id = %s", (mem,)
        ).fetchone()[0]
        assert link_count == 2
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_환각_후보는_저장되지_않는다(conn):
    conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "스벅에서 커피")
        stub = StubExtractor([{"type": "place", "name": "스타벅스"}])  # 원문에 없음
        process_pending(limit=10, extractor=stub)
        assert _entities_of(conn, user) == []
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_재처리해도_중복이_생기지_않는다(conn):
    conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "민수 또 봄")
        stub = StubExtractor([{"type": "person", "name": "민수"}])
        process_pending(limit=10, extractor=stub)
        # 같은 메모를 다시 큐에 넣어 재처리
        conn.execute("select pgmq.send(%s, %s)", (QUEUE, f'{{"memory_id":"{mem}","user_id":"{user}"}}'))
        process_pending(limit=10, extractor=stub)

        ent_count = conn.execute(
            "select count(*)::int from public.entities where user_id = %s", (user,)
        ).fetchone()[0]
        link_count = conn.execute(
            "select count(*)::int from public.memory_entities where memory_id = %s", (mem,)
        ).fetchone()[0]
        assert ent_count == 1
        assert link_count == 1
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_메모_삭제시_고아_entity가_사라진다(conn):
    conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "민수 혼자 언급")
        stub = StubExtractor([{"type": "person", "name": "민수"}])
        process_pending(limit=10, extractor=stub)
        assert len(_entities_of(conn, user)) == 1

        conn.execute("delete from public.memories where id = %s", (mem,))  # 링크 CASCADE → 트리거
        assert _entities_of(conn, user) == []
    finally:
        delete_user(conn, user)
```

- [ ] **Step 5: 실행**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -m integration -v
```

Expected: 스키마 3 + 기존 5(빈 스텁 주입) + 추출 4 = 12건 PASS. (아직 Gemini 미주입 — 스텁만)

- [ ] **Step 6: 단위 분리·ruff**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration"
worker\.venv\Scripts\python.exe -m ruff check worker
```

Expected: 단위(test_time 7 + test_extraction 6)만 DB 없이 통과, ruff 통과.

- [ ] **Step 7: 커밋**

```powershell
git add worker/src/silen_worker/db.py worker/src/silen_worker/tasks/process.py worker/tests/test_process.py worker/tests/test_extraction_integration.py
git commit -m "feat(worker): 추출 파이프라인 배선 (스텁 LLM)

process_pending의 사소한 잡을 추출 잡으로 교체. 메모 텍스트를 추출기
포트로 넘기고, 가드레일 통과분을 entities·memory_entities에 멱등 upsert.

스텁 추출기로 파이프라인 전체를 검증: 저장·환각 폐기·재처리 멱등·
메모 삭제 시 고아 삭제. 실 Gemini는 주입만 바꾸면 된다."
```

---

## Task 4: Gemini 클라이언트 (키 필요)

**⚠️ 전제:** `GEMINI_API_KEY`(무학습 구성)가 있어야 한다. 없으면 이 태스크를 건너뛰고 스텁 파이프라인(Task 3)을 병합한 뒤, 키 확보 후 진행한다.

**Files:**
- Create: `worker/src/silen_worker/extraction/gemini.py`
- Modify: `worker/pyproject.toml`(google-genai 의존성)

**Interfaces:**
- Consumes: Task 2 `LLMExtractor` 포트
- Produces: `GeminiExtractor` 구현

- [ ] **Step 1: SDK API 확인 (드리프트 주의)**

Gemini SDK·구조화 출력 API는 바뀌었을 수 있다. 구현 전 Google 공식 문서를 확인한다.

```powershell
# google-genai(신규 SDK) 구조화 출력·무학습 구성 문서 확인
```

WebFetch: `https://ai.google.dev/gemini-api/docs/structured-output` — "Extract the Python google-genai SDK call for JSON structured output with response_schema, and the model id for Gemini Flash". 그리고 데이터 거버넌스(무학습): `https://ai.google.dev/gemini-api/terms` — "Extract whether paid-tier API inputs are used for training and how to ensure no-training".

**무학습 구성이 확인 안 되면 중단하고 사람에게 보고한다.** 이건 협상 불가 조건이다.

- [ ] **Step 2: 의존성 추가**

`worker/pyproject.toml`의 `dependencies`에 `google-genai`를 추가(Step 1에서 확인한 정확한 패키지명).

```powershell
worker\.venv\Scripts\python.exe -m pip install -e "worker[dev]"
```

- [ ] **Step 3: GeminiExtractor 작성**

`worker/src/silen_worker/extraction/gemini.py` — Step 1에서 확인한 API로 작성. 골격:

```python
"""실 Gemini Flash 추출기. 무학습 구성(유료 API/Vertex)만 사용한다.
API 키는 환경변수. 본문은 처리용이며 우리 로그에 남기지 않는다.
"""

import os

# from google import genai  # Step 1에서 확인한 정확한 import

_PROMPT = (
    "다음 텍스트에 등장하는 사람·장소·활동·사물을 뽑아라. "
    "텍스트에 없는 것을 지어내지 마라. 추론·해석·감정 판단을 하지 마라. "
    "이름은 텍스트에 나타난 형태의 기본형으로(조사 제거). "
    "엔티티가 없으면 빈 배열."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["person", "place", "activity", "thing"]},
                    "name": {"type": "string"},
                },
                "required": ["type", "name"],
            },
        }
    },
    "required": ["entities"],
}


class GeminiExtractor:
    def __init__(self) -> None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY가 없다 — 무학습 구성 유료 API 키 필요")
        # self._client = genai.Client(api_key=api_key)  # Step 1 확인 API

    def extract(self, text: str) -> list[dict]:
        # Step 1에서 확인한 구조화 출력 호출.
        # 응답 JSON의 entities 배열을 그대로 반환(가드레일이 뒤에서 검증).
        # 타임아웃·재시도(지수 백오프)·비용 상한 인지(backend.md).
        ...
```

Step 1의 실제 API로 `__init__`·`extract`를 완성한다.

- [ ] **Step 4: 실 Gemini 스모크 (키 있을 때)**

```powershell
$env:GEMINI_API_KEY = "<무학습 구성 키>"
worker\.venv\Scripts\python.exe -c "from silen_worker.extraction.gemini import GeminiExtractor; print(GeminiExtractor().extract('민수랑 김밥 먹고 그 카페 감'))"
```

Expected: `[{'type':'person','name':'민수'}, {'type':'thing','name':'김밥'}, {'type':'place','name':'카페'}]` 류. 한국어 4종이 뽑히는지 육안 확인.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/extraction/gemini.py worker/pyproject.toml worker/pyproject... package-lock 등
git commit -m "feat(worker): Gemini Flash 추출기 (무학습 구성)

무학습 유료 API로 4종 엔티티를 구조화 출력으로 받는다. 지어내지
말라는 프롬프트 + 스키마 강제 + (뒤단) 가드레일로 환각을 막는다.
API 키는 환경변수, 본문은 로그에 안 남긴다."
```

---

## Task 5: eval 골든셋 (키 필요)

**⚠️ 전제:** Task 4와 동일. 실 Gemini 호출이 필요하다.

**Files:**
- Create: `evals/entities/fixtures.json`, `evals/entities/run.py`

**Interfaces:**
- Consumes: Task 4 `GeminiExtractor`, Task 2 `guardrail`
- Produces: eval 러너(CI 게이트 후보)

- [ ] **Step 1: 골든셋 픽스처 작성**

`evals/entities/fixtures.json` — ai-evals.md 필수 케이스. 기록 본문을 커밋에 넣지 않는다는 git.md 원칙상, 픽스처는 **합성 예시**(실사용자 데이터 아님)로 작성한다.

```json
{
  "cases": [
    {"name": "hallucination-expansion", "text": "스벅에서 커피",
     "must_not_contain": ["스타벅스"], "reason": "확장은 원문에 없어 폐기"},
    {"name": "empty-no-entities", "text": "그냥 그런 하루",
     "expected_count_max": 0, "reason": "억지 생성 X"},
    {"name": "korean-particle", "text": "민수랑 점심 먹음",
     "must_contain": [{"type": "person", "name": "민수"}], "reason": "조사 제거"},
    {"name": "conservative-merge", "text": "김민수랑 민수는 다른 사람",
     "distinct_names": ["김민수", "민수"], "reason": "과병합 X"},
    {"name": "four-types", "text": "카페에서 요가하고 김밥 먹고 지은이 만남",
     "must_contain": [
        {"type": "place", "name": "카페"}, {"type": "activity", "name": "요가"},
        {"type": "thing", "name": "김밥"}, {"type": "person", "name": "지은"}
     ]}
  ]
}
```

- [ ] **Step 2: 러너 작성**

`evals/entities/run.py` — 각 케이스를 `GeminiExtractor` + `guardrail`로 돌려 기대 속성을 검사하고, 환각율·근거정합율·false positive율을 리포트한다. 실패 시 종료 코드 1(CI 게이트).

(구현: fixtures 로드 → 각 text에 대해 guardrail(extractor.extract(text), text) → must_contain/must_not_contain/count 검사 → 집계 출력.)

- [ ] **Step 3: 실행 (키 있을 때)**

```powershell
$env:GEMINI_API_KEY = "<키>"
worker\.venv\Scripts\python.exe evals/entities/run.py
```

Expected: 모든 케이스 통과, 환각율 0%. 한국어 4종 품질이 부족하면 프롬프트 보강 또는 Pro 승급 검토(스펙 §14).

- [ ] **Step 4: 커밋**

```powershell
git add evals/entities
git commit -m "feat(eval): 엔티티 추출 골든셋

환각 유혹·빈 텍스트·조사·보수적 병합·4종 분류를 실 Gemini로 검증.
근거 없는 사실 0%를 게이트한다(ai-evals.md). 픽스처는 합성 예시."
```

---

## Task 6: 문서 (키 불필요)

**Files:**
- Modify: `supabase/README.md`, `README.md`, `.env.example`

- [ ] **Step 1: 환경변수 안내**

`.env.example`에 추가(값 비움):

```
# Gemini — 무학습 구성(유료 API/Vertex). 무료 티어 금지.
GEMINI_API_KEY=
```

- [ ] **Step 2: supabase/README에 엔티티 메모**

큐 절 아래에 추가:

```markdown
## 엔티티

- 워커가 메모 텍스트에서 4종(person·place·activity·thing)을 추출해
  entities·memory_entities를 채운다. relation_type은 'mentioned'
  (met/visited/did로 단정하지 않는다).
- 추출 name이 원문에 없으면 폐기(환각 0%). 추출자이지 해석자가 아니다.
- 고아 entity는 memory_entities AFTER DELETE 트리거로 즉시 삭제 —
  타인 이름이 남지 않게.
```

- [ ] **Step 3: 전체 검사**

```powershell
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
```

Expected: 통과. (pytest는 스텁 통합 포함 — 키 없이 도는 것만)

- [ ] **Step 4: 커밋**

```powershell
git add supabase/README.md README.md .env.example
git commit -m "docs: 엔티티 추출 안내와 Gemini 무학습 구성 환경변수"
```

- [ ] **Step 5: 보안 리뷰**

인증·삭제·본문 전송 변경이므로 `/security-review`(privacy.md). 타인 이름 저장·고아 삭제·본문 로깅·Gemini 전송을 중점 확인.

- [ ] **Step 6: 브랜치 마무리**

`/superpowers:finishing-a-development-branch`. rebase 후 `merge --no-ff`, squash 금지.

---

## 완료 기준

- relation_type `mentioned` 허용, 고아 entity 트리거로 즉시 삭제(뮤테이션 점검 확인)
- 가드레일이 원문에 없는 name 폐기, 보수적 정규화
- 스텁 파이프라인: 저장·환각 폐기·멱등·고아삭제·스코핑 통합 통과
- (키 있을 때) Gemini Flash가 한국어 4종 추출, eval 골든셋 통과
- 단위 테스트는 DB·키 없이 통과
- `ruff`·`pytest`·`supabase db reset` 통과

## 이번 범위 밖
- 유저 확정 병합 UI (프론트)
- detector(first-occurrence·freq-shift) — 통계, 엔티티가 쌓인 뒤
- 백필(기존 메모) — 실데이터 시점 일회성
- relations(엔티티 그래프)·재추출 링크 동기화
