# 워커 파이프라인 밑감 (pgmq + 트리거 + Python 워커) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 메모가 저장되면 트리거가 pgmq에 메시지를 넣고, Python 워커가 그걸 소비해 user 스코프로 메모를 읽고 메시지를 지우는 배관을 세운다. LLM·도메인 로직 없음 — 배관이 돈다는 것만 증명한다.

**Architecture:** 스펙(`docs/superpowers/specs/2026-07-23-worker-pipeline-design.md`)을 옮긴다. 가장 위험한 가정(pgmq가 로컬 CLI에 있는가)을 Task 1에서 먼저 검증한다. 이후 트리거(DB) → 워커 DB 계층(psycopg) → 워커 소비(process_pending) 순. 워커는 특권 역할로 RLS 밖에서 돌므로 user_id 필터를 코드로 강제하는 것을 테스트로 고정한다.

**Tech Stack:** pgmq · PostgreSQL 트리거 · Python 3.12 · psycopg 3 · pytest · Vitest(통합)

## Global Constraints

- 산출물은 **코드**다. `main` 직접 커밋 금지 — `feat/worker-pipeline` 브랜치(생성됨).
- 선행: 기록 백엔드·auth·RLS·GRANT가 `main`에 병합됨(확인됨).
- 커밋 메시지 `<type>(<scope>): <한국어 요약>`. scope는 `worker`·`db`. `Co-Authored-By` 트레일러.
- **마이그레이션은 up/down을 같은 커밋에.** down은 `supabase/migrations/down/<타임스탬프>_<이름>.down.sql`.
- 타임스탬프는 `npx supabase migration new <name>` 생성값. 이 문서의 `<ts1>`·`<ts2>`를 그 값으로 대체.
- 로컬 Supabase 스택 필요. **`db reset` 후 auth 502는 `supabase stop && start`로 복구**(supabase/README).
- 워커는 **특권 Postgres 역할**(로컬 `postgres`)로 psycopg 직접 접속 → RLS 우회. **모든 쿼리에 user_id 필터를 코드로 강제**(스펙 §8).
- 큐 이름 `memory_jobs`. 메시지 `{memory_id, user_id}`. 본문(raw_text)은 메시지에 싣지 않는다.
- Python venv는 `worker\.venv`(auth 때 3.12로 생성됨). 명령은 `worker\.venv\Scripts\python.exe` 직접 호출.
- 인증·삭제·RAG 변경 아님 → `/security-review`는 필수 아님. 단 워커 스코핑이 새 격리 표면이라 병합 전 스코핑 테스트 통과를 확인한다.

---

## File Structure

| 경로 | 책임 |
|------|------|
| `supabase/migrations/<ts1>_pgmq_queue.sql` | pgmq 확장 + `memory_jobs` 큐 |
| `supabase/migrations/<ts2>_enqueue_trigger.sql` | memories AFTER INSERT → pgmq.send |
| `lib/repositories/queue.integration.test.ts` | 트리거가 메시지를 넣는지(TS 통합) |
| `worker/src/silen_worker/db.py` | psycopg 접속 + `fetch_memory`(스코프) |
| `worker/src/silen_worker/queue.py` | pgmq read/delete/archive 래퍼 |
| `worker/src/silen_worker/tasks/__init__.py` `worker/src/silen_worker/tasks/process.py` | `process_pending` |
| `worker/tests/test_worker_db.py` | 스코핑(통합) |
| `worker/tests/test_process.py` | 소비 roundtrip·at-least-once(통합) |
| `worker/tests/conftest.py` | 테스트 시드(auth.users·memory) 헬퍼 |

---

## Task 1: pgmq 검증 + 큐 마이그레이션

**가장 위험한 가정**을 먼저 확인한다: pgmq가 로컬 CLI에 있고 마이그레이션으로 재생되는가. 없으면 수제 jobs 테이블로 폴백(스펙 §4).

**Files:**
- Create: `supabase/migrations/<ts1>_pgmq_queue.sql`, `supabase/migrations/down/<ts1>_pgmq_queue.down.sql`

**Interfaces:**
- Consumes: 없음
- Produces: pgmq 확장, 큐 `memory_jobs`. 함수 `pgmq.send/read/delete/archive`

