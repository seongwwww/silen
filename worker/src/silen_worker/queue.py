"""pgmq 래퍼. 큐 API를 한곳에 모아 detector·추출 잡이 재사용한다."""

from typing import Any

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

QUEUE = "memory_jobs"


def send_message(
    conn: psycopg.Connection, queue: str, message: dict[str, Any]
) -> int:
    """기존 pgmq 큐에 JSON 메시지 하나를 넣고 msg_id를 반환한다."""
    row = conn.execute(
        "select pgmq.send(%s, %s::jsonb)",
        (queue, Jsonb(message)),
    ).fetchone()
    return int(row[0])


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


def mark_recall_processing(
    conn: psycopg.Connection,
    msg_id: int,
    user_id: str,
    request_id: str,
) -> bool:
    row = conn.execute(
        """
        update pgmq.q_memory_jobs
           set message = jsonb_set(message, '{status}', '"processing"'::jsonb)
         where msg_id = %s
           and message->>'job_type' = 'recall'
           and message->>'user_id' = %s
           and message->>'request_id' = %s
           and message->>'status' in ('queued', 'processing')
        returning msg_id
        """,
        (msg_id, user_id, request_id),
    ).fetchone()
    return row is not None


def reset_recall_for_retry(
    conn: psycopg.Connection,
    msg_id: int,
    user_id: str,
    request_id: str,
) -> None:
    conn.execute(
        """
        update pgmq.q_memory_jobs
           set message = jsonb_set(message, '{status}', '"queued"'::jsonb)
         where msg_id = %s
           and message->>'user_id' = %s
           and message->>'request_id' = %s
        """,
        (msg_id, user_id, request_id),
    )


def complete_recall_message(
    conn: psycopg.Connection,
    msg_id: int,
    user_id: str,
    request_id: str,
    response: dict[str, Any],
) -> None:
    """원 질문을 제거한 완료 payload로 교체하고 잠시 뒤 정리 대상으로 만든다."""
    payload = {
        "job_type": "recall_result",
        "request_id": request_id,
        "user_id": user_id,
        "status": "done",
        "response": response,
    }
    conn.execute(
        """
        update pgmq.q_memory_jobs
           set message = %s::jsonb,
               vt = clock_timestamp() + interval '10 minutes'
         where msg_id = %s
           and message->>'user_id' = %s
           and message->>'request_id' = %s
        """,
        (Jsonb(payload), msg_id, user_id, request_id),
    )


def fail_recall_message(
    conn: psycopg.Connection,
    msg_id: int,
    user_id: str,
    request_id: str,
    error_code: str,
) -> None:
    """본문·질문·예외 메시지 없이 고정 오류 코드만 잠시 보존한다."""
    payload = {
        "job_type": "recall_result",
        "request_id": request_id,
        "user_id": user_id,
        "status": "error",
        "error_code": error_code,
    }
    conn.execute(
        """
        update pgmq.q_memory_jobs
           set message = %s::jsonb,
               vt = clock_timestamp() + interval '10 minutes'
         where msg_id = %s
           and message->>'user_id' = %s
           and message->>'request_id' = %s
        """,
        (Jsonb(payload), msg_id, user_id, request_id),
    )
