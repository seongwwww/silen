"""사용자 로컬 설정 시각이 지난 날짜의 일기 요청을 멱등하게 예약한다."""

import psycopg

from silen_worker.db import insert_scheduled_diary_request
from silen_worker.queue import QUEUE, send_message


def schedule_diary(
    conn: psycopg.Connection,
    user_id: str,
    target_date_iso: str,
) -> str | None:
    """기존 요청 원장과 기존 memory_jobs 큐를 같은 트랜잭션에서 갱신한다."""
    with conn.transaction():
        request_id = insert_scheduled_diary_request(
            conn,
            user_id,
            target_date_iso,
        )
        if request_id is None:
            return None
        send_message(
            conn,
            QUEUE,
            {
                "job_type": "diary",
                "request_id": request_id,
                "user_id": user_id,
                "date": target_date_iso,
            },
        )
    return request_id