- [ ] **Step 1: pgmq 존재를 즉석 확인**

마이그레이션을 쓰기 전에 로컬 DB에서 pgmq API가 실제로 되는지 확인한다.

```powershell
node -e "const{Client}=require('pg');const c=new Client({connectionString:'postgresql://postgres:postgres@127.0.0.1:54322/postgres'});c.connect().then(()=>c.query('create extension if not exists pgmq')).then(()=>c.query(`select pgmq.create('probe_q')`)).then(()=>c.query(`select pgmq.send('probe_q','{""x"":1}')`)).then(()=>c.query('select msg_id, message from pgmq.read($1,$2,$3)',['probe_q',30,1])).then(r=>{console.log('read:',JSON.stringify(r.rows));return c.query(`select pgmq.drop_queue('probe_q')`)}).then(()=>{console.log('pgmq OK');return c.end()}).catch(e=>{console.error('pgmq FAIL:',e.message);process.exit(1)})"
```

Expected: `read: [{"msg_id":...,"message":{"x":1}}]` 후 `pgmq OK`.

**FAIL이면 중단하고 폴백 결정.** `extension "pgmq" is not available`이면 로컬 이미지에 pgmq가 없다 — 스펙 §4의 수제 jobs 테이블로 전환하고 이 계획을 다시 검토한다. 함수명이 다르면(`pgmq.create_queue` 등) 아래 마이그레이션을 그 이름으로 맞춘다.

- [ ] **Step 2: 마이그레이션 생성**

```powershell
npx supabase migration new pgmq_queue
```

출력 타임스탬프를 `<ts1>`로 쓴다.

- [ ] **Step 3: up 스크립트 작성**

`supabase/migrations/<ts1>_pgmq_queue.sql`:

```sql
-- 비동기 큐. Next(적재)·Python 워커(소비)가 DB로만 통신한다(backend.md).
-- pgmq는 같은 Postgres 안에 있어 적재가 메모 insert와 같은 트랜잭션에 묶인다.
create extension if not exists pgmq;

-- 메모 처리 잡 큐. 메시지는 {memory_id, user_id}.
select pgmq.create('memory_jobs');
```

- [ ] **Step 4: down 스크립트 작성**

`supabase/migrations/down/<ts1>_pgmq_queue.down.sql`:

```sql
-- 큐를 지운다. 확장은 다른 큐가 있을 수 있어 남긴다(보수적).
select pgmq.drop_queue('memory_jobs');
```

- [ ] **Step 5: 적용·재생 확인**

```powershell
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
```

Expected: `Applying migration <ts1>_pgmq_queue.sql...`, `db reset` 종료 코드 0.

- [ ] **Step 6: 커밋**

```powershell
git add supabase/migrations
git commit -m "feat(db): pgmq 큐 memory_jobs

비동기 큐를 pgmq로 세운다. Next(적재)·Python 워커(소비)가 DB로만
통신하며, in-DB라 적재가 메모 insert와 같은 트랜잭션에 묶인다.

가정 검증: pgmq가 로컬 CLI 스택에 있고 마이그레이션으로 재생된다."
```

---

## Task 2: 적재 트리거

메모가 생기면 트리거가 큐에 메시지를 넣는다. 앱은 탐지를 모른다.

**Files:**
- Create: `supabase/migrations/<ts2>_enqueue_trigger.sql`, `supabase/migrations/down/<ts2>_enqueue_trigger.down.sql`, `lib/repositories/queue.integration.test.ts`

**Interfaces:**
- Consumes: Task 1의 큐, auth의 `testSupport`
- Produces: `memories` AFTER INSERT 트리거

- [ ] **Step 1: 마이그레이션 생성**

```powershell
npx supabase migration new enqueue_trigger
```

- [ ] **Step 2: up 스크립트 작성**

`supabase/migrations/<ts2>_enqueue_trigger.sql`:

```sql
-- 메모가 생기면 처리 잡을 큐에 넣는다. 앱은 탐지를 모르고 트리거가
-- 결합을 대신한다(2자산이 큐+DB로만 통신). insert와 같은 트랜잭션이라
-- 메모가 커밋되면 메시지도 반드시 들어간다(유령·유실 잡 없음).
-- 본문(raw_text)은 싣지 않는다 — memory_id만. 워커가 DB에서 읽는다.
create function public.enqueue_memory_job() returns trigger
  language plpgsql
  security definer
  set search_path = ''
as $$
begin
  perform pgmq.send('memory_jobs', jsonb_build_object(
    'memory_id', new.id,
    'user_id', new.user_id
  ));
  return new;
end;
$$;

create trigger on_memory_created
  after insert on public.memories
  for each row execute function public.enqueue_memory_job();
```

- [ ] **Step 3: down 스크립트 작성**

`supabase/migrations/down/<ts2>_enqueue_trigger.down.sql`:

```sql
drop trigger if exists on_memory_created on public.memories;
drop function if exists public.enqueue_memory_job();
```

- [ ] **Step 4: 통합 테스트 작성 (TS)**

`lib/repositories/queue.integration.test.ts`:

```ts
import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { Client } from "pg";
import { adminClient } from "./testSupport";
import type { SupabaseClient } from "@supabase/supabase-js";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let admin: SupabaseClient;
let db: Client;
let user: string;

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
  const { data } = await admin.auth.admin.createUser({
    email: "queue-test@example.com",
    email_confirm: true,
  });
  user = data.user!.id;
});

afterAll(async () => {
  await admin.auth.admin.deleteUser(user);
  await db.end();
});

// 큐를 비워 테스트 간 간섭을 없앤다.
beforeEach(async () => {
  await db.query("select pgmq.purge_queue('memory_jobs')");
});

describe("적재 트리거", () => {
  it("메모가 생기면 큐에 {memory_id, user_id} 메시지가 들어간다", async () => {
    const { data } = await admin
      .from("memories")
      .insert({ user_id: user, source_type: "manual", memory_type: "moment" })
      .select("id")
      .single();
    const memoryId = data!.id;

    const res = await db.query(
      "select message from pgmq.read('memory_jobs', 30, 10)",
    );
    const messages = res.rows.map((r) => r.message);
    expect(messages).toContainEqual({ memory_id: memoryId, user_id: user });
  });

  it("메모가 없으면 메시지도 없다", async () => {
    const res = await db.query("select msg_id from pgmq.read('memory_jobs', 30, 10)");
    expect(res.rowCount).toBe(0);
  });
});
```

- [ ] **Step 5: 적용·실행**

```powershell
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
npm run test:integration
```

Expected: 기존 통합 + 트리거 2건 통과. `pgmq.purge_queue`/`pgmq.read` 함수명이 다르면 Task 1 Step 1에서 확인한 이름으로 맞춘다.

- [ ] **Step 6: 커밋**

```powershell
git add supabase/migrations lib/repositories/queue.integration.test.ts
git commit -m "feat(db): 메모 적재 트리거

memories AFTER INSERT가 pgmq.send로 처리 잡을 넣는다. 앱은 탐지를
모르고 트리거가 결합을 대신한다. insert와 같은 트랜잭션이라 메모가
커밋되면 메시지도 반드시 들어간다. 메시지엔 memory_id만, 본문은 안 싣는다."
```

---

## Task 3: 워커 DB 계층 + 스코핑

psycopg로 특권 역할 접속, `fetch_memory`가 user_id로 필터. **워커의 유일한 격리 방어선**을 테스트로 고정한다.

**Files:**
- Create: `worker/src/silen_worker/db.py`, `worker/src/silen_worker/queue.py`, `worker/tests/__init__.py`, `worker/tests/conftest.py`, `worker/tests/test_worker_db.py`
- Modify: `worker/pyproject.toml`(psycopg 의존성·pytest 마커)

**Interfaces:**
- Consumes: Task 1·2의 스키마·큐
- Produces: `connect()`, `fetch_memory(conn, memory_id, user_id) -> Memory | None`, `read_messages/delete_message/archive_message`

- [ ] **Step 1: 의존성·마커 추가**

`worker/pyproject.toml`의 `dependencies`에 `psycopg[binary]`를 추가하고, pytest 마커를 등록한다.

