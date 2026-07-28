"""pgmq 래퍼. 큐 API를 한곳에 모아 detector·추출 잡이 재사용한다."""

from typing import Any

import psycopg
from psycopg import sql

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


def read_messages_for_user(
    conn: psycopg.Connection,
    queue: str,
    user_id: str,
    vt: int,
    qty: int,
) -> list[tuple[int, int, dict[str, Any]]]:
    """해당 사용자의 보이는 메시지만 claim한다.

    pgmq.read는 필터를 받지 않아 먼저 읽은 다른 사용자의 read_ct·vt까지 바꾼다.
    사용자 격리가 필요한 테스트 경로에서는 큐 테이블에서 소유자 조건을 건 뒤
    같은 claim 동작을 원자적으로 수행한다.
    """
    table = sql.Identifier("pgmq", f"q_{queue}")
    query = sql.SQL(
        """
        with selected as (
          select msg_id
          from {}
          where vt <= clock_timestamp()
            and message->>'user_id' = %s
          order by msg_id
          limit %s
          for update skip locked
        )
        update {} as queue
        set vt = clock_timestamp() + make_interval(secs => %s),
            read_ct = queue.read_ct + 1
        from selected
        where queue.msg_id = selected.msg_id
        returning queue.msg_id, queue.read_ct, queue.message
        """
    ).format(table, table)
    rows = conn.execute(query, (user_id, qty, vt)).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def delete_message(conn: psycopg.Connection, queue: str, msg_id: int) -> None:
    conn.execute("select pgmq.delete(%s, %s)", (queue, msg_id))


def archive_message(conn: psycopg.Connection, queue: str, msg_id: int) -> None:
    conn.execute("select pgmq.archive(%s, %s)", (queue, msg_id))
