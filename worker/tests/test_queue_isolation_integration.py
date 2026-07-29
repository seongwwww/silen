"""큐 격리 회귀 — 통합 테스트가 다른 사용자의 메시지를 삼키면 안 된다."""

import pytest

from silen_worker.tasks.process import process_pending
from tests.conftest import StubEmbedder, delete_user, seed_memory, seed_user

_EMB = StubEmbedder()

class _NoEntities:
    def extract(self, text):
        return []


def _queue_payloads(conn):
    rows = conn.execute("select message from pgmq.q_memory_jobs").fetchall()
    return [row[0] for row in rows]


def _queue_delivery_state(conn, memory_id):
    return conn.execute(
        "select read_ct, vt from pgmq.q_memory_jobs "
        "where (message->>'memory_id') = %s",
        (memory_id,),
    ).fetchone()


@pytest.mark.integration
def test_다른_사용자의_메시지는_소비되지_않는다(conn):
    stranger = seed_user(conn)
    owner = seed_user(conn)
    stranger_memory = seed_memory(conn, stranger, "격리 테스트 A")
    owner_memory = seed_memory(conn, owner, "격리 테스트 B")
    try:
        stranger_state = _queue_delivery_state(conn, stranger_memory)
        processed = process_pending(
            limit=10,
            embedder=_EMB, extractor=_NoEntities(),
            only_user_id=owner,
        )

        assert owner_memory in processed
        assert stranger_memory not in processed

        payloads = _queue_payloads(conn)
        assert any(payload.get("memory_id") == stranger_memory for payload in payloads)
        assert not any(payload.get("memory_id") == owner_memory for payload in payloads)
        assert _queue_delivery_state(conn, stranger_memory) == stranger_state

        archived = conn.execute(
            "select count(*)::int from pgmq.a_memory_jobs "
            "where (message->>'memory_id') = %s",
            (stranger_memory,),
        ).fetchone()[0]
        assert archived == 0
    finally:
        delete_user(conn, stranger)
        delete_user(conn, owner)