```toml
[project]
name = "silen-worker"
version = "0.0.0"
description = "실은 차이 탐지·서술 워커"
requires-python = ">=3.11"
dependencies = [
    "numpy",
    "scipy",
    "pandas",
    "tzdata",
    "psycopg[binary]",
]

[project.optional-dependencies]
dev = ["pytest", "ruff"]

[tool.pytest.ini_options]
# "."(워커 루트)을 넣어 `from tests.conftest import ...`가 해석되게 한다.
# tests/__init__.py와 함께 tests를 패키지로 만든다.
pythonpath = ["src", "."]
testpaths = ["tests"]
markers = [
    "integration: 로컬 Supabase 스택이 떠 있어야 하는 테스트",
]

[tool.ruff]
line-length = 100
```

설치:

```powershell
worker\.venv\Scripts\python.exe -m pip install -e "worker[dev]"
```

Expected: `Successfully installed ... psycopg ...`

- [ ] **Step 2: 큐 래퍼 작성**

`worker/src/silen_worker/queue.py`:

```python
"""pgmq 래퍼. 큐 API를 한곳에 모아 detector·추출 잡이 재사용한다."""

from typing import Any

import psycopg

QUEUE = "memory_jobs"


def read_messages(
    conn: psycopg.Connection, queue: str, vt: int, qty: int
) -> list[tuple[int, int, dict[str, Any]]]:
    """(msg_id, read_ct, message) 목록을 반환한다. vt초 동안 다른 소비자에게 숨긴다."""
    rows = conn.execute(
        "select msg_id, read_ct, message from pgmq.read(%s, %s, %s)",
        (queue, vt, qty),
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def delete_message(conn: psycopg.Connection, queue: str, msg_id: int) -> None:
    conn.execute("select pgmq.delete(%s, %s)", (queue, msg_id))


def archive_message(conn: psycopg.Connection, queue: str, msg_id: int) -> None:
    conn.execute("select pgmq.archive(%s, %s)", (queue, msg_id))
```

- [ ] **Step 3: DB 계층 작성**

`worker/src/silen_worker/db.py`:

```python
"""워커 DB 접근. 특권 역할(로컬 postgres)로 psycopg 직접 접속해 RLS를 우회한다.
RLS가 막아주지 않으므로 모든 조회에 user_id 필터를 코드로 강제한다(스펙 §8).
"""

import os
from dataclasses import dataclass

import psycopg

DEFAULT_DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


def dsn() -> str:
    return os.environ.get("SUPABASE_DB_URL", DEFAULT_DSN)


def connect() -> psycopg.Connection:
    return psycopg.connect(dsn(), autocommit=True)


@dataclass
class Memory:
    id: str
    user_id: str
    raw_text: str | None


def fetch_memory(conn: psycopg.Connection, memory_id: str, user_id: str) -> Memory | None:
    """메모를 조회한다. user_id로도 필터해 교차 사용자 접근을 코드로 막는다.
    잠긴/삭제된 메모는 제외한다(is_locked·deleted_at)."""
    row = conn.execute(
        "select id::text, user_id::text, raw_text "
        "from public.memories "
        "where id = %s and user_id = %s and deleted_at is null and is_locked = false",
        (memory_id, user_id),
    ).fetchone()
    if row is None:
        return None
    return Memory(id=row[0], user_id=row[1], raw_text=row[2])
```

- [ ] **Step 4: 테스트 시드 헬퍼 작성**

`worker/tests/__init__.py` (빈 파일 — tests를 패키지로 만들어 `from tests.conftest` 임포트가 되게 한다):

```python
```

`worker/tests/conftest.py`:

```python
"""통합 테스트 공용. auth.users를 직접 시드하고(트리거가 public.users 생성),
메모를 만든다. 로컬 postgres 슈퍼유저로 접속하므로 auth 스키마에 쓸 수 있다."""

import uuid

import psycopg
import pytest

from silen_worker.db import dsn


@pytest.fixture
def conn() -> psycopg.Connection:
    c = psycopg.connect(dsn(), autocommit=True)
    yield c
    c.close()


def seed_user(conn: psycopg.Connection) -> str:
    """최소 auth.users 행을 만든다. handle_new_user 트리거가 public.users를 만든다."""
    user_id = str(uuid.uuid4())
    conn.execute(
        """
        insert into auth.users
          (instance_id, id, aud, role, email, encrypted_password,
           email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
           created_at, updated_at, confirmation_token, email_change,
           email_change_token_new, recovery_token)
        values
          ('00000000-0000-0000-0000-000000000000', %s, 'authenticated',
           'authenticated', %s, '', now(),
           '{"provider":"email","providers":["email"]}', '{}',
           now(), now(), '', '', '', '')
        """,
        (user_id, f"worker-{user_id[:8]}@example.com"),
    )
    return user_id


def seed_memory(conn: psycopg.Connection, user_id: str, text: str | None = "메모") -> str:
    row = conn.execute(
        "insert into public.memories (user_id, raw_text, source_type, memory_type) "
        "values (%s, %s, 'manual', 'moment') returning id::text",
        (user_id, text),
    ).fetchone()
    return row[0]


def delete_user(conn: psycopg.Connection, user_id: str) -> None:
    # auth.users 삭제가 CASCADE로 public.users·memories를 지운다.
    conn.execute("delete from auth.users where id = %s", (user_id,))
```

**auth.users 컬럼이 로컬 GoTrue 버전과 달라 insert가 실패하면**, 실패 메시지의 NOT NULL 컬럼을 위 목록에 추가한다. 이는 알려진 취약 지점이다.

- [ ] **Step 5: 스코핑 테스트 작성**

`worker/tests/test_worker_db.py`:

```python
import pytest

from silen_worker.db import fetch_memory
from tests.conftest import seed_user, seed_memory, delete_user


@pytest.mark.integration
def test_본인_메모는_조회된다(conn):
    user = seed_user(conn)
    try:
        memory_id = seed_memory(conn, user, "본인 메모")
        result = fetch_memory(conn, memory_id, user)
        assert result is not None
        assert result.id == memory_id
        assert result.raw_text == "본인 메모"
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_남의_user_id로는_조회되지_않는다(conn):
    # 워커가 user_id 필터를 지키는지 — 교차 사용자 격리의 코드 방어선.
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        memory_id = seed_memory(conn, alice, "앨리스 메모")
        assert fetch_memory(conn, memory_id, bob) is None
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)
```

- [ ] **Step 6: 실행**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -m integration -v
```

Expected: 스코핑 2건 PASS. `auth.users` insert 실패 시 Step 4 주석대로 컬럼 보강.

- [ ] **Step 7: 단위 테스트가 DB를 요구하지 않는지 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration" -v
```

Expected: 기존 `test_time.py`의 7건만 실행되고 통과(DB 불필요).

- [ ] **Step 8: ruff**

```powershell
worker\.venv\Scripts\python.exe -m ruff check worker
```

Expected: `All checks passed!`

- [ ] **Step 9: 커밋**

```powershell
git add worker/pyproject.toml worker/src/silen_worker/db.py worker/src/silen_worker/queue.py worker/tests/__init__.py worker/tests/conftest.py worker/tests/test_worker_db.py
git commit -m "feat(worker): DB 계층·pgmq 래퍼·스코핑 테스트

psycopg로 특권 역할 접속. fetch_memory가 user_id로 필터해 교차 사용자
접근을 코드로 막는다 — 워커의 유일한 격리 방어선(RLS 밖)이라
엔티티 추출 전에 먼저 테스트로 고정한다.
pytest integration 마커로 DB 테스트와 순수 단위를 분리."
```

---

## Task 4: 워커 소비 — process_pending

**Files:**
- Create: `worker/src/silen_worker/tasks/__init__.py`, `worker/src/silen_worker/tasks/process.py`, `worker/tests/test_process.py`

**Interfaces:**
- Consumes: Task 3의 `connect`·`fetch_memory`·큐 래퍼
- Produces: `process_pending(limit=10) -> list[str]`

- [ ] **Step 1: process_pending 작성**

`worker/src/silen_worker/tasks/__init__.py`:

```python
"""워커 잡 진입점."""
```

`worker/src/silen_worker/tasks/process.py`:

