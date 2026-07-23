# 워커 파이프라인 밑감 설계 스펙 — pgmq + Python 워커 + 트리거

- 날짜: 2026-07-23
- 관련: `.claude/rules/backend.md`(2자산·큐·멱등성), `docs/decisions/ADR-0002-schema-gates.md`, `docs/superpowers/specs/2026-07-23-recording-backend-design.md`, `docs/planning/서비스_기획서.md` §13
- 상태: 설계 확정 (구현 계획 대기)
- 선행: 기록 백엔드(`memories` 테이블·insert 경로)가 `main`에 있음. auth·RLS·GRANT도 병합됨.

## 1. 배경

기획서 §13 순서상 인증·기록 다음은 W2 "baseline 엔진 + 차이 탐지"다. 그러나 지금 데이터(수동 텍스트 + 감정칩)로는 제품이 약속한 "차이 발견"(그 노래 또·3일째 김밥·처음 간 곳)을 탐지할 수 없다. 그 재료는 텍스트에서 **엔티티**(사람·장소·활동·사물)를 뽑아야 나오고, 엔티티 추출은 **LLM 워커 잡**이다.

엔티티 추출은 세 가지를 한꺼번에 끌고 온다: 워커 파이프라인(pgmq+워커+트리거), LLM 인프라(프로바이더·구조화 출력·eval), 프라이버시(타인 이름 추출·본문을 LLM에 전송). 검증 안 된 배관 위에 이걸 다 얹으면 리스크 슬라이스가 된다.

그래서 분해한다:
- **A(이 스펙): 워커 파이프라인 밑감** — pgmq + 워커 소비 + 메모 트리거 + Python DB 접근. 사소한 잡으로 배관만 증명. LLM 없음. 인프라 리스크를 먼저 걷어낸다.
- **B(후속): 엔티티 추출 잡** — 사소한 잡을 진짜 LLM 추출로 교체. AI 리스크는 그때.

이 스펙은 A만 다룬다. **사용자에게 보이는 것은 없다** — 순수 인프라다.

## 2. 결정 요약

| # | 항목 | 결정 |
|---|------|------|
| 1 | 큐 | pgmq (Postgres 메시지 큐). 큐 이름 `memory_jobs` |
| 2 | 메시지 단위 | 메모별 `{memory_id, user_id}` (엔티티 추출이 메모 단위) |
| 3 | 적재 | `memories` insert AFTER 트리거 → `pgmq.send`. 앱은 탐지를 모름 |
| 4 | 워커 실행 | 일회성 `process_pending(limit)`. 데몬·스케줄은 범위 밖 |
| 5 | 워커 DB | 특권 역할(로컬 `postgres`)로 psycopg 직접 접속. RLS 우회 → **user_id 필터를 코드로 강제** |
| 6 | 사소한 잡 | 스코프 조회 + 메시지 삭제. 도메인 쓰기 없음(B로) |
| 7 | 멱등성 | pgmq at-least-once + visibility timeout. 멱등 효과는 B |

---

## 3. 흐름

```
메모 insert ──[AFTER INSERT 트리거]──▶ pgmq.send('memory_jobs', {memory_id, user_id})
                                              │
                        Python 워커 (service_role, 일회성)
                                              │
   pgmq.read(limit) → 각 메시지: 메모 조회(user 스코프) → 사소한 잡 → pgmq.delete
                                              │
                        실패 시 삭제 안 함 → visibility timeout 후 재전달
```

---

## 4. pgmq 검증 (가장 위험한 가정)

**pgmq가 로컬 Supabase CLI 스택에 있는가**를 구현 첫 단계에서 확인한다. Supabase는 pgmq를 지원하지만 로컬 이미지 버전에 따라 활성화 방식이 다를 수 있다. `create extension pgmq` 또는 `create extension pgmq cascade`가 마이그레이션으로 재생되는지 확인한다.

**폴백**: pgmq가 없으면 수제 `jobs` 테이블(`SELECT ... FOR UPDATE SKIP LOCKED`)로 전환한다. 이 경우 메시지 API·visibility 로직을 직접 구현한다. 어느 쪽이든 이 검증 단계에서 확정하고, 이후 워커 인터페이스(`read`/`delete`/`archive`)는 동일하게 유지한다.

