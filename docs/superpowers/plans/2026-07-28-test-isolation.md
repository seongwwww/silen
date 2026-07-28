# 통합 테스트 격리 구현 계획

> **실행 주체:** Codex가 구현한다. 태스크마다 ① 실패 테스트 → ② 실패 확인 → ③ 계획의 코드 그대로 → ④ 통과 → ⑤ ruff/lint → ⑥ 그 태스크 단위로 1커밋.

**Goal:** 통합 테스트가 개발 DB의 다른 데이터를 파괴하지 않게 한다. 테스트를 돌린 뒤에도 실데이터 검증 재료가 살아남아야 한다.

**Architecture:** 테스트는 DB를 소유하지 않는다. 전역 삭제·purge를 없애고, 그것만으로 위험해지는 큐는 `process_pending(only_user_id=...)`로 남의 메시지를 건너뛰어 보호한다. 전역 상태 단언은 자기 것 단언으로 바꾼다.

**Tech Stack:** Python 3.12(pytest) · TypeScript(Vitest) · pgmq · Supabase

## Global Constraints

- **`main` 직접 커밋 금지** — **`fix/test-isolation`을 `main`에서 새로 만들어** 작업한다. 스펙·계획은 이미 `main`에 있다.
- 커밋 메시지 `<type>(<scope>): <한국어 요약>`. scope는 `worker`·`test`·`docs`. **`Co-Authored-By`는 네 것으로.**
- **태스크마다 커밋만. push·merge 금지**(사람이 한다).
- **스키마·마이그레이션·API·프론트 화면 코드 변경 없음.** 손대는 것은 테스트와 `process_pending` 한 함수뿐이다.
- ⚠️ **`process_pending`의 기본 동작을 바꾸지 마라.** `only_user_id=None`이면 지금과 완전히 동일해야 한다(프로덕션 CLI가 그대로 쓴다).
- ⚠️ **테스트를 약화하지 마라.** 전역 단언을 자기 것 단언으로 바꾸는 건 정확화지 완화가 아니다. 단언 자체를 지우거나 `expect(true)` 류로 만들지 마라.
- **로컬 Supabase 필요.** `db reset` 후엔 `npx supabase stop; Start-Sleep -Seconds 3; npx supabase start`.
- 파이썬은 `worker\.venv\Scripts\python.exe` 직접 호출.
- 🚫 **실 LLM을 부르지 마라.** 모든 테스트는 스텁 추출기를 쓴다.
- 완료(DoD) = ruff + pytest + lint + build + vitest(단위·통합).
- 못 고치는 실패·모호한 점은 **멈추고 보고**하라.

## 결정 고정

1. **`only_user_id` 검사는 `try` 블록 앞에 둔다.** 그래야 예외 경로의 아카이브(데드레터)가 남의 메시지에 절대 닿지 않는다.
2. **건너뛴 메시지는 삭제도 아카이브도 하지 않는다.** `continue`만 한다. 읽기로 vt(60초) 동안 안 보이지만 그 뒤 되돌아온다 — 의도된 동작이다.
3. **`only_user_id=None`이 기본**이고, 그때는 지금과 동일하게 전부 처리한다.
4. **큐 상태를 단언할 땐 `pgmq.read`를 쓰지 마라.** `read`는 vt를 세팅하는 **부작용**이 있어 남의 메시지를 60초 숨긴다. 단언에는 큐 테이블을 직접 조회한다(`select message from pgmq.q_memory_jobs`).
5. **`purge_queue` 호출을 전부 제거한다**(워커 7곳 + 프론트 1곳). 남기지 마라.
6. **`schema.integration.test.ts`의 `listUsers` 전역 삭제를 제거**하고, 만든 user id를 모아 그것만 지운다. `delete from public.deletions`도 그 id들로 한정한다.
7. **`queue.integration.test.ts`의 "메모가 없으면 메시지도 없다"** 는 전역 빈 상태를 단언한다. **이 테스트 사용자의 메모를 참조하는 메시지가 없다**로 좁힌다.
8. **핵심 회귀 테스트는 새 파일**(`worker/tests/test_queue_isolation_integration.py`)에 둔다. 눈에 띄어야 회귀를 막는다.
9. **`.claude/rules/testing.md`에 규칙 한 줄을 추가**한다. 문서가 아니라 규칙이어야 다음 에이전트가 지킨다.

## File Structure