```python
"""메모 잡 소비. pgmq에서 읽어 메모를 스코프 조회하고 메시지를 지운다.

일회성 — 프로덕션에서 어떻게 주기 실행할지(데몬·cron)는 범위 밖.
이번 슬라이스의 잡은 사소하다(조회 후 삭제). 엔티티 추출은 후속 스펙에서
이 자리를 채운다.
"""

from silen_worker.db import connect, fetch_memory
from silen_worker.queue import QUEUE, read_messages, delete_message, archive_message

VISIBILITY_TIMEOUT = 30  # 초. 처리 중 워커가 죽으면 이만큼 뒤 재전달된다.
MAX_READS = 5  # 이 횟수를 넘게 재전달되면 데드레터로 보낸다.


def process_pending(limit: int = 10) -> list[str]:
    """큐에서 최대 limit개 처리하고 처리한 memory_id를 반환한다."""
    processed: list[str] = []
    with connect() as conn:
        for msg_id, read_ct, payload in read_messages(conn, QUEUE, VISIBILITY_TIMEOUT, limit):
            try:
                memory = fetch_memory(conn, payload["memory_id"], payload["user_id"])
                if memory is not None:
                    processed.append(memory.id)
                # 메모가 없어도(삭제·잠금) 메시지는 지운다 — 재시도 의미 없음.
                delete_message(conn, QUEUE, msg_id)
            except Exception:
                # 삭제하지 않으면 visibility timeout 후 재전달된다.
                # 상한을 넘으면 데드레터로 보내 무한 재시도를 막는다.
                if read_ct >= MAX_READS:
                    archive_message(conn, QUEUE, msg_id)
    return processed
```

- [ ] **Step 2: roundtrip·at-least-once 테스트 작성**

`worker/tests/test_process.py`:

```python
import time

import pytest

from silen_worker.queue import QUEUE, read_messages, delete_message
from silen_worker.tasks.process import process_pending
from tests.conftest import seed_user, seed_memory, delete_user


@pytest.mark.integration
def test_메모_생성부터_처리까지_배관이_돈다(conn):
    conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))
    user = seed_user(conn)
    try:
        # seed_memory의 insert가 트리거로 메시지를 넣는다.
        memory_id = seed_memory(conn, user, "처리될 메모")

        processed = process_pending(limit=10)

        assert memory_id in processed
        # 처리 후 큐가 비었다.
        assert read_messages(conn, QUEUE, 1, 10) == []
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_삭제하지_않은_메시지는_visibility_timeout_후_재전달된다(conn):
    conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "재전달 메모")

        # vt=1로 읽고 지우지 않는다.
        first = read_messages(conn, QUEUE, 1, 10)
        assert len(first) == 1
        # 즉시 다시 읽으면 숨겨져 있어 안 보인다.
        assert read_messages(conn, QUEUE, 1, 10) == []
        # vt가 지나면 다시 보인다(at-least-once).
        time.sleep(1.5)
        again = read_messages(conn, QUEUE, 1, 10)
        assert len(again) == 1
        # 정리.
        delete_message(conn, QUEUE, again[0][0])
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_메모가_삭제됐어도_메시지는_치워진다(conn):
    conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))
    user = seed_user(conn)
    try:
        memory_id = seed_memory(conn, user, "곧 삭제")
        # 메시지는 이미 큐에 있다. 메모를 지운다(메시지는 남는다).
        conn.execute("delete from public.memories where id = %s", (memory_id,))

        processed = process_pending(limit=10)

        # 처리 목록엔 없지만(메모 없음), 큐는 비워졌다.
        assert memory_id not in processed
        assert read_messages(conn, QUEUE, 1, 10) == []
    finally:
        delete_user(conn, user)
```

- [ ] **Step 3: 실행**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -m integration -v
```

Expected: 스코핑 2 + 소비 3 = 5건 PASS.

- [ ] **Step 4: 뮤테이션 점검 — 스코핑이 실제 방어선인지**

`fetch_memory`의 user_id 필터를 잠시 지우면 격리 테스트가 깨져야 한다. `db.py`에서 `and user_id = %s`를 임시로 빼고(파라미터도 하나로) 스코핑 테스트를 돌린다.

```powershell
# db.py의 fetch_memory 쿼리에서 user_id 조건을 임시로 제거한 뒤:
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_worker_db.py -m integration -v
```

Expected: FAIL — "남의 user_id로는 조회되지 않는다"가 깨진다(필터 없으면 남의 메모도 반환).

확인 후 원상복구하고 재실행:

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -m integration -v
```

