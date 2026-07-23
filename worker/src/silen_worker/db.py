"""워커 DB 접근. 특권 역할(로컬 postgres)로 psycopg 직접 접속해 RLS를 우회한다.
RLS가 막아주지 않으므로 모든 조회에 user_id 필터를 코드로 강제한다(스펙 §8).
"""

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

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