| 경로 | 책임 |
|------|------|
| `worker/src/silen_worker/tasks/process.py`(수정) | `only_user_id` 파라미터 |
| `worker/tests/test_queue_isolation_integration.py` | **핵심 회귀** — 남의 메시지 생존 |
| `worker/tests/test_process.py`(수정) | purge 제거·자기 것 단언·스코프 전달 |
| `worker/tests/test_extraction_integration.py`(수정) | purge 제거·스코프 전달 |
| `lib/repositories/queue.integration.test.ts`(수정) | purge 제거·자기 것 단언 |
| `lib/repositories/schema.integration.test.ts`(수정) | 전역 사용자 삭제 제거 |
| `.claude/rules/testing.md`(수정) | 규칙 한 줄 |

---

## Task 1: `process_pending`에 스코프 + 핵심 회귀 테스트

**⚠️ 이 태스크가 이 작업의 핵심이다.** 남의 메시지를 보호하는 장치와 그 증거를 함께 만든다.

**Files:** Modify `worker/src/silen_worker/tasks/process.py`; Create `worker/tests/test_queue_isolation_integration.py`

- [ ] **Step 1: 실패 테스트 작성**

`worker/tests/test_queue_isolation_integration.py`:

```python
"""큐 격리 회귀 — 통합 테스트가 남의 메시지를 삼키면 안 된다.

이 테스트가 없으면 회귀가 조용히 돌아온다. 실제로 개발 DB의 실데이터
잡이 두 번 사라졌고, 그때마다 파이프라인 검증 재료를 잃었다.
"""

import json

import pytest

from silen_worker.queue import QUEUE
from silen_worker.tasks.process import process_pending
from tests.conftest import seed_user, seed_memory, delete_user


class _NoEntities:
    def extract(self, text):
        return []


def _queue_payloads(conn):
    rows = conn.execute("select message from pgmq.q_memory_jobs").fetchall()
    return [r[0] for r in rows]


@pytest.mark.integration
def test_남의_메시지는_소비되지_않는다(conn):
    """다른 사용자의 잡이 큐에 있어도 살아남아야 한다 — 삭제도 아카이브도 안 됨."""
    stranger = seed_user(conn)
    owner = seed_user(conn)
    try:
        stranger_memory = seed_memory(conn, stranger, "남의 기록")
        owner_memory = seed_memory(conn, owner, "내 기록")

        processed = process_pending(
            limit=10, extractor=_NoEntities(), only_user_id=owner
        )

        assert owner_memory in processed
        assert stranger_memory not in processed

        # 남의 메시지는 큐에 그대로 있다.
        payloads = _queue_payloads(conn)
        assert any(p.get("memory_id") == stranger_memory for p in payloads)
        # 내 메시지는 처리돼 사라졌다.
        assert not any(p.get("memory_id") == owner_memory for p in payloads)

        # 아카이브(데드레터)로도 가지 않았다.
        archived = conn.execute(
            "select count(*)::int from pgmq.a_memory_jobs where (message->>'memory_id') = %s",
            (stranger_memory,),
        ).fetchone()[0]
        assert archived == 0
    finally:
        delete_user(conn, stranger)
        delete_user(conn, owner)


@pytest.mark.integration
def test_스코프가_없으면_기존대로_전부_처리한다(conn):
    """only_user_id=None은 프로덕션 기본 동작 — 지금과 같아야 한다."""
    user_a = seed_user(conn)
    user_b = seed_user(conn)
    try:
        memory_a = seed_memory(conn, user_a, "가 기록")
        memory_b = seed_memory(conn, user_b, "나 기록")

        processed = process_pending(limit=50, extractor=_NoEntities())

        assert memory_a in processed
        assert memory_b in processed
    finally:
        delete_user(conn, user_a)
        delete_user(conn, user_b)
```