---

## 5. 적재 트리거

`memories`에 AFTER INSERT 트리거를 건다.

```sql
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

**앱은 탐지를 모른다** — 기록 API가 큐 적재를 하지 않고 트리거가 결합을 대신한다(2자산이 "큐+DB로만 통신"). 트리거는 insert와 같은 트랜잭션이라 메모가 커밋되면 메시지도 확실히 들어간다.

`security definer` + `search_path = ''`는 auth의 `handle_new_user`와 같은 방어다.

**메시지에 본문(raw_text)을 싣지 않는다** — `memory_id`만. 워커가 필요할 때 DB에서 읽는다. 큐에 기록 본문이 쌓이지 않게 한다(backend.md 로깅 원칙의 연장).

**트랜잭션 결합이 오히려 강점이다.** pgmq는 같은 Postgres 안에 있으므로 `pgmq.send`는 네트워크 홉 없는 로컬 insert다. 메모 insert와 같은 트랜잭션이라 **메모가 커밋되면 메시지도 반드시 들어가고, 롤백되면 둘 다 사라진다**(유령 잡·유실 잡 없음, 트랜잭션 아웃박스가 공짜). 외부 큐였다면 "메모는 저장됐는데 적재 실패"가 생겨 5초 기록을 위협했겠지만, in-DB pgmq에서는 적재 실패 ≡ DB 실패 ≡ insert 실패라 그 창이 없다.

**백필**: 트리거는 AFTER INSERT라 **새 메모만** 적재한다. 기록 백엔드가 이미 병합돼 그전에 만들어진 메모는 큐에 없다. 배포 시 기존 메모를 일회성으로 적재하는 백필(예: `select pgmq.send('memory_jobs', ...) from memories where ...`)이 필요하나, B(엔티티 추출)가 실제로 기존 메모를 처리해야 할 때 다루고 이 스펙 범위 밖으로 둔다 — A는 배관 증명이라 새 메모로 충분하다.

---

## 6. Python 워커 (backend.md 2자산 3계층)

### 경계 — `worker/src/silen_worker/tasks/process.py`

```python
def process_pending(limit: int = 10) -> list[str]:
    """pgmq에서 최대 limit개 읽어 처리하고, 처리한 memory_id 목록을 반환한다.

    일회성. 프로덕션에서 어떻게 주기 실행할지(데몬·cron)는 범위 밖.
    실패한 메시지는 삭제하지 않아 visibility timeout 후 재전달된다.
    """
```

메시지를 읽고, 각각을 서비스에 넘기고, 성공하면 삭제한다. 처리한 id를 반환해 테스트가 검증한다.

### 서비스 — `worker/src/silen_worker/jobs/`

이번 스펙에서는 잡이 사소해 얇다. 사소한 잡: 메모를 조회(스코프 확인)하고 반환. B에서 엔티티 추출로 채워진다.

### 저장소 — `worker/src/silen_worker/db.py`

```python
def fetch_memory(memory_id: str, user_id: str) -> Memory | None:
    """메모를 조회한다. user_id로도 필터해 교차 사용자 접근을 코드로 막는다."""
```

**워커는 특권 Postgres 역할로 붙어 RLS를 우회한다.** psycopg로 직접 SQL을 실행하므로 접속 주체는 PostgREST의 `service_role` JWT가 **아니라 실제 Postgres 역할**이다(로컬은 `postgres` 슈퍼유저). RLS는 슈퍼유저·`BYPASSRLS` 역할·테이블 소유자에게 적용되지 않으므로 워커 쿼리에는 RLS가 걸리지 않는다. 반대로 **비특권 역할로 붙이면 RLS가 전면 차단해 워커가 아무것도 못 읽는다** — 그래서 특권 역할이 필수다.

RLS가 막아주지 않는 만큼, 워커 쿼리가 user_id 필터를 빠뜨리면 교차 사용자 데이터가 섞인다. 이 저장소가 user 스코프를 강제하는 **유일한 지점**이며(backend.md), 코드 리뷰·테스트 대상이다.

접속은 로컬 DB URL(`postgresql://postgres:postgres@127.0.0.1:54322/postgres`) 또는 환경변수. psycopg로 접근한다(supabase-py는 PostgREST 경유라 워커의 직접 SQL에 부적합). 프로덕션에서 워커가 붙을 역할(전용 `worker` 역할 + `BYPASSRLS`, 또는 소유자 역할)은 배포 시 정하며 범위 밖이다 — 로컬은 `postgres`.

