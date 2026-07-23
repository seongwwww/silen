import time

import pytest

from silen_worker.queue import QUEUE, read_messages, delete_message
from silen_worker.tasks.process import process_pending
from tests.conftest import seed_user, seed_memory, delete_user


class _NoEntities:
    def extract(self, text):
        return []


@pytest.mark.integration
def test_메모_생성부터_처리까지_배관이_돈다(conn):
    conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))
    user = seed_user(conn)
    try:
        # seed_memory의 insert가 트리거로 메시지를 넣는다.
        memory_id = seed_memory(conn, user, "처리될 메모")

        processed = process_pending(limit=10, extractor=_NoEntities())

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

        processed = process_pending(limit=10, extractor=_NoEntities())

        # 처리 목록엔 없지만(메모 없음), 큐는 비워졌다.
        assert memory_id not in processed
        assert read_messages(conn, QUEUE, 1, 10) == []
    finally:
        delete_user(conn, user)