- [ ] **Step 2: 실패 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_queue_isolation_integration.py -m integration -v
```
Expected: 첫 테스트가 `TypeError: process_pending() got an unexpected keyword argument 'only_user_id'`로 FAIL.

- [ ] **Step 3: 구현**

`worker/src/silen_worker/tasks/process.py`의 함수 시그니처와 루프 앞부분을 아래로 바꾼다:

```python
def process_pending(
    limit: int = 10,
    extractor: LLMExtractor | None = None,
    only_user_id: str | None = None,
) -> list[str]:
    """큐에서 최대 limit개 처리하고 처리한 memory_id를 반환한다.
    extractor는 LLMExtractor 포트. 테스트는 스텁, 프로덕션은 Gemini를 주입한다.

    only_user_id를 주면 그 사용자의 메시지만 처리하고 나머지는 **건드리지 않는다**
    (삭제도 아카이브도 안 함). 통합 테스트가 개발 DB의 남의 잡을 삼켜 실데이터
    검증 재료를 날리던 문제를 막는다. None이면 지금까지처럼 전부 처리한다.
    """
    if extractor is None:
        from silen_worker.extraction.gemini import GeminiExtractor

        extractor = GeminiExtractor()

    processed: list[str] = []
    with connect() as conn:
        for msg_id, read_ct, payload in read_messages(conn, QUEUE, VISIBILITY_TIMEOUT, limit):
            # 남의 메시지는 손대지 않는다. try 밖에 두어야 예외 경로의
            # 아카이브(데드레터)도 절대 닿지 않는다. 읽기로 vt 동안 안 보이지만
            # 그 뒤 큐로 되돌아온다.
            if only_user_id is not None and payload.get("user_id") != only_user_id:
                continue
            try:
```

**나머지 본문(`memory = fetch_memory(...)` 이하)은 그대로 둔다.**

- [ ] **Step 4: 통과 확인**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker/tests/test_queue_isolation_integration.py -m integration -v
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 2건 PASS, ruff 통과.

- [ ] **Step 5: 커밋**

```powershell
git add worker/src/silen_worker/tasks/process.py worker/tests/test_queue_isolation_integration.py
git commit -m "feat(worker): process_pending에 사용자 스코프

통합 테스트가 큐 머리부터 읽어 남의 잡까지 소비·삭제했다. 스텁 추출기로
처리되어 실데이터 잡이 조용히 사라졌고, 그때마다 파이프라인 검증 재료를
잃었다. only_user_id를 주면 남의 메시지를 건너뛴다 — 삭제도 아카이브도
하지 않는다. 검사를 try 밖에 둬 예외 경로의 데드레터도 닿지 않게 했다.
None이면 기존 동작 그대로다."
```

---

## Task 2: 워커 테스트 — purge 제거·자기 것 단언

**Files:** Modify `worker/tests/test_process.py`, `worker/tests/test_extraction_integration.py`

- [ ] **Step 1: `test_process.py` 수정**

세 곳의 `conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))` 줄을 **삭제**한다(17·34·56행 부근).

`process_pending(...)` 호출에 **자기 user를 넘긴다**:
```python
        processed = process_pending(limit=10, extractor=_NoEntities(), only_user_id=user)
```

전역 큐 단언을 자기 것 단언으로 바꾼다. `assert read_messages(conn, QUEUE, 1, 10) == []` 를 아래로 교체:

```python
        # 큐 전체가 비었는지가 아니라 "내 메시지가 사라졌는지"를 본다.
        # pgmq.read는 vt를 세팅하는 부작용이 있어 단언에 쓰지 않는다.
        remaining = conn.execute(
            "select 1 from pgmq.q_memory_jobs where (message->>'memory_id') = %s",
            (memory_id,),
        ).fetchone()
        assert remaining is None
```

`memory_id` 변수가 없는 테스트에서는 그 테스트가 만든 메모 id를 쓴다(없으면 `seed_memory` 반환값을 변수로 받는다).

visibility timeout 재전달 테스트(`test_삭제하지_않은_메시지는...`)는 `read_messages`로 **자기 메시지가 돌아오는지**를 보므로, 읽은 메시지 중 자기 `memory_id`를 가진 것을 찾아 단언하도록 좁힌다.

- [ ] **Step 2: `test_extraction_integration.py` 수정**

네 곳의 purge 줄(27·50·63·87행 부근)을 **삭제**하고, `process_pending(...)` 호출마다 `only_user_id=user`를 넘긴다.

- [ ] **Step 3: 실행**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -q
worker\.venv\Scripts\python.exe -m ruff check worker
```
Expected: 전체 PASS(기준선 131 + Task 1의 2건 = 133), ruff 통과.

- [ ] **Step 4: 커밋**

```powershell
git add worker/tests/test_process.py worker/tests/test_extraction_integration.py
git commit -m "test(worker): 큐 purge 제거·자기 메시지만 단언

전역 purge로 남의 잡을 날리는 대신 only_user_id로 자기 것만 처리한다.
'큐가 비었다'는 우연히 참인 전역 상태였다 — '내 메시지가 사라졌다'가
실제로 검증하려던 것이다. 단언에는 부작용 없는 큐 테이블 조회를 쓴다."
```

