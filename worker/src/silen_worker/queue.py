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
