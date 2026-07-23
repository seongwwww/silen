import pytest

from silen_worker.queue import QUEUE
from silen_worker.tasks.process import process_pending
from tests.conftest import seed_user, seed_memory, delete_user


class StubExtractor:
    """고정 후보를 반환하는 스텁. 실 Gemini 없이 파이프라인을 검증한다."""

    def __init__(self, candidates):
        self._candidates = candidates

    def extract(self, text):
        return self._candidates


def _entities_of(conn, user):
    return conn.execute(
        "select entity_type, name from public.entities where user_id = %s order by name",
        (user,),
    ).fetchall()


@pytest.mark.integration
def test_추출_결과가_entities_memory_entities로_저장된다(conn):
    conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "민수랑 김밥 먹음")  # 트리거가 큐에 넣음
        stub = StubExtractor(
            [{"type": "person", "name": "민수"}, {"type": "thing", "name": "김밥"}]
        )
        processed = process_pending(limit=10, extractor=stub)

        assert mem in processed
        rows = _entities_of(conn, user)
        assert ("person", "민수") in rows
        assert ("thing", "김밥") in rows
        link_count = conn.execute(
            "select count(*)::int from public.memory_entities where memory_id = %s", (mem,)
        ).fetchone()[0]
        assert link_count == 2
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_환각_후보는_저장되지_않는다(conn):
    conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "스벅에서 커피")
        stub = StubExtractor([{"type": "place", "name": "스타벅스"}])  # 원문에 없음
        process_pending(limit=10, extractor=stub)
        assert _entities_of(conn, user) == []
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_재처리해도_중복이_생기지_않는다(conn):
    conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "민수 또 봄")
        stub = StubExtractor([{"type": "person", "name": "민수"}])
        process_pending(limit=10, extractor=stub)
        # 같은 메모를 다시 큐에 넣어 재처리
        conn.execute("select pgmq.send(%s, %s)", (QUEUE, f'{{"memory_id":"{mem}","user_id":"{user}"}}'))
        process_pending(limit=10, extractor=stub)

        ent_count = conn.execute(
            "select count(*)::int from public.entities where user_id = %s", (user,)
        ).fetchone()[0]
        link_count = conn.execute(
            "select count(*)::int from public.memory_entities where memory_id = %s", (mem,)
        ).fetchone()[0]
        assert ent_count == 1
        assert link_count == 1
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_메모_삭제시_고아_entity가_사라진다(conn):
    conn.execute("select pgmq.purge_queue(%s)", (QUEUE,))
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "민수 혼자 언급")
        stub = StubExtractor([{"type": "person", "name": "민수"}])
        process_pending(limit=10, extractor=stub)
        assert len(_entities_of(conn, user)) == 1

        conn.execute("delete from public.memories where id = %s", (mem,))  # 링크 CASCADE → 트리거
        assert _entities_of(conn, user) == []
    finally:
        delete_user(conn, user)