---

## Task 3: `queue.integration.test.ts` — purge 제거·자기 것 단언

**Files:** Modify `lib/repositories/queue.integration.test.ts`

- [ ] **Step 1: purge 제거**

아래 `beforeEach` 블록을 **통째로 삭제**한다:

```ts
// 큐를 비워 테스트 간 간섭을 없앤다.
beforeEach(async () => {
  await db.query("select pgmq.purge_queue('memory_jobs')");
});
```

`beforeEach` import가 안 쓰이면 import 목록에서도 뺀다.

- [ ] **Step 2: 두 단언을 자기 것으로 좁힌다**

첫 테스트(`메모가 생기면 ...`)의 조회를 아래로 바꾼다. `pgmq.read`는 vt를 세팅해 남의 메시지를 숨기므로 쓰지 않는다:

```ts
    const res = await db.query(
      "select message from pgmq.q_memory_jobs where (message->>'memory_id') = $1",
      [memoryId],
    );
    expect(res.rows.map((r) => r.message)).toContainEqual({
      memory_id: memoryId,
      user_id: user,
    });
```

둘째 테스트(`메모가 없으면 메시지도 없다`)는 전역 빈 상태를 단언하므로 **이 사용자 기준**으로 좁힌다:

```ts
  it("메모를 만들지 않으면 이 사용자의 메시지도 없다", async () => {
    const res = await db.query(
      "select msg_id from pgmq.q_memory_jobs where (message->>'user_id') = $1",
      [user],
    );
    expect(res.rowCount).toBe(0);
  });
```

> ⚠️ 이 테스트는 같은 파일의 첫 테스트가 메모를 만들기 **전에** 돌아야 의미가 있다. 순서가 바뀌면 첫 테스트가 만든 메시지가 잡히므로, **둘째 테스트를 파일에서 첫 테스트보다 위로 옮긴다.** 옮기기 애매하면 멈추고 보고하라.

- [ ] **Step 3: 실행·커밋**

```powershell
npx vitest run --config vitest.integration.config.mts lib/repositories/queue.integration.test.ts
npm run lint
```

```powershell
git add lib/repositories/queue.integration.test.ts
git commit -m "test: 큐 트리거 테스트를 자기 사용자로 좁힌다

전역 purge를 없애고 이 사용자의 메시지만 조회·단언한다. pgmq.read는
vt를 세팅하는 부작용이 있어 단언에서 큐 테이블 직접 조회로 바꿨다."
```

---

## Task 4: `schema.integration.test.ts` — 전역 사용자 삭제 제거

**Files:** Modify `lib/repositories/schema.integration.test.ts`

- [ ] **Step 1: 전역 삭제를 자기 것 정리로 교체**

기존 `beforeEach`(21~27행 부근)를 **삭제**하고, 만든 사용자를 추적하는 방식으로 바꾼다. 파일 상단(`const db = ...` 아래)에 추가:

```ts
// 테스트가 만든 사용자만 추적해 지운다. 전역 삭제(listUsers → 전부 deleteUser)는
// 개발 DB의 실데이터까지 날려 파이프라인 검증 재료를 잃게 했다.
const createdUsers: string[] = [];

afterEach(async () => {
  if (createdUsers.length === 0) return;
  await db.query("delete from public.deletions where user_id = any($1::uuid[])", [
    createdUsers,
  ]);
  const admin = adminClient();
  for (const id of createdUsers) {
    await admin.auth.admin.deleteUser(id);
  }
  createdUsers.length = 0;
});
```

`afterEach`를 `vitest` import에 추가하고, 안 쓰게 된 `beforeEach`는 뺀다.

`createUser` 함수가 만든 id를 추적하도록 반환 직전에 한 줄 넣는다:

```ts
  if (error) throw error;
  createdUsers.push(data.user.id);
  return data.user.id;
```

- [ ] **Step 2: 실행**

```powershell
npx vitest run --config vitest.integration.config.mts lib/repositories/schema.integration.test.ts
```
Expected: 전부 PASS. 단언은 이미 `where user_id = $1`로 스코프돼 있어 전역 비움 없이도 통과해야 한다.

**실패하면 어떤 단언이 왜 전역 상태에 기대는지 보고하라.** 단언을 지우거나 약화시키지 마라.