Expected: 5건 PASS.

- [ ] **Step 5: ruff·단위 분리 확인**

```powershell
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration"
```

Expected: ruff 통과, 단위 7건만(DB 불필요) 통과.

- [ ] **Step 6: 커밋**

```powershell
git add worker/src/silen_worker/tasks worker/tests/test_process.py
git commit -m "feat(worker): process_pending 소비

pgmq에서 읽어 메모를 스코프 조회하고 메시지를 지운다. 일회성.
실패 시 삭제하지 않아 visibility timeout으로 재시도, 상한 초과 시
데드레터. 배관 roundtrip·at-least-once 재전달·메모 부재 처리를
통합 테스트로 고정. 뮤테이션 점검으로 스코핑이 방어선임을 확인."
```

---

## Task 5: 문서 + DoD

**Files:**
- Modify: `supabase/README.md`, `README.md`

- [ ] **Step 1: supabase/README에 큐 메모**

`supabase/README.md`의 Storage 절 아래에 추가:

```markdown
## 큐 (pgmq)

- 비동기 큐는 pgmq. 큐 `memory_jobs`, 메시지 `{memory_id, user_id}`.
- 메모 insert AFTER 트리거가 적재한다. in-DB라 메모 커밋과 같은
  트랜잭션 — 유령·유실 잡이 없다. 메시지엔 본문을 싣지 않는다.
- 워커는 특권 역할(로컬 postgres)로 psycopg 직접 접속해 RLS를 우회하므로,
  워커 쿼리가 user_id 필터를 지키는 것이 유일한 격리 방어선이다.
- 새 잡을 추가하면 이 큐를 재사용하고, 처리는 멱등(자연키 upsert)해야 한다.
```

- [ ] **Step 2: README에 워커 실행·검사 안내**

`README.md`의 저장소 구조에서 `worker/` 줄을 보강하고, 검사 절에 워커 통합을 추가한다.

구조 블록의 `worker/` 아래에:

```
worker/src/silen_worker/tasks/   # 큐 소비 잡 진입점(process_pending)
worker/src/silen_worker/db.py    # 워커 DB 접근(user 스코프 강제)
```

검사 절(`### 3. 검사`)의 워커 명령을 마커 분리로 교체:

```powershell
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker -m "not integration"   # 단위(DB 불필요)
worker\.venv\Scripts\python.exe -m pytest worker -m integration          # 통합(Supabase 스택 필요)
```

- [ ] **Step 3: 전체 검사**

```powershell
npm run check
npm run test:integration
worker\.venv\Scripts\python.exe -m ruff check worker
worker\.venv\Scripts\python.exe -m pytest worker
npx supabase db reset
npx supabase stop; Start-Sleep -Seconds 3; npx supabase start
```

Expected: 모두 통과. `db reset` 후엔 재기동으로 502 방지, 그다음 통합 테스트가 초록.

- [ ] **Step 4: 커밋**

```powershell
git add supabase/README.md README.md
git commit -m "docs: 워커 큐 파이프라인 안내"
```

- [ ] **Step 5: 브랜치 마무리**

`/superpowers:finishing-a-development-branch`. rebase 후 `merge --no-ff`, squash 금지(git.md).

---

## 완료 기준

- 메모 insert → 트리거가 pgmq에 `{memory_id, user_id}`를 넣는다
- `process_pending`이 메시지를 소비하고 올바른 memory_id를 반환한다
- `fetch_memory`가 남의 user_id로는 `None`을 반환한다(뮤테이션 점검으로 확인)
- 삭제 안 한 메시지가 visibility timeout 후 재전달된다
- 메모가 사라져도 메시지는 치워진다
- 단위 테스트(pytest -m "not integration")는 DB 없이 통과
- `npm run check`·`npm run test:integration`·`ruff`·`pytest`·`db reset` 통과

## 이번 범위 밖

- 엔티티 추출·LLM (후속 스펙 B)
- detector·차이 탐지 (통계, 이후)
- 멱등 효과(upsert) — B에서
- 프로덕션 워커 실행(데몬·스케줄)·전용 역할
- 백필(기존 메모 적재) — B에서