---

## 7. 멱등성·재시도

- **at-least-once**: pgmq는 메시지를 최소 한 번 전달한다. 처리 후 명시적으로 삭제해야 사라진다.
- **visibility timeout**: 읽은 메시지는 일정 시간 안 보이다가, 삭제 안 하면 다시 보인다(재시도). 처리 중 워커가 죽어도 메시지를 잃지 않는다.
- **데드레터**: `read_ct`(읽은 횟수)가 상한을 넘으면 `pgmq.archive`로 옮긴다. 무한 재시도를 막는다.
- **동시 워커 안전**: `pgmq.read`는 읽은 메시지를 visibility timeout 동안 다른 소비자에게 숨긴다. 따라서 워커를 여러 개 돌려도 같은 메시지를 이중 처리하지 않는다(운영 시 처리량 확장이 안전).
- **멱등 효과**는 이 스펙 범위 밖이다. A의 사소한 잡은 도메인 쓰기가 없어 재처리해도 부작용이 없다. B에서 엔티티를 upsert할 때 자연키 멱등성을 실제로 설계한다.

---

## 8. 보안 — 워커는 RLS 밖

Python 워커는 특권 Postgres 역할(§6)로 접속해 RLS를 우회한다. 이는 워커가 모든 사용자의 데이터를 처리해야 하기 때문이다(탐지·추출은 전역 잡). 대가로 **RLS가 막아주지 않으므로 워커 저장소 계층이 user_id 필터를 코드로 강제**해야 한다.

A에서 이 스코핑을 테스트로 고정한다 — B가 텍스트에서 타인 이름을 뽑기 시작하기 전에, 격리 기반을 먼저 못박는다. 이 순서가 의도적이다.

---

## 9. 테스트 요구사항

### 통합

- 메모 insert → 트리거가 `memory_jobs`에 메시지를 넣는다(`pgmq` 큐에 1건).
- `process_pending` → 메시지를 소진하고 올바른 `memory_id`를 반환한다.
- 여러 메모 insert → 여러 메시지. 메모가 없으면 메시지도 없다.
- **at-least-once**: 처리 중 삭제하지 않은 메시지는 visibility timeout 후 다시 읽힌다.

### 스코핑 (보안)

- `fetch_memory(memory_id, 올바른 user_id)`는 메모를 반환한다.
- `fetch_memory(memory_id, 다른 user_id)`는 `None`을 반환한다(교차 사용자 차단).

### 단위 (Python)

- 메시지 파싱(memory_id·user_id 추출), 잘못된 페이로드 처리.

### 마이그레이션

- pgmq 확장·큐·트리거 마이그레이션에 down 스크립트를 같은 커밋에.
- `supabase db reset`이 빈 DB에서 재생. (db reset 후 auth 502는 재기동으로 복구 — supabase/README)

---

## 10. 후속 스펙

- **B: 엔티티 추출 잡** — 사소한 잡을 LLM 추출로 교체. 프로바이더(학습 미사용)·구조화 출력·eval 골든셋·프라이버시(타인 이름·본문 전송)·보수적 병합(`normalized_name`).
- **C: detector** — 엔티티 위 first-occurrence·freq-shift(통계). "그 노래 또"·"3일째 김밥".
- **D: 서술** — 의미 필터·차이 서술(LLM + eval). 차이를 사람 문장으로.

## 11. 검증이 필요한 가정

구현 첫 단계에서 확인하고, 다르면 설계를 고친다.

- **pgmq가 로컬 CLI 스택에 있고 마이그레이션으로 재생 가능한지**(§4). 없으면 수제 jobs 테이블로 폴백.
- **트리거의 `pgmq.send`가 익명 사용자 메모 insert에서도 동작하는지.** 트리거는 `security definer`라 될 것으로 보이나 확인한다.
- **psycopg가 워커 의존성으로 적합한지.** 로컬 DB에 SQL 직접 실행이 되는지 확인(numpy/scipy와 함께 설치).