- [ ] **Step 3: 커밋**

```powershell
git add lib/repositories/schema.integration.test.ts
git commit -m "test: 스키마 테스트가 자기 사용자만 지우게

beforeEach마다 listUsers로 모든 auth 사용자를 지워 개발 DB의 실데이터까지
날렸다. 단언은 이미 user 스코프라 전역 비움이 필요 없었다 — 만든 사용자만
추적해 정리한다."
```

---

## Task 5: 규칙·문서

**Files:** Modify `.claude/rules/testing.md`, `supabase/README.md`

- [ ] **Step 1: 규칙 추가**

`.claude/rules/testing.md`의 "방식" 절에 항목을 추가한다(문서가 아니라 **규칙**이어야 다음 에이전트가 지킨다):

```markdown
- **통합 테스트는 DB를 소유하지 않는다.** 자기가 만든 것만 만들고, 자기가 만든 것만
  지우고, 자기 것에 대해서만 단언한다. 전역 삭제(`listUsers` → 전부 삭제)·전역
  `purge_queue`·"큐가 비었다" 같은 전역 상태 단언을 쓰지 마라 — 개발 DB의 실데이터를
  날려 파이프라인 검증 재료가 사라진다.
- 큐를 소비하는 테스트는 `process_pending(only_user_id=...)`로 자기 사용자만 처리한다.
  큐 상태를 단언할 땐 `pgmq.read`(vt를 세팅하는 부작용) 대신 큐 테이블을 직접 조회한다.
```

- [ ] **Step 2: supabase/README 갱신**

`supabase/README.md`의 "큐 (pgmq)" 절 끝에 추가:

```markdown
- 큐는 전역이다. 통합 테스트는 `purge_queue`로 비우지 않고
  `process_pending(only_user_id=...)`로 자기 잡만 처리한다 — 전역 purge는 개발 DB의
  실데이터 잡을 날린다.
```

- [ ] **Step 3: 전체 검사**

```powershell
worker\.venv\Scripts\python.exe -m pytest worker -q
worker\.venv\Scripts\python.exe -m ruff check worker
npx vitest run
npm run lint
npm run build
npx vitest run --config vitest.integration.config.mts
```
Expected: 전부 통과. 기준선 프론트 단위 63 · 통합 49 · 워커 131(+새 2건).

- [ ] **Step 4: 사람이 확인할 것을 보고에 남긴다**

통합 테스트를 돌린 **뒤에도** 기존 사용자·메모·일기가 남아 있는지 확인하고 건수를 보고한다:

```powershell
worker\.venv\Scripts\python.exe -c "import psycopg; c=psycopg.connect('postgresql://postgres:postgres@127.0.0.1:54322/postgres'); print('users', c.execute('select count(*) from public.users').fetchone()[0], 'memories', c.execute('select count(*) from public.memories where deleted_at is null').fetchone()[0], 'diaries', c.execute('select count(*) from public.diaries').fetchone()[0])"
```

- [ ] **Step 5: 커밋**

```powershell
git add .claude/rules/testing.md supabase/README.md
git commit -m "docs: 통합 테스트가 DB를 소유하지 않는다는 규칙

전역 삭제·purge·전역 상태 단언 금지를 testing.md 규칙으로 못박는다.
문서가 아니라 규칙이어야 다음 에이전트가 지킨다."
```

- [ ] **Step 6: 최종 보고**

`HANDOFF.md`의 "상태" 절을 갱신하고 커밋한다. **push·merge는 하지 마라.**

---

## 완료 기준

- `purge_queue` 호출이 저장소에 **0건**이다.
- `schema.integration.test.ts`에 `listUsers` 전역 삭제가 없다.
- **핵심 회귀 테스트가 통과한다** — 남의 메시지가 큐에 남고 아카이브되지도 않는다.
- `process_pending(only_user_id=None)`이 기존과 동일하게 전부 처리한다(테스트로 증명).
- 통합 테스트를 돌린 뒤에도 **기존 사용자·메모·일기가 남아 있다**(건수 보고).
- ruff + pytest + lint + build + vitest(단위·통합) 전부 통과.

## 이번 범위 밖
- 테스트 전용 DB·스택 분리 · seed 스크립트.
- `run-pending --user` CLI 노출.
- 워커 CLI UTF-8 · 엔티티 추출 일반명사 억제.
